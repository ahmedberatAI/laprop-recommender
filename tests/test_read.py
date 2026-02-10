"""Unit tests for laprop.processing.read — parquet cache, CSV loading, helpers."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

from laprop.processing.read import (
    _sanitize_column_name,
    _standardize_columns,
    _count_filled_urls,
    _get_domain_counts,
    read_csv_robust,
    _save_cache,
    _load_cache,
)


# ============================================================================
# _sanitize_column_name
# ============================================================================
class TestSanitizeColumnName:
    def test_strips_bom_and_whitespace(self):
        assert _sanitize_column_name("\ufeffURL ") == "url"

    def test_lowercase(self):
        assert _sanitize_column_name("Price") == "price"

    def test_normal_name(self):
        assert _sanitize_column_name("name") == "name"


# ============================================================================
# _standardize_columns
# ============================================================================
class TestStandardizeColumns:
    def test_lowercases_columns(self):
        df = pd.DataFrame({"Name": [1], "PRICE": [2]})
        result = _standardize_columns(df)
        assert "name" in result.columns
        assert "price" in result.columns

    def test_merges_bom_url(self):
        df = pd.DataFrame({
            "url": ["a", None],
            "\ufeffurl": [None, "b"],
        })
        result = _standardize_columns(df)
        assert "url" in result.columns
        # The second row should have value "b" (filled from BOM column)
        assert result["url"].iloc[1] == "b"


# ============================================================================
# _count_filled_urls
# ============================================================================
class TestCountFilledUrls:
    def test_counts_non_empty(self):
        s = pd.Series(["https://a.com", "", None, "https://b.com", " "])
        assert _count_filled_urls(s) == 2

    def test_all_empty(self):
        s = pd.Series([None, "", " "])
        assert _count_filled_urls(s) == 0


# ============================================================================
# _get_domain_counts
# ============================================================================
class TestGetDomainCounts:
    def test_mixed_domains(self):
        s = pd.Series([
            "https://www.amazon.com.tr/dp/B0123",
            "https://www.vatanbilgisayar.com/laptop.html",
            "https://www.incehesap.com/notebook/123",
            "https://www.amazon.com.tr/dp/B0456",
            None,
        ])
        counts = _get_domain_counts(s)
        assert counts["amazon"] == 2
        assert counts["vatan"] == 1
        assert counts["incehesap"] == 1

    def test_empty_series(self):
        s = pd.Series([], dtype=str)
        counts = _get_domain_counts(s)
        assert counts["amazon"] == 0


# ============================================================================
# read_csv_robust
# ============================================================================
class TestReadCsvRobust:
    def test_reads_utf8_csv(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Name,Price\nLaptop A,25000\nLaptop B,30000", encoding="utf-8")
        df = read_csv_robust(csv_file)
        assert len(df) == 2
        assert "name" in df.columns
        assert "price" in df.columns

    def test_reads_csv_with_bom(self, tmp_path):
        csv_file = tmp_path / "test_bom.csv"
        csv_file.write_bytes(b"\xef\xbb\xbfName,Price\nLaptop,25000")
        df = read_csv_robust(csv_file)
        assert "name" in df.columns

    def test_invalid_file_raises(self, tmp_path):
        csv_file = tmp_path / "nonexistent.csv"
        with pytest.raises(Exception):
            read_csv_robust(csv_file)


# ============================================================================
# _save_cache / _load_cache (parquet round-trip)
# ============================================================================
class TestCacheRoundTrip:
    def test_save_and_load(self, tmp_path):
        """Verify parquet + metadata sidecar round-trip."""
        cache_file = tmp_path / "test_cache.parquet"
        meta_file = cache_file.with_suffix(".meta.json")

        df = pd.DataFrame({
            "name": ["Laptop A", "Laptop B"],
            "price": [20000, 30000],
            "mixed_col": ["text", 42],  # mixed type object column
        })
        expected_files = ["a.csv", "b.csv"]
        vatan_stats = (100, 80)

        # Patch the module-level CACHE_FILE and _CACHE_META
        with patch("laprop.processing.read.CACHE_FILE", cache_file), \
             patch("laprop.processing.read._CACHE_META", meta_file):
            _save_cache(df, expected_files, vatan_stats)
            assert cache_file.exists()
            assert meta_file.exists()

            # Verify metadata
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            assert meta["data_files"] == expected_files
            assert meta["vatan_stats"] == [100, 80]

            # Load back
            result = _load_cache(expected_files)
            assert result is not None
            loaded_df, loaded_stats = result
            assert len(loaded_df) == 2
            assert loaded_stats == (100, 80)

    def test_load_cache_metadata_mismatch(self, tmp_path):
        """Cache should return None when data_files don't match."""
        cache_file = tmp_path / "test_cache.parquet"
        meta_file = cache_file.with_suffix(".meta.json")

        df = pd.DataFrame({"name": ["A"], "price": [1000]})

        with patch("laprop.processing.read.CACHE_FILE", cache_file), \
             patch("laprop.processing.read._CACHE_META", meta_file):
            _save_cache(df, ["a.csv"], None)
            # Try to load with different expected files
            result = _load_cache(["different.csv"])
            assert result is None

    def test_load_cache_missing_file(self, tmp_path):
        """Cache should return None when parquet file doesn't exist."""
        cache_file = tmp_path / "nonexistent.parquet"
        with patch("laprop.processing.read.CACHE_FILE", cache_file):
            result = _load_cache(["a.csv"])
            assert result is None

    def test_save_cache_with_none_vatan_stats(self, tmp_path):
        cache_file = tmp_path / "test_cache.parquet"
        meta_file = cache_file.with_suffix(".meta.json")

        df = pd.DataFrame({"name": ["A"], "price": [1000]})

        with patch("laprop.processing.read.CACHE_FILE", cache_file), \
             patch("laprop.processing.read._CACHE_META", meta_file):
            _save_cache(df, ["a.csv"], None)
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            assert "vatan_stats" not in meta


