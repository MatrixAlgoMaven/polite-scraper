
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError, Timeout

from src.models import Book


BASE_URL = "https://books.toscrape.com/"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
BOOK_CACHE_DIR = CACHE_DIR / "books"
OUTPUT_DIR = PROJECT_ROOT / "output"

BOOKS_FILE = OUTPUT_DIR / "books.json"
ERRORS_FILE = OUTPUT_DIR / "errors.json"
REPORT_FILE = OUTPUT_DIR / "run-report.json"

HEADERS = {
    "User-Agent": (
        "PoliteScraper/1.0 "
        "(educational project; https://github.com/MatrixAlgoMaven)"
    )
}

TIMEOUT = 10
MIN_REQUEST_INTERVAL = 0.5
MAX_RETRIES = 1
RETRY_DELAY = 1

last_request_time = None
cache_hits = 0
pages_fetched = 0
failed_pages = []


def fetch_page(url: str, cache_file: Path) -> str:
    """Read cached HTML or download and cache a page politely."""
    global last_request_time, cache_hits, pages_fetched

    if cache_file.exists():
        cache_hits += 1
        print(f"CACHE HIT: {cache_file.name}")
        return cache_file.read_text(encoding="utf-8")

    for attempt in range(MAX_RETRIES + 1):
        if last_request_time is not None:
            elapsed = time.monotonic() - last_request_time
            remaining = MIN_REQUEST_INTERVAL - elapsed
            if remaining > 0:
                time.sleep(remaining)

        last_request_time = time.monotonic()

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            print(f"HTTP {response.status_code}: {url}")
            response.raise_for_status()

            # Requests detects the response encoding; use its decoded text.
            html = response.text

            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(html, encoding="utf-8")
            pages_fetched += 1

            print(f"CACHED: {cache_file.name}")
            return html

        except Timeout:
            if attempt < MAX_RETRIES:
                print(f"Timeout. Retrying once: {url}")
                time.sleep(RETRY_DELAY)
            else:
                raise

        except HTTPError as error:
            status = error.response.status_code if error.response else 0

            if status >= 500 and attempt < MAX_RETRIES:
                print(f"HTTP {status}. Retrying once: {url}")
                time.sleep(RETRY_DELAY)
            else:
                raise

    raise RuntimeError(f"Failed to fetch URL after retries: {url}")


def catalogue_url(page_number: int) -> str:
    """Return the URL for one of the first three catalogue pages."""
    if page_number == 1:
        return BASE_URL
    return urljoin(BASE_URL, f"catalogue/page-{page_number}.html")


def discover_catalogue_pages() -> None:
    """Fetch/cache catalogue pages and verify their listings."""
    for page_number in range(1, 4):
        url = catalogue_url(page_number)
        cache_file = CACHE_DIR / f"catalogue-page-{page_number}.html"

        try:
            html = fetch_page(url, cache_file)
            soup = BeautifulSoup(html, "html.parser")
            books = soup.select("article.product_pod")

            if len(books) != 20:
                raise ValueError(
                    f"Expected 20 listings on page {page_number}, "
                    f"found {len(books)}"
                )

            print(f"Page {page_number}: {len(books)} book listings")

        except Exception as error:
            failed_pages.append({
                "url": url,
                "source_page": page_number,
                "reason": str(error),
            })
            raise


def discover_book_urls() -> list[dict]:
    """Discover unique product URLs from the three cached catalogues."""
    discovered = {}

    for page_number in range(1, 4):
        cache_file = CACHE_DIR / f"catalogue-page-{page_number}.html"
        html = cache_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        page_url = catalogue_url(page_number)

        for link in soup.select("article.product_pod h3 a[href]"):
            product_url = urljoin(page_url, link["href"])
            discovered.setdefault(product_url, {
                "product_url": product_url,
                "source_page": page_number,
            })

    books = list(discovered.values())

    if len(books) != 60:
        raise ValueError(
            f"Expected 60 unique books, discovered {len(books)}"
        )

    return books


def fetch_book_page(product_url: str) -> str:
    """Fetch/cache a product page using a stable filename."""
    path_parts = urlparse(product_url).path.rstrip("/").split("/")
    slug = path_parts[-2] if len(path_parts) >= 2 else path_parts[-1]

    cache_file = BOOK_CACHE_DIR / f"{slug}.html"
    return fetch_page(product_url, cache_file)


