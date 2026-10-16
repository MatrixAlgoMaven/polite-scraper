
from pathlib import Path

import requests

BASE_URL = "https://books.toscrape.com/"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
CACHE_FILE = CACHE_DIR / "catalogue-page-1.html"

HEADERS = {
    "User-Agent": (
        "PoliteScraper/1.0 "
        "(educational project; https://github.com/MatrixAlgoMaven)"
    )
}

TIMEOUT = 10


def fetch_catalogue_page():
    if CACHE_FILE.exists():
        html = CACHE_FILE.read_text(encoding="utf-8")
        print(f"CACHE HIT: bytes={len(html.encode('utf-8'))}")
        return html

    response = requests.get(
        BASE_URL,
        headers=HEADERS,
        timeout=TIMEOUT,
    )

    print(f"HTTP status: {response.status_code}")
    response.raise_for_status()

    html = response.text

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(html, encoding="utf-8")

    print(f"FETCH: bytes={len(html.encode('utf-8'))}")
    print(f"Saved HTML to: {CACHE_FILE.relative_to(PROJECT_ROOT)}")

    return html


if __name__ == "__main__":
    fetch_catalogue_page()
