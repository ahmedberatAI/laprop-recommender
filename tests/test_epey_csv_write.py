import csv
import json
import tempfile
import unittest
from pathlib import Path

from epey_scraper import OUTPUT_COLUMNS, generate_csv_from_jsonl


class TestEpeyCsvWrite(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def test_generate_csv_from_jsonl_writes_header_and_rows(self):
        rows = [
            {
                "source_url": "https://example.com/item1.html",
                "name": "Example One",
                "price_min_try": 1000,
                "cpu_model": "i5",
                "ram_gb": 8,
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            jsonl_path = Path(temp_dir) / "out.jsonl"
            csv_path = Path(temp_dir) / "out.csv"
            self._write_jsonl(jsonl_path, rows)

            generate_csv_from_jsonl(str(jsonl_path), str(csv_path))

            self.assertTrue(csv_path.exists())
            with csv_path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, OUTPUT_COLUMNS)
                data = list(reader)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["source_url"], rows[0]["source_url"])

    def test_generate_csv_from_jsonl_skips_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jsonl_path = Path(temp_dir) / "out.jsonl"
            csv_path = Path(temp_dir) / "out.csv"
            self._write_jsonl(jsonl_path, [])

            generate_csv_from_jsonl(str(jsonl_path), str(csv_path))

            self.assertFalse(csv_path.exists())
