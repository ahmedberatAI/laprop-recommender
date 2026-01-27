from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]

SCRAPERS = {
    "amazon": BASE_DIR / "amazon_scraper.py",
    "incehesap": BASE_DIR / "incehesap_scraper.py",
    "vatan": BASE_DIR / "vatan_scraper.py",
}

DATA_FILES = [
    BASE_DIR / "amazon_laptops.csv",
    BASE_DIR / "vatan_laptops.csv",
    BASE_DIR / "incehesap_laptops.csv",
]

CACHE_FILE = BASE_DIR / "laptop_cache.pkl"
ALL_DATA_FILE = BASE_DIR / "all_data.csv"
