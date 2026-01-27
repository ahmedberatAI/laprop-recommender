import csv
import tempfile
import unittest
from pathlib import Path

from epey_scraper import OUTPUT_COLUMNS, write_rows_atomic


class TestEpeyCsvWrite(unittest.TestCase):
    def test_write_rows_atomic_writes_header_and_rows(self):
        rows = [
            {
                "url": "https://example.com/item1.html",
                "name": "Example One",
                "price": "1000",
                "screen_size": "15.6",
                "ssd": "512",
                "cpu": "i5",
                "ram": "8",
                "os": "Windows",
                "gpu": "Intel",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "out.csv"
            row_count, size = write_rows_atomic(path, rows)
            self.assertEqual(row_count, 1)
            self.assertGreater(size, 0)
            with path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, OUTPUT_COLUMNS)
                data = list(reader)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["url"], rows[0]["url"])

    def test_write_rows_atomic_writes_header_for_empty(self):
        rows = []

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "out.csv"
            row_count, size = write_rows_atomic(path, rows)
            self.assertEqual(row_count, 0)
            self.assertGreater(size, 0)
            with path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, OUTPUT_COLUMNS)
                data = list(reader)
            self.assertEqual(len(data), 0)
