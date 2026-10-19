
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import requests
from pydantic import ValidationError
from requests.exceptions import Timeout

from src.main import extract_book_fields, fetch_page
from src.models import Book


class TestPriceParsing(unittest.TestCase):
    def test_price_is_normalized_to_numeric_gbp(self):
        html = """
        <html>
            <body>
                <div class="product_main">
                    <h1>Test Book</h1>
                    <p class="price_color">£51.77</p>
                    <p class="availability in-stock">
                        In stock (22 available)
                    </p>
                    <p class="star-rating Three"></p>
                </div>
                <div id="product_description">
                    <h2>Product Description</h2>
                </div>
                <p>A sample book description.</p>
            </body>
        </html>
        """

        result = extract_book_fields(
            html,
            "https://books.toscrape.com/catalogue/test-book_1000/index.html",
            1,
        )

        self.assertEqual(result["price_text"], "£51.77")
        self.assertEqual(result["price_gbp"], 51.77)
        self.assertEqual(result["title"], "Test Book")


class TestBookValidation(unittest.TestCase):
    def setUp(self):
        self.valid_book = {
            "title": "Test Book",
            "product_url": (
                "https://books.toscrape.com/"
                "catalogue/test-book_1000/index.html"
            ),
            "price_text": "£51.77",
            "price_gbp": 51.77,
            "availability_text": "In stock",
            "rating_text": "Three",
            "description": "A sample book description.",
            "source_page": 1,
            "fetched_at": datetime.now(timezone.utc),
        }

    def test_valid_book_passes_validation(self):
        book = Book(**self.valid_book)
        self.assertEqual(book.title, "Test Book")

    def test_zero_price_fails_validation(self):
        invalid_book = self.valid_book.copy()
        invalid_book["price_gbp"] = 0

        with self.assertRaises(ValidationError):
            Book(**invalid_book)

    def test_source_page_out_of_range_fails_validation(self):
        invalid_book = self.valid_book.copy()
        invalid_book["source_page"] = 4

        with self.assertRaises(ValidationError):
            Book(**invalid_book)


class TestFetchRetry(unittest.TestCase):
    def test_timeout_retries_and_then_succeeds(self):
        with TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test.html"

            response = Mock()
            response.status_code = 200
            response.text = "<html>Success</html>"
            response.raise_for_status.return_value = None

            with (
                patch(
                    "src.main.requests.get",
                    side_effect=[
                        Timeout("temporary timeout"),
                        response,
                    ],
                ) as mock_get,
                patch("src.main.time.sleep"),
            ):
                html = fetch_page(
                    "https://example.com/test",
                    cache_file,
                )

            self.assertEqual(html, "<html>Success</html>")
            self.assertEqual(mock_get.call_count, 2)
            self.assertTrue(cache_file.exists())
            self.assertEqual(
                cache_file.read_text(encoding="utf-8"),
                html,
            )

    def test_404_is_not_retried(self):
        with TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "missing.html"

            response = Mock()
            response.status_code = 404
            response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                "404 Not Found",
                response=response,
            )

            with (
                patch(
                    "src.main.requests.get",
                    return_value=response,
                ) as mock_get,
                patch("src.main.time.sleep"),
            ):
                with self.assertRaises(requests.exceptions.HTTPError):
                    fetch_page(
                        "https://example.com/missing",
                        cache_file,
                    )

            self.assertEqual(mock_get.call_count, 1)
            self.assertFalse(cache_file.exists())


if __name__ == "__main__":
    unittest.main()
