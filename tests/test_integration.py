"""Integration tests — end-to-end pipeline: raw data → clean → recommend."""

import numpy as np
import pandas as pd
import pytest

from laprop.processing.clean import clean_data
from laprop.recommend.engine import (
    calculate_score,
    get_recommendations,
    filter_by_usage,
)


@pytest.mark.integration
class TestEndToEndPipeline:
    """Simulate the full pipeline: raw CSV → clean_data → get_recommendations."""

    @pytest.fixture
    def realistic_raw_df(self):
        """A larger, more realistic raw DataFrame."""
        rows = [
            {
                "name": "ASUS TUF Gaming F15 Intel Core i7-12700H 16GB DDR5 512GB SSD RTX 4050 15.6\" FHD 144Hz",
                "price": 32999,
                "ram": "16 GB DDR5",
                "ssd": "512 GB SSD",
                "screen_size": '15.6"',
                "url": "https://www.amazon.com.tr/dp/B0ASUS",
            },
            {
                "name": "Lenovo IdeaPad 3 Intel Core i5-1235U 8GB RAM 256GB SSD 15.6 FHD",
                "price": 15999,
                "ram": "8 GB",
                "ssd": "256GB",
                "screen_size": None,
                "url": "https://www.vatanbilgisayar.com/lenovo.html",
            },
            {
                "name": "Apple MacBook Air M2 8GB 256GB SSD 13.6 inch",
                "price": 35999,
                "ram": None,
                "ssd": None,
                "screen_size": "13.6 inch",
                "url": "https://www.amazon.com.tr/dp/B0MAC",
            },
            {
                "name": "MSI Katana 15 i7-13620H 16GB 1TB SSD RTX 4070 15.6\" FHD",
                "price": 55999,
                "ram": "16 GB",
                "ssd": "1 TB SSD NVMe",
                "screen_size": '15.6"',
                "url": "https://www.incehesap.com/msi-katana",
            },
            {
                "name": "HP Pavilion 15 Ryzen 5 7530U 16GB 512GB SSD 15.6\" FHD",
                "price": 22999,
                "ram": "16 GB DDR4",
                "ssd": "512 GB SSD",
                "screen_size": '15.6"',
                "url": "https://www.vatanbilgisayar.com/hp-pavilion.html",
            },
            {
                "name": "Dell XPS 13 Plus Intel Core i7-1360P 16GB LPDDR5 512GB SSD 13.4\" OLED",
                "price": 45999,
                "ram": "16 GB LPDDR5",
                "ssd": "512 GB NVMe",
                "screen_size": '13.4"',
                "url": "https://www.amazon.com.tr/dp/B0DELL",
            },
            {
                "name": "Acer Nitro 5 AN515 Ryzen 7 7735HS 16GB 512GB SSD RTX 4060 15.6\" FHD",
                "price": 38999,
                "ram": "16 GB",
                "ssd": "512 GB",
                "screen_size": '15.6"',
                "url": "https://www.incehesap.com/acer-nitro",
            },
            {
                "name": "Casper Excalibur G770 i5-12500H 16GB 500GB SSD RTX 3050 15.6\" FHD",
                "price": 25999,
                "ram": "16 GB",
                "ssd": "500 GB",
                "screen_size": '15.6"',
                "url": "https://www.vatanbilgisayar.com/casper.html",
            },
        ]
        return pd.DataFrame(rows)

    def test_clean_data_produces_valid_df(self, realistic_raw_df):
        cleaned = clean_data(realistic_raw_df)
        assert len(cleaned) >= 3, "At least 3 laptops should survive cleaning"
        # Essential columns present
        for col in ["name", "price", "brand", "cpu", "gpu", "ram_gb", "ssd_gb", "cpu_score", "gpu_score"]:
            assert col in cleaned.columns, f"Missing column: {col}"
        # All prices valid
        assert (cleaned["price"] > 5000).all()

    def test_full_pipeline_productivity(self, realistic_raw_df):
        cleaned = clean_data(realistic_raw_df)
        prefs = {
            "min_budget": 15000,
            "max_budget": 50000,
            "usage_key": "productivity",
            "usage_label": "Productivity",
        }
        results = get_recommendations(cleaned, prefs, top_n=3)
        assert isinstance(results, pd.DataFrame)
        if not results.empty:
            assert "score" in results.columns
            assert results["score"].between(0, 100).all()
            assert len(results) <= 3

    def test_full_pipeline_gaming(self, realistic_raw_df):
        cleaned = clean_data(realistic_raw_df)
        prefs = {
            "min_budget": 25000,
            "max_budget": 60000,
            "usage_key": "gaming",
            "usage_label": "Gaming",
            "min_gpu_score_required": 5.0,
            "gaming_min_gpu": 5.0,
        }
        results = get_recommendations(cleaned, prefs, top_n=3)
        assert isinstance(results, pd.DataFrame)
        # Gaming results should have decent GPU
        if not results.empty:
            assert (results["gpu_score"] >= 4.0).all()

    def test_full_pipeline_portability(self, realistic_raw_df):
        cleaned = clean_data(realistic_raw_df)
        prefs = {
            "min_budget": 15000,
            "max_budget": 50000,
            "usage_key": "portability",
            "usage_label": "Portability",
        }
        results = get_recommendations(cleaned, prefs, top_n=3)
        assert isinstance(results, pd.DataFrame)

    def test_full_pipeline_dev_web(self, realistic_raw_df):
        cleaned = clean_data(realistic_raw_df)
        prefs = {
            "min_budget": 15000,
            "max_budget": 50000,
            "usage_key": "dev",
            "usage_label": "Dev",
            "dev_mode": "web",
        }
        results = get_recommendations(cleaned, prefs, top_n=3)
        assert isinstance(results, pd.DataFrame)

    def test_scores_are_deterministic(self, realistic_raw_df):
        """Same input should produce same output."""
        cleaned = clean_data(realistic_raw_df)
        prefs = {
            "min_budget": 15000,
            "max_budget": 60000,
            "usage_key": "productivity",
            "usage_label": "Prod",
        }
        r1 = get_recommendations(cleaned.copy(), prefs, top_n=3)
        r2 = get_recommendations(cleaned.copy(), prefs, top_n=3)
        if not r1.empty and not r2.empty:
            assert list(r1["score"]) == list(r2["score"])

    def test_clean_then_filter(self, realistic_raw_df):
        """Verify filter_by_usage works on cleaned data."""
        cleaned = clean_data(realistic_raw_df)
        prefs = {"usage_key": "gaming", "min_gpu_score_required": 6.0}
        filtered = filter_by_usage(cleaned, "gaming", prefs)
        # Should not crash and should return a DataFrame
        assert isinstance(filtered, pd.DataFrame)
