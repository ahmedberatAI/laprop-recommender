"""Shared fixtures for the laprop test suite."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure src/ is on the path so "import laprop" works when running from repo root.
repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
for p in (src_path, repo_root):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

# Reconfigure stdout/stderr for Windows Unicode safety.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_laptop_row():
    """A single laptop row dict with all expected fields populated."""
    return {
        "name": "ASUS ROG Strix G16 Intel Core i7-13650HX 16GB 512GB SSD RTX 4060 16\" FHD 144Hz",
        "price": 42999,
        "brand": "asus",
        "cpu": "I7-13650HX",
        "gpu": "RTX 4060",
        "gpu_norm": "GeForce RTX 4060",
        "ram_gb": 16.0,
        "ssd_gb": 512.0,
        "screen_size": 16.0,
        "cpu_score": 8.0,
        "gpu_score": 8.0,
        "os": "freedos",
        "url": "https://www.amazon.com.tr/dp/B0TEST",
    }


@pytest.fixture
def sample_laptop_df(sample_laptop_row):
    """A small DataFrame with diverse laptop entries for filter / score tests."""
    rows = [
        sample_laptop_row,
        {
            "name": "Lenovo IdeaPad Slim 5 Intel Core i5-1335U 8GB 256GB SSD 14\" FHD",
            "price": 18999,
            "brand": "lenovo",
            "cpu": "I5-1335U",
            "gpu": "integrated",
            "gpu_norm": "Intel Iris Xe (iGPU)",
            "ram_gb": 8.0,
            "ssd_gb": 256.0,
            "screen_size": 14.0,
            "cpu_score": 6.0,
            "gpu_score": 2.5,
            "os": "windows",
            "url": "https://www.vatanbilgisayar.com/lenovo.html",
        },
        {
            "name": "Apple MacBook Air M2 8GB 256GB SSD 13.6\" Retina",
            "price": 35999,
            "brand": "apple",
            "cpu": "M2",
            "gpu": "Apple M2 GPU",
            "gpu_norm": "Apple M2 GPU",
            "ram_gb": 8.0,
            "ssd_gb": 256.0,
            "screen_size": 13.6,
            "cpu_score": 8.2,
            "gpu_score": 7.5,
            "os": "macos",
            "url": "https://www.amazon.com.tr/dp/B0MAC",
        },
        {
            "name": "MSI Katana 15 i7-12700H 16GB 1TB SSD RTX 4070 15.6\" FHD 144Hz",
            "price": 55999,
            "brand": "msi",
            "cpu": "I7-12700H",
            "gpu": "RTX 4070",
            "gpu_norm": "GeForce RTX 4070",
            "ram_gb": 16.0,
            "ssd_gb": 1024.0,
            "screen_size": 15.6,
            "cpu_score": 7.5,
            "gpu_score": 8.8,
            "os": "freedos",
            "url": "https://www.incehesap.com/msi-katana",
        },
        {
            "name": "HP Pavilion 15 Ryzen 5 7530U 16GB 512GB SSD 15.6\" FHD",
            "price": 22999,
            "brand": "hp",
            "cpu": "Ryzen 5 7530U",
            "gpu": "Radeon Graphics",
            "gpu_norm": "Radeon Graphics (iGPU)",
            "ram_gb": 16.0,
            "ssd_gb": 512.0,
            "screen_size": 15.6,
            "cpu_score": 6.8,
            "gpu_score": 2.5,
            "os": "windows",
            "url": "https://www.vatanbilgisayar.com/hp-pavilion.html",
        },
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def base_preferences():
    """Minimal preference dict that every scoring / recommendation call needs."""
    return {
        "min_budget": 15000,
        "max_budget": 60000,
        "usage_key": "productivity",
        "usage_label": "Productivity",
    }


@pytest.fixture
def gaming_preferences():
    """Preferences for a gaming scenario."""
    return {
        "min_budget": 30000,
        "max_budget": 70000,
        "usage_key": "gaming",
        "usage_label": "Gaming",
        "min_gpu_score_required": 6.0,
        "gaming_min_gpu": 6.0,
    }


@pytest.fixture
def dev_web_preferences():
    """Preferences for a web-developer scenario."""
    return {
        "min_budget": 15000,
        "max_budget": 50000,
        "usage_key": "dev",
        "usage_label": "Dev",
        "dev_mode": "web",
    }


@pytest.fixture
def raw_csv_df():
    """DataFrame that mimics a raw CSV load (before clean_data)."""
    return pd.DataFrame({
        "name": [
            "ASUS TUF Gaming F15 i7-12700H 16GB RAM DDR5 512GB SSD RTX 4050 15.6\" FHD",
            "Lenovo IdeaPad 3 i5-1235U 8 GB RAM 256 GB SSD 15.6 inc",
            "Apple MacBook Air M2 8GB 256GB SSD 13.6 inch",
        ],
        "price": ["32.999 TL", "15999", 35999],
        "ram": ["16 GB DDR5", "8 GB", None],
        "ssd": ["512 GB SSD", "256GB", None],
        "screen_size": ['15.6"', None, "13.6 inch"],
        "url": [
            "https://www.amazon.com.tr/dp/B0ASUS",
            "https://www.vatanbilgisayar.com/lenovo.html",
            "https://www.amazon.com.tr/dp/B0MAC",
        ],
    })


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Provide a temporary directory for cache read/write tests."""
    return tmp_path
