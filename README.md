# The Polite Scraper

A Python web scraper that discovers, extracts, normalizes, validates, and stores book catalogue data from [Books to Scrape](https://books.toscrape.com/), a website designed for scraping practice.

The project focuses on responsible request handling, caching, data validation, error reporting, and repeatable runs.

## Target Classification

- **Target:** [Books to Scrape](https://books.toscrape.com/)
- **Purpose:** Educational web-scraping practice.
- **Scope:** The first three catalogue pages, covering 60 book listings.
- **Output:** Structured JSON records validated with Pydantic.
- **Browser requirement:** Browser automation is unnecessary for this static HTML target; Requests and Beautiful Soup are sufficient for the current scope.
- **Responsible use:** This project is limited to the practice sandbox. Check a site's rules and terms before adapting the scraper for another target.

### Robots Check

On 16 October 2026, a request to [https://books.toscrape.com/robots.txt](https://books.toscrape.com/robots.txt) returned HTTP 401 Unauthorized. This records the observed response only; it does not establish the contents of the robots file or imply permission to scrape other sites.

## Features

- Fetches the first three catalogue pages and discovers unique product URLs.
- Extracts book details from product pages.
- Normalizes GBP price text into a numeric `price_gbp` value.
- Validates records with a Pydantic model.
- Caches downloaded HTML to reduce repeat requests.
- Uses an identifying User-Agent and a 10-second request timeout.
- Waits at least 500 milliseconds between network-request attempts.
- Retries timeouts and HTTP 5xx responses once; does not retry HTTP 403 or 404 responses.
- Writes valid records, invalid-record details, and a run report to JSON files.
- Reuses cached pages on subsequent runs, avoiding unnecessary requests.

## Data Schema

Each valid book record contains:

| Field | Description |
|---|---|
| `title` | Book title |
| `product_url` | URL of the product page |
| `price_text` | Original displayed price text |
| `price_gbp` | Numeric price in GBP |
| `availability_text` | Availability text shown on the page |
| `rating_text` | Star rating as text |
| `description` | Book description |
| `source_page` | Catalogue page where the book was discovered (1–3) |
| `fetched_at` | UTC timestamp recorded during extraction |

Records are validated before they are written to `output/books.json`.

## Requirements

- Python 3.13
- Requests
- Beautiful Soup 4
- Pydantic

## Setup

Clone the repository and open its directory in a terminal.

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Run the Scraper

From the project root, run:

```powershell
python -m src.main
```

The scraper creates the cache and output directories as needed.

## Running the Tests

Run the automated test suite from the project root:

```powershell
python -m unittest discover -s tests -v
```

The tests cover:

- Price parsing and normalization to numeric GBP.
- Acceptance of valid book records.
- Rejection of records with a zero price.
- Rejection of records with an invalid catalogue page number.
- Retrying a request after a timeout and successfully caching the response.
- Avoiding retries after an HTTP 404 response.

The tests use mocked HTTP responses and temporary files. They do not require live network requests or depend on the scraper's cache files.

## Generated Files

The scraper writes these files under `output/`:

- `books.json` — validated book records.
- `errors.json` — details of records that failed scraping or validation.
- `run-report.json` — run status, timestamps, duration, page-fetch count, cache hits, record counts, and failed-page details.

Downloaded HTML is stored in `cache/` and reused on subsequent runs. Cache and generated output files are excluded from Git.

## Latest Verified Run

A completed run produced:

- **Status:** `success`
- **Valid records:** 60
- **Invalid records:** 0
- **Unique product URLs:** 60
- **Cache hits:** 63 (three catalogue pages and 60 product pages)

The run above used cached HTML, so these cache hits did not require new network requests. Run the scraper again to generate a fresh report for your environment.

## Limitations

- Only the first three catalogue pages are in scope.
- The scraper expects the current HTML structure of Books to Scrape; a site redesign may require selector changes.
- Cached HTML can become stale. Remove the relevant cache files when you intentionally want to fetch fresh pages.
- The recorded `fetched_at` timestamp is generated during extraction, including when a cached product page is used.

## Ethical Use

This is an educational project for a scraping practice site. Before scraping another website, review its terms, robots directives, access restrictions, and request limits. Use an identifying User-Agent, keep request rates conservative, and stop if the site denies access. Do not treat a successful HTTP response as permission to collect or reuse data.

## Project Structure

```text
polite-scraper/
├── src/
│   ├── main.py
│   └── models.py
├── tests/
│   └── test_scraper.py
├── requirements.txt
├── README.md
├── .gitignore
├── cache/              # Generated, ignored by Git
└── output/             # Generated, ignored by Git
```