# ============================================================================
# load_data (with mocked CSV files)
# ============================================================================
class TestLoadData:
    def test_load_data_from_csvs(self, tmp_path):
        """Test load_data reading actual CSV files."""
        from laprop.processing.read import load_data

        # Create test CSV files
        csv1 = tmp_path / "amazon_laptops.csv"
        csv1.write_text(
            "name,price,url\nLaptop A,25000,https://amazon.com.tr/a\nLaptop B,30000,https://amazon.com.tr/b",
            encoding="utf-8",
        )
        csv2 = tmp_path / "vatan_laptops.csv"
        csv2.write_text(
            "name,price,url\nLaptop C,20000,https://vatanbilgisayar.com/c.html",
            encoding="utf-8",
        )

        cache_file = tmp_path / "laptop_cache.parquet"
        meta_file = cache_file.with_suffix(".meta.json")
        data_files = [csv1, csv2]

        with patch("laprop.processing.read.DATA_FILES", data_files), \
             patch("laprop.processing.read.CACHE_FILE", cache_file), \
             patch("laprop.processing.read._CACHE_META", meta_file):
            result = load_data(use_cache=False)
            assert result is not None
            assert len(result) == 3
            assert "name" in result.columns
            # Cache should have been created
            assert cache_file.exists()

    def test_load_data_from_cache(self, tmp_path):
        """Test load_data using cached parquet."""
        from laprop.processing.read import load_data

        cache_file = tmp_path / "laptop_cache.parquet"
        meta_file = cache_file.with_suffix(".meta.json")

        df = pd.DataFrame({
            "name": ["Cached Laptop A", "Cached Laptop B"],
            "price": [25000, 30000],
            "url": ["https://amazon.com.tr/a", "https://vatanbilgisayar.com/b.html"],
        })
        expected_files = ["a.csv", "b.csv"]

        with patch("laprop.processing.read.CACHE_FILE", cache_file), \
             patch("laprop.processing.read._CACHE_META", meta_file), \
             patch("laprop.processing.read.DATA_FILES", [Path("a.csv"), Path("b.csv")]):
            _save_cache(df, expected_files, (1, 1))
            result = load_data(use_cache=True)
            assert result is not None
            assert len(result) == 2
            assert result["name"].iloc[0] == "Cached Laptop A"

    def test_load_data_no_files(self, tmp_path):
        """Test load_data when no CSV files exist."""
        from laprop.processing.read import load_data

        cache_file = tmp_path / "laptop_cache.parquet"
        meta_file = cache_file.with_suffix(".meta.json")
        nonexistent = [tmp_path / "none1.csv", tmp_path / "none2.csv"]

        with patch("laprop.processing.read.DATA_FILES", nonexistent), \
             patch("laprop.processing.read.CACHE_FILE", cache_file), \
             patch("laprop.processing.read._CACHE_META", meta_file):
            result = load_data(use_cache=False)
            assert result is None


class TestReadCsvRobustAdditional:
    def test_reads_semicolon_csv(self, tmp_path):
        csv_file = tmp_path / "semi.csv"
        csv_file.write_text("Name;Price\nLaptop A;25000\nLaptop B;30000", encoding="utf-8")
        df = read_csv_robust(csv_file)
        assert len(df) == 2

    def test_reads_cp1254_csv(self, tmp_path):
        csv_file = tmp_path / "turkish.csv"
        csv_file.write_text("Name,Price\nLaptop \u00dc,25000", encoding="cp1254")
        df = read_csv_robust(csv_file)
        assert len(df) == 1
