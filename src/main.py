
from pathlib import Path
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"

HEADERS = {
    "User-Agent": (
        "PoliteScraper/1.0 "
        "(educational project; https://github.com/MatrixAlgoMaven)"
    )
}
TIMEOUT = 10
MIN_REQUEST_INTERVAL = 0.5

last_request_time = None


def fetch_page(url: str, cache_file: Path) -> str:
    global last_request_time

    if cache_file.exists():
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


if __name__ == "__main__":
    discover_catalogue_pages()
