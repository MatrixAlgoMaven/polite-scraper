import json
from pathlib import Path
import time

from src.models import Book
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

BASE_URL = "https://books.toscrape.com/"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
BOOK_CACHE_DIR = CACHE_DIR / "books"
REPORT_FILE = PROJECT_ROOT / "output" / "run-report.json"

HEADERS = {
    "User-Agent": (
        "PoliteScraper/1.0 "
        "(educational project; https://github.com/MatrixAlgoMaven)"
    )
}
TIMEOUT = 10
MIN_REQUEST_INTERVAL = 0.5

last_request_time = None
cache_hits = 0
pages_fetched = 0



def fetch_page(url: str, cache_file: Path) -> str:
    global last_request_time, cache_hits, pages_fetched

    if cache_file.exists():
        cache_hits += 1
        html = cache_file.read_text(encoding="utf-8")
        print(f"CACHE HIT: {cache_file.name}")
        return html

    if last_request_time is not None:
        elapsed = time.monotonic() - last_request_time
        remaining = MIN_REQUEST_INTERVAL - elapsed

        if remaining > 0:
            time.sleep(remaining)

    last_request_time = time.monotonic()

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    print(f"HTTP {response.status_code}: {url}")
    response.raise_for_status()

    pages_fetched += 1

    response.encoding = "utf-8"
    html = response.text
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(html, encoding="utf-8")
    print(f"CACHED: {cache_file.name}")

    return html



def discover_catalogue_pages() -> None:
    page_urls = [
        (BASE_URL, CACHE_DIR / "catalogue-page-1.html"),
    ]

    for page_number in range(1, 4):
        if page_number == 1:
            url, cache_file = page_urls[0]
        else:
            url = f"{BASE_URL}catalogue/page-{page_number}.html"
            cache_file = CACHE_DIR / f"catalogue-page-{page_number}.html"

        html = fetch_page(url, cache_file)
        soup = BeautifulSoup(html, "html.parser")
        books = soup.select("article.product_pod")

        print(f"Page {page_number}: {len(books)} book listings")

        if page_number < 3:
            next_link = soup.select_one("li.next a")
            if next_link is None:
                raise ValueError(
                    f"Page {page_number} has no next-page link"
                )

            print(f"Next-page link: {next_link.get('href')}")

    print("Catalogue discovery complete: checked pages 1–3.")

def discover_book_urls() -> list[dict]:
    all_books = []

    for page_number in range(1, 4):
        cache_file = CACHE_DIR / f"catalogue-page-{page_number}.html"
        html = cache_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        for book in soup.select("article.product_pod h3 a[href]"):
            if page_number == 1:
                catalogue_url = BASE_URL
            else:
                catalogue_url = f"{BASE_URL}catalogue/page-{page_number}.html"

            product_url = urljoin(catalogue_url, book["href"])

            all_books.append({
                "product_url": product_url,
                "source_page": page_number,
            })

    return all_books

def fetch_book_page(product_url: str) -> str:
    book_slug = product_url.rstrip("/").split("/")[-2]
    cache_file = BOOK_CACHE_DIR / f"{book_slug}.html"

    return fetch_page(product_url, cache_file)

def scrape_one_book(book: dict) -> dict:
    html = fetch_book_page(book["product_url"])

    return extract_book_fields(
        html,
        book["product_url"],
        book["source_page"],
    )

def scrape_all_books() -> list[dict]:
    books = discover_book_urls()
    scraped_books = []

    for index, book in enumerate(books, start=1):
        print(f"Scraping book {index}/{len(books)}: {book['product_url']}")

        try:
            scraped_book = scrape_one_book(book)
            scraped_books.append(scraped_book)
        except Exception as error:
            print(f"FAILED: {book['product_url']} — {error}")

    print(f"Scraping complete: {len(scraped_books)}/{len(books)} books extracted.")
    return scraped_books


def save_books(books: list[dict]) -> None:
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "books.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(books, file, indent=2, ensure_ascii=False)

    print(f"Saved {len(books)} books to {output_file}")


def save_errors(errors: list[dict]) -> None:
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "errors.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(errors, file, indent=2, ensure_ascii=False)

    print(f"Saved {len(errors)} errors to {output_file}")


def extract_book_fields(html: str, product_url: str, source_page: int) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.select_one("div.product_main h1")
    price = soup.select_one("p.price_color")
    availability = soup.select_one("p.availability")
    rating = soup.select_one("p.star-rating")
    description = soup.select_one("#product_description + p")

    return {
        "title": title.get_text(" ", strip=True) if title else None,
        "product_url": product_url,
        "price_text": price.get_text(" ", strip=True) if price else None,
        "price_gbp": (
            float(price.get_text(" ", strip=True).replace("£", "").strip())
            if price else None
        ),
        "availability_text": (
            availability.get_text(" ", strip=True) if availability else None
        ),
        "rating_text": (
            rating.get("class", [])[-1]
            if rating and len(rating.get("class", [])) > 1
            else None
        ),
        "description": (
            description.get_text(" ", strip=True) if description else None
        ),
        "source_page": source_page,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def save_run_report(report: dict) -> None:
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with REPORT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print(f"Saved run report to {REPORT_FILE}")


if __name__ == "__main__":
    run_started_at = datetime.now(timezone.utc)
    discover_catalogue_pages()

    books = scrape_all_books()
    valid_books = []
    errors = []

    for book in books:
        try:
            validated_book = Book.model_validate(book)
            valid_books.append(validated_book.model_dump(mode="json"))
        except Exception as error:
            errors.append({
                "product_url": book.get("product_url"),
                "source_page": book.get("source_page"),
                "record": book,
                "reason": str(error),
            })
            print(f"VALIDATION FAILED: {book.get('product_url')} — {error}")

    save_books(valid_books)
    save_errors(errors)
    run_finished_at = datetime.now(timezone.utc)
    duration_seconds = (run_finished_at - run_started_at).total_seconds()

    print(f"Run duration: {duration_seconds:.2f} seconds")
    run_report = {
        "started_at": run_started_at.isoformat(),
        "finished_at": run_finished_at.isoformat(),
        "duration_seconds": round(duration_seconds, 2),
        "pages_fetched": pages_fetched,
        "cache_hits": cache_hits,
        "valid_records": len(valid_books),
        "invalid_records": len(errors),
        "failed_pages": [],
    }

    save_run_report(run_report)

