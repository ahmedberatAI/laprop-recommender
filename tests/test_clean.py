"""Unit tests for laprop.processing.clean."""

import math

import numpy as np
import pandas as pd
import pytest

from laprop.processing.clean import (
    clean_ram_value,
    clean_ssd_value,
    clean_price,
    extract_brand,
    clean_data,
)


# ============================================================================
# clean_ram_value
# ============================================================================
class TestCleanRamValue:
    @pytest.mark.parametrize("inp,expected", [
        ("16 GB DDR5", 16),
        ("8GB", 8),
        ("(32GB) DDR4", 32),
        ("8GB + 8GB = 16GB", 16),
        ("4", 4),
        ("128", 128),
        ("abc", 8),      # default
        (None, 8),
        (np.nan, 8),
    ])
    def test_various_inputs(self, inp, expected):
        assert clean_ram_value(inp) == expected

    def test_just_number_invalid(self):
        # 7 is not in the valid RAM set
        assert clean_ram_value("7") == 8


# ============================================================================
# clean_ssd_value
# ============================================================================
class TestCleanSsdValue:
    @pytest.mark.parametrize("inp,expected", [
        ("512 GB SSD", 512),
        ("1TB SSD NVMe", 1024),
        ("256GB", 256),
    ])
    def test_valid_inputs(self, inp, expected):
        result = clean_ssd_value(inp)
        assert result == expected

    def test_none_returns_nan(self):
        assert math.isnan(clean_ssd_value(None))

    def test_nan_returns_nan(self):
        assert math.isnan(clean_ssd_value(np.nan))

    def test_empty_string_returns_nan(self):
        assert math.isnan(clean_ssd_value(""))

    def test_plain_number_string(self):
        # "512" should be parsed as 512 GB
        result = clean_ssd_value("512")
        assert result == 512

    def test_form_factor_returns_nan(self):
        # 2280 is a form factor, not a capacity
        result = clean_ssd_value("2280")
        assert math.isnan(result)


# ============================================================================
# clean_price
# ============================================================================
class TestCleanPrice:
    @pytest.mark.parametrize("inp,expected", [
        ("32.999 TL", 32999),
        ("15999", 15999),
        (42999, 42999),
        (42999.0, 42999),
        ("1.234.567", None),   # >500000
        ("500", None),         # <1000
        (None, None),
        (np.nan, None),
    ])
    def test_price_parsing(self, inp, expected):
        result = clean_price(inp)
        assert result == expected


# ============================================================================
# extract_brand
# ============================================================================
class TestExtractBrand:
    @pytest.mark.parametrize("name,expected", [
        ("ASUS ROG Strix G16", "asus"),
        ("Lenovo ThinkPad X1", "lenovo"),
        ("Apple MacBook Air M2", "apple"),
        ("Dell XPS 13", "dell"),
        ("HP Pavilion 15", "hp"),
        ("MSI Katana 15", "msi"),
        ("Acer Nitro 5", "acer"),
        ("Microsoft Surface Laptop", "microsoft"),
        ("Huawei MateBook D16", "huawei"),
        ("Samsung Galaxy Book", "samsung"),
        ("Monster Tulpar T5", "monster"),
        ("Casper Excalibur G770", "casper"),
        ("Unknown Brand Laptop", "other"),
        (None, "other"),
        (np.nan, "other"),
    ])
    def test_brand_detection(self, name, expected):
        assert extract_brand(name) == expected

    def test_keyword_variants(self):
        assert extract_brand("ROG STRIX something") == "asus"
        assert extract_brand("Predator Helios 300") == "acer"
        assert extract_brand("Legion 5 Pro") == "lenovo"
        assert extract_brand("Alienware m18") == "dell"
        assert extract_brand("OMEN 16 Gaming") == "hp"
        assert extract_brand("Victus 15") == "hp"


# ============================================================================
# clean_data (integration-like)
# ============================================================================
class TestCleanData:
    def test_clean_data_produces_expected_columns(self, raw_csv_df):
        result = clean_data(raw_csv_df)
        expected_cols = {"name", "price", "brand", "cpu", "gpu", "gpu_norm",
                         "ram_gb", "ssd_gb", "screen_size", "cpu_score",
                         "gpu_score", "os", "parse_warnings"}
        assert expected_cols.issubset(set(result.columns))

    def test_clean_data_drops_invalid_price(self):
        df = pd.DataFrame({
            "name": ["Test Laptop"],
            "price": ["abc"],
            "url": ["https://example.com"],
        })
        result = clean_data(df)
        assert len(result) == 0

    def test_clean_data_drops_low_price(self):
        df = pd.DataFrame({
            "name": ["Cheap Laptop"],
            "price": [3000],
            "url": ["https://example.com"],
        })
        result = clean_data(df)
        assert len(result) == 0  # price < 5000

    def test_clean_data_basic_flow(self, raw_csv_df):
        result = clean_data(raw_csv_df)
        # At least 1 row should survive (the valid ones)
        assert len(result) >= 1
        # All prices should be > 5000
        assert (result["price"] > 5000).all()
        # brand should be populated
        assert result["brand"].notna().all()

    def test_vatan_url_filtering(self):
        """Vatan rows without .html should be removed."""
        df = pd.DataFrame({
            "name": ["Laptop A", "Laptop B"],
            "price": [25000, 30000],
            "url": [
                "https://www.vatanbilgisayar.com/notebook-laptop/",
                "https://www.vatanbilgisayar.com/laptop-b.html",
            ],
        })
        result = clean_data(df)
        # Only the .html URL should survive
        if len(result) > 0:
            urls = result["url"].tolist()
            for u in urls:
                if "vatanbilgisayar.com" in str(u):
                    assert ".html" in str(u)
