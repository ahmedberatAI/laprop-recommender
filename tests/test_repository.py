"""Unit tests for laprop.storage.repository — deduplication helpers."""

import numpy as np
import pandas as pd
import pytest

from laprop.storage.repository import (
    _normalize_key_value,
    _build_row_key,
    _iter_existing_keys,
    _dedupe_dataframe,
    FALLBACK_FIELDS,
)


# ============================================================================
# _normalize_key_value
# ============================================================================
class TestNormalizeKeyValue:
    def test_none(self):
        assert _normalize_key_value(None) == ""

    def test_nan(self):
        assert _normalize_key_value(float("nan")) == ""

    def test_integer_float(self):
        assert _normalize_key_value(25000.0) == "25000"

    def test_fractional_float(self):
        assert _normalize_key_value(15.6) == "15.6"

    def test_string_stripped_lower(self):
        assert _normalize_key_value("  ASUS  ") == "asus"

    def test_normal_string(self):
        assert _normalize_key_value("laptop") == "laptop"


# ============================================================================
# _build_row_key
# ============================================================================
class TestBuildRowKey:
    def test_with_url(self):
        row = pd.Series({"name": "Laptop A", "price": 25000})
        key = _build_row_key("amazon", "https://example.com/a", row)
        assert "amazon" in key
        assert "url" in key
        assert "example.com" in key

    def test_without_url_uses_fallback(self):
        row = pd.Series({"name": "Laptop B", "price": 30000, "cpu": "i7"})
        key = _build_row_key("vatan", "", row)
        assert "fb" in key
        assert "laptop b" in key

    def test_none_url_uses_fallback(self):
        row = pd.Series({"name": "X"})
        key = _build_row_key("amazon", None, row)
        assert "fb" in key


# ============================================================================
# _iter_existing_keys
# ============================================================================
class TestIterExistingKeys:
    def test_nonexistent_file(self, tmp_path):
        keys = _iter_existing_keys(tmp_path / "nope.csv")
        assert keys == set()

    def test_existing_csv(self, tmp_path):
        csv_path = tmp_path / "all_data.csv"
        csv_path.write_text(
            "source,url,name,price\namazon,u1,Laptop A,25000\nvatan,,Laptop B,30000",
            encoding="utf-8",
        )
        keys = _iter_existing_keys(csv_path)
        assert len(keys) == 2

    def test_corrupt_csv(self, tmp_path):
        csv_path = tmp_path / "bad.csv"
        csv_path.write_bytes(b"\x80\x81\x82\x83")
        keys = _iter_existing_keys(csv_path)
        # Should handle gracefully
        assert isinstance(keys, set)


# ============================================================================
# _dedupe_dataframe
# ============================================================================
class TestDedupeDataframe:
    def test_removes_duplicates(self):
        existing = {"amazon||url||u1"}
        df = pd.DataFrame([
            {"source": "amazon", "url": "u1", "name": "A", "price": 100},  # dup
            {"source": "amazon", "url": "u2", "name": "B", "price": 200},  # new
        ])
        result, deduped = _dedupe_dataframe(df, existing)
        assert len(result) == 1
        assert deduped == 1
        assert result.iloc[0]["url"] == "u2"

    def test_removes_internal_duplicates(self):
        df = pd.DataFrame([
            {"source": "amazon", "url": "u1", "name": "A", "price": 100},
            {"source": "amazon", "url": "u1", "name": "A", "price": 100},  # dup
        ])
        result, deduped = _dedupe_dataframe(df, set())
        assert len(result) == 1
        assert deduped == 1

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result, deduped = _dedupe_dataframe(df, set())
        assert result.empty
        assert deduped == 0

    def test_no_duplicates(self):
        df = pd.DataFrame([
            {"source": "amazon", "url": "u1", "name": "A", "price": 100},
            {"source": "vatan", "url": "u2", "name": "B", "price": 200},
        ])
        result, deduped = _dedupe_dataframe(df, set())
        assert len(result) == 2
        assert deduped == 0

    def test_adds_missing_columns(self):
        df = pd.DataFrame([
            {"name": "A", "price": 100},
        ])
        result, deduped = _dedupe_dataframe(df, set())
        assert "source" in result.columns
        assert "url" in result.columns
        assert len(result) == 1
