from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"

SCRAPERS = {
    "amazon": BASE_DIR / "amazon_scraper.py",
    "incehesap": BASE_DIR / "incehesap_scraper.py",
    "vatan": BASE_DIR / "vatan_scraper.py",
}

DATA_FILES = [
    DATA_DIR / "amazon_laptops.csv",
    DATA_DIR / "vatan_laptops.csv",
    DATA_DIR / "incehesap_laptops.csv",
    DATA_DIR / "teknosa_laptops.csv",
]

CACHE_FILE = BASE_DIR / "laptop_cache.pkl"
ALL_DATA_FILE = DATA_DIR / "all_data.csv"