def extract_book_fields(
    html: str,
    product_url: str,
    source_page: int,
) -> dict:
    """Extract raw fields and normalize the book price."""
    soup = BeautifulSoup(html, "html.parser")

    title = soup.select_one("div.product_main h1")
    price = soup.select_one("p.price_color")
    availability = soup.select_one("p.availability")
    rating = soup.select_one("p.star-rating")
    description = soup.select_one("#product_description + p")

    if not all([title, price, availability, rating, description]):
        raise ValueError("One or more required product fields are missing")

    # HTML entities are decoded by Beautiful Soup. Remove only currency
    # characters and surrounding whitespace before converting the price.
    price_text = price.get_text(" ", strip=True).replace("\xa0", " ").strip()
    numeric_text = price_text.replace("£", "").strip()
    numeric_text = numeric_text.replace(",", "")

    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", numeric_text):
        raise ValueError(f"Could not parse price: {price_text!r}")

    rating_classes = rating.get("class", [])
    rating_text = next(
        (item for item in rating_classes if item in {
            "One", "Two", "Three", "Four", "Five"
        }),
        None,
    )

    if rating_text is None:
        raise ValueError("Book rating is missing or invalid")

    return {
        "title": title.get_text(" ", strip=True),
        "product_url": product_url,
        "price_text": price_text,
        "price_gbp": float(numeric_text),
        "availability_text": availability.get_text(" ", strip=True),
        "rating_text": rating_text,
        "description": description.get_text(" ", strip=True),
        "source_page": source_page,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def scrape_one_book(book: dict) -> dict:
    html = fetch_book_page(book["product_url"])
    return extract_book_fields(
        html,
        book["product_url"],
        book["source_page"],
    )


def scrape_all_books() -> list[dict]:
    """Scrape each discovered book, recording individual failures."""
    scraped_books = []

    for index, book in enumerate(discover_book_urls(), start=1):
        url = book["product_url"]
        print(f"Scraping book {index}/60: {url}")

        try:
            scraped_books.append(scrape_one_book(book))
        except Exception as error:
            failed_pages.append({
                "url": url,
                "source_page": book["source_page"],
                "reason": str(error),
            })
            scraped_books.append({
                "_scrape_error": str(error),
                "product_url": url,
                "source_page": book["source_page"],
            })
            print(f"FAILED: {url} — {error}")

    return scraped_books


def save_json(path: Path, data) -> None:
    """Write readable UTF-8 JSON without escaping Unicode characters."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")


def save_books(books: list[dict]) -> None:
    save_json(BOOKS_FILE, books)
    print(f"Saved {len(books)} books to {BOOKS_FILE}")


def save_errors(errors: list[dict]) -> None:
    save_json(ERRORS_FILE, errors)
    print(f"Saved {len(errors)} errors to {ERRORS_FILE}")


def save_run_report(report: dict) -> None:
    save_json(REPORT_FILE, report)
    print(f"Saved run report to {REPORT_FILE}")


def main() -> None:
    global last_request_time, cache_hits, pages_fetched, failed_pages

    run_started_at = datetime.now(timezone.utc)
    last_request_time = None
    cache_hits = 0
    pages_fetched = 0
    failed_pages = []

    valid_books = []
    errors = []
    catalogue_ok = False

    try:
        discover_catalogue_pages()
        catalogue_ok = True
        scraped_books = scrape_all_books()

        for book in scraped_books:
            if "_scrape_error" in book:
                errors.append({
                    "product_url": book["product_url"],
                    "source_page": book["source_page"],
                    "reason": book["_scrape_error"],
                })
                continue

            try:
                validated = Book.model_validate(book)
                valid_books.append(validated.model_dump(mode="json"))
            except Exception as error:
                errors.append({
                    "product_url": book.get("product_url"),
                    "source_page": book.get("source_page"),
                    "record": book,
                    "reason": str(error),
                })

        # Replace the output files only after catalogue discovery succeeds.
        save_books(valid_books)
        save_errors(errors)

    except Exception as error:
        print(f"SCRAPER RUN FAILED: {error}")
        errors.append({
            "stage": "catalogue",
            "reason": str(error),
        })
        # Preserve the previous books.json and errors.json if catalogue
        # discovery fails before the scraping stage completes.
        if not catalogue_ok:
            print("Keeping previous books.json and errors.json unchanged.")
        else:
            save_errors(errors)

    finished_at = datetime.now(timezone.utc)
    duration = (finished_at - run_started_at).total_seconds()

    if not catalogue_ok:
        status = "failed"
    elif errors or failed_pages:
        status = "partial_failure"
    else:
        status = "success"

    report = {
        "status": status,
        "started_at": run_started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(duration, 2),
        "pages_fetched": pages_fetched,
        "cache_hits": cache_hits,
        "valid_records": len(valid_books),
        "invalid_records": len(errors),
        "failed_pages": failed_pages,
    }

    save_run_report(report)
    print(f"Run status: {status}")
    print(f"Valid records: {len(valid_books)}")
    print(f"Errors: {len(errors)}")


if __name__ == "__main__":
    main()
