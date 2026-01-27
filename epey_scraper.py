import argparse
import csv
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

OUTPUT_COLUMNS = [
    "source_url", "source_id", "name", "brand", "model",
    "price_min_try", "price_max_try", "currency", "tech_score",
    "cpu_model", "gpu_model", "ram_gb", "storage_gb", "storage_type",
    "screen_size_in", "screen_resolution", "os", "weight_kg",
    "scraped_at", "raw_text_signature"
]

# Mapping Turkish keys to canonical fields
FIELD_MAP = {
    "ram_gb": ["RAM", "Bellek", "Sistem Belleği", "Bellek (RAM)"],
    "cpu_model": ["İşlemci", "İşlemci Modeli", "İşlemci Serisi"],
    "gpu_model": ["Ekran Kartı", "Grafik İşlemci", "Harici Grafik İşlemcisi", "GPU"],
    "storage": ["Depolama", "Disk", "Sabit Disk", "SSD Kapasitesi", "HDD Kapasitesi"],
    "screen_size": ["Ekran Boyutu"],
    "resolution": ["Ekran Çözünürlüğü", "Çözünürlük"],
    "os": ["İşletim Sistemi", "Platform"],
    "weight": ["Ağırlık", "Cihaz Ağırlığı"],
    "brand": ["Marka"], # Sometimes explicit, often derived
    "tech_score": ["Puan", "Epey Puanı"]
}

# Global Stop Event for 403/429
STOP_EVENT = threading.Event()
FILE_LOCK = threading.Lock()

# =============================================================================
# UTILS: NORMALIZATION & PARSING
# =============================================================================

def clean_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return " ".join(text.strip().split())

def parse_turkish_float(text: str) -> Optional[float]:
    """Parses '26.614,94 TL' -> 26614.94"""
    if not text:
        return None
    try:
        # Remove non-numeric except . and ,
        clean = re.sub(r'[^\d.,]', '', text)
        if ',' in clean and '.' in clean:
            # Assumes 1.000,50 format
            clean = clean.replace('.', '').replace(',', '.')
        elif ',' in clean:
            # Assumes 1000,50 format
            clean = clean.replace(',', '.')
        return float(clean)
    except ValueError:
        return None

def extract_number(text: str) -> Optional[float]:
    """Extracts first float number from text e.g. '15.6 inç' -> 15.6"""
    if not text:
        return None
    match = re.search(r'(\d+[.,]?\d*)', text)
    if match:
        val = match.group(1).replace(',', '.')
        return float(val)
    return None

def parse_storage(text: str) -> (Optional[int], Optional[str]):
    """Returns (gb_int, type_str). e.g. '512 GB SSD' -> (512, 'SSD')"""
    if not text:
        return None, None
    
    text_upper = text.upper()
    gb = 0
    
    # Extract number
    num = extract_number(text)
    if num:
        if "TB" in text_upper:
            gb = int(num * 1024)
        else:
            gb = int(num)
            
    # Determine type
    s_type = "Unknown"
    if "SSD" in text_upper:
        s_type = "SSD"
    elif "HDD" in text_upper:
        s_type = "HDD"
    elif "NVME" in text_upper:
        s_type = "NVMe"
    elif "EMMC" in text_upper:
        s_type = "eMMC"
        
    return gb if gb > 0 else None, s_type

def get_canonical_id(url: str) -> str:
    """Derive ID from URL slug."""
    path = urlparse(url).path
    if path.endswith('.html'):
        return path.split('/')[-1].replace('.html', '')
    return path.strip('/').replace('/', '_')

def generate_signature(data_dict: Dict) -> str:
    """Generate short hash of critical data to detect changes."""
    s = json.dumps(data_dict, sort_keys=True)
    return hashlib.md5(s.encode('utf-8')).hexdigest()[:8]

# =============================================================================
# CLASSES
# =============================================================================

class StateManager:
    """Manages incremental crawling state."""
    def __init__(self, filepath: str, resume: bool):
        self.filepath = filepath
        self.data = {
            "visited_listings": [],
            "found_products": {}, # url: status (pending/done/error)
            "stats": {"pages": 0, "products": 0, "errors": 0}
        }
        if resume and os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logging.info(f"Resumed state: {len(self.data['found_products'])} products known.")
            except Exception as e:
                logging.error(f"Failed to load state: {e}. Starting fresh.")

    def add_listing_page(self, url):
        if url not in self.data["visited_listings"]:
            self.data["visited_listings"].append(url)

    def is_listing_visited(self, url):
        return url in self.data["visited_listings"]

    def add_product(self, url):
        if url not in self.data["found_products"]:
            self.data["found_products"][url] = "pending"

    def mark_product_done(self, url, status="done"):
        self.data["found_products"][url] = status
        if status == "done":
            self.data["stats"]["products"] += 1
        elif status == "error":
            self.data["stats"]["errors"] += 1

    def get_pending_products(self):
        return [u for u, s in self.data["found_products"].items() if s == "pending"]

    def save(self):
        with FILE_LOCK:
            tmp_path = self.filepath + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.filepath)

class HtmlCache:
    """Disk-based HTML caching."""
    def __init__(self, cache_dir: str, enabled: bool = True):
        self.cache_dir = cache_dir
        self.enabled = enabled
        if enabled:
            os.makedirs(cache_dir, exist_ok=True)

    def _get_path(self, url: str) -> str:
        h = hashlib.sha1(url.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f"{h}.html")

    def get(self, url: str) -> Optional[str]:
        if not self.enabled: 
            return None
        path = self._get_path(url)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                return None
        return None

    def save(self, url: str, html: str):
        if not self.enabled or not html: 
            return
        path = self._get_path(url)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)

class Fetcher:
    """Handles network requests, retries, and politeness."""
    def __init__(self, min_delay: float, max_delay: float, max_retries: int):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self._lock = threading.Lock()
        self._last_request_time = 0

    def _throttle(self):
        """Global throttle to ensure we don't spam even with threads."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            delay = random.uniform(self.min_delay, self.max_delay)
            if elapsed < delay:
                time.sleep(delay - elapsed)
            self._last_request_time = time.time()

    def get(self, url: str) -> Optional[str]:
        if STOP_EVENT.is_set():
            return None

        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                response = self.session.get(url, timeout=15)
                
                if response.status_code in [403, 429]:
                    logging.critical(f"Blocked (Status {response.status_code}) at {url}. Stopping scraper.")
                    STOP_EVENT.set()
                    return None
                
                if response.status_code != 200:
                    logging.warning(f"HTTP {response.status_code} for {url} (Attempt {attempt})")
                    time.sleep(attempt * 2) # Backoff
                    continue

                return response.text

            except requests.RequestException as e:
                logging.error(f"Network error {url}: {e}")
                time.sleep(attempt * 2)
        
        return None

class EpeyParser:
    """Parses Listing and Product pages."""
    
    @staticmethod
    def parse_listing(html: str, base_url: str) -> (List[str], Optional[str]):
        """Returns list of product URLs and next page URL."""
        soup = BeautifulSoup(html, 'lxml')
        product_urls = []
        
        # 1. Extract Products
        # Epey listing usually has links inside div.detay or li elements
        # Strategy: Look for any link containing /laptop/ that ends in .html
        # Avoiding listing pages like /laptop/2/
        
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            # Heuristic: Product pages usually end in .html, listings do not (or end in number)
            if '/laptop/' in href and href.endswith('.html'):
                full_url = urljoin(base_url, href)
                product_urls.append(full_url)
        
        # 2. Extract Pagination
        next_url = None
        # Look for "Sonraki" or "İleri" text or specific class
        next_btn = soup.find('a', string=re.compile(r'Sonraki|İleri', re.I))
        if not next_btn:
             # Try finding current page and next number
             pagination = soup.find('div', class_='sayfalama')
             if pagination:
                 current = pagination.find('a', class_='aktif')
                 if current:
                     next_sibling = current.find_next_sibling('a')
                     if next_sibling:
                         next_btn = next_sibling

        if next_btn and next_btn.has_attr('href'):
            next_url = urljoin(base_url, next_btn['href'])

        return list(set(product_urls)), next_url

    @staticmethod
    def parse_product(html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, 'lxml')
        
        record = {
            "source": "epey",
            "source_url": url,
            "source_id": get_canonical_id(url),
            "name": None,
            "brand": None,
            "model": None,
            "offers": [],
            "basic_specs": {},
            "full_specs": {},
            "scraped_at": datetime.now(timezone.utc).isoformat()
        }

        # --- Name ---
        h1 = soup.find('h1')
        if h1:
            record["name"] = clean_text(h1.get_text())
            # Simple brand extraction heuristic
            if record["name"]:
                record["brand"] = record["name"].split()[0]

        # --- Offers (Notebook Fiyatları) ---
        # Strategy: Look for the specific section. Epey often uses #fiyatlar
        fiyat_div = soup.find(id='fiyatlar')
        if fiyat_div:
            # Usually a list or table structure
            # We look for rows. Often <li> or <tr> inside
            rows = fiyat_div.find_all(lambda tag: tag.name in ['li', 'tr'] and ('fiyat' in tag.get('class', []) or 'cell' in tag.get('class', [])))
            
            if not rows:
                 # Fallback: scan for any element with 'fiyat' in text near 'TL'
                 pass # Too complex for reliable fallback, stick to ID/Class
            
            for row in rows:
                offer = {
                    "seller": None, 
                    "price_try": None, 
                    "price_text": None, 
                    "updated_rel": None,
                    "out_link": None
                }
                
                # Seller (often alt text of image or text in first cell)
                img = row.find('img')
                if img and img.get('alt'):
                    offer["seller"] = img.get('alt')
                else:
                    seller_div = row.find(class_='magaza')
                    if seller_div:
                        offer["seller"] = clean_text(seller_div.get_text())

                # Price
                price_container = row.find(class_='fiyat') or row.find('a', class_='urun_fiyat')
                if price_container:
                    raw_price = clean_text(price_container.get_text())
                    offer["price_text"] = raw_price
                    offer["price_try"] = parse_turkish_float(raw_price)
                    
                    # Link
                    if price_container.name == 'a':
                        offer["out_link"] = price_container.get('href')
                    elif price_container.find('a'):
                        offer["out_link"] = price_container.find('a').get('href')

                # Update info
                time_div = row.find(class_='zaman')
                if time_div:
                    offer["updated_rel"] = clean_text(time_div.get_text())

                if offer["price_try"]:
                    record["offers"].append(offer)

        # --- Specs ---
        
        # 1. Basic Specs (Temel Özellikleri) - Often #ozellikler .row
        basic_container = soup.find(id='oncelikli')
        if basic_container:
            for li in basic_container.find_all('div', class_='row'):
                spans = li.find_all('span') # key, value
                if len(spans) >= 2:
                    k = clean_text(spans[0].get_text()).rstrip(':')
                    v = clean_text(spans[1].get_text())
                    record["basic_specs"][k] = v
        
        # 2. Full Specs (Tüm Özellikler / Kategorize)
        # Epey structure: #tum_ozellikler -> div.baslik (Category) -> ul -> li (Key: Value)
        full_container = soup.find(id='tum_ozellikler')
        if not full_container:
            full_container = soup.find(id='ozellikler') # Fallback
            
        if full_container:
            current_category = "General"
            # Loop through elements to handle H3 (Cat) then UL (Items) sequence
            for child in full_container.children:
                if child.name in ['h3', 'h4', 'div'] and ('baslik' in child.get('class', []) or 'kategori' in str(child.get('class', []))):
                    current_category = clean_text(child.get_text())
                elif child.name in ['ul', 'table']:
                    if current_category not in record["full_specs"]:
                        record["full_specs"][current_category] = {}
                    
                    items = child.find_all(['li', 'tr'])
                    for item in items:
                        # Logic to split key/value
                        # Often <span>Key</span> <span>Value</span> or text
                        cols = item.find_all(['span', 'td', 'div'])
                        if len(cols) >= 2:
                             # robust cleanup to avoid empty keys
                             k = clean_text(cols[0].get_text()).rstrip(':')
                             v = clean_text(cols[1].get_text())
                             if k:
                                record["full_specs"][current_category][k] = v

        return record

    @staticmethod
    def normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert extracted strings to canonical types."""
        
        # Combine basic and flattened full specs for searching
        all_specs = record["basic_specs"].copy()
        for cat, specs in record["full_specs"].items():
            all_specs.update(specs)
            
        def find_val(keys):
            for k in keys:
                # Direct match
                if k in all_specs: return all_specs[k]
                # Partial key match (slower but robust)
                for spec_k, spec_v in all_specs.items():
                    if k.lower() == spec_k.lower():
                        return spec_v
            return None

        # Price stats
        prices = [o["price_try"] for o in record["offers"] if o["price_try"]]
        if prices:
            record["price_min_try"] = min(prices)
            record["price_max_try"] = max(prices)
            record["currency"] = "TRY"
        else:
            record["price_min_try"] = None
            record["price_max_try"] = None

        # Tech Score
        score_val = find_val(FIELD_MAP["tech_score"])
        record["tech_score"] = float(score_val) if score_val and score_val.replace('.','').isdigit() else None

        # Hardware Specs
        record["cpu_model"] = find_val(FIELD_MAP["cpu_model"])
        record["gpu_model"] = find_val(FIELD_MAP["gpu_model"])
        
        ram_txt = find_val(FIELD_MAP["ram_gb"])
        record["ram_gb"] = int(extract_number(ram_txt)) if extract_number(ram_txt) else None
        
        storage_txt = find_val(FIELD_MAP["storage"])
        s_gb, s_type = parse_storage(storage_txt)
        record["storage_gb"] = s_gb
        record["storage_type"] = s_type
        
        screen_txt = find_val(FIELD_MAP["screen_size"])
        record["screen_size_in"] = extract_number(screen_txt)
        
        record["screen_resolution"] = find_val(FIELD_MAP["resolution"])
        record["os"] = find_val(FIELD_MAP["os"])
        
        w_txt = find_val(FIELD_MAP["weight"])
        record["weight_kg"] = extract_number(w_txt)

        # Signature
        record["raw_text_signature"] = generate_signature(all_specs)

        return record

# =============================================================================
# MAIN LOGIC
# =============================================================================

def process_product(url: str, fetcher: Fetcher, cache: HtmlCache, state: StateManager, writer_lock: threading.Lock, jsonl_path: str):
    if STOP_EVENT.is_set():
        return

    # 1. Check Cache
    html = cache.get(url)
    from_cache = True
    
    # 2. Fetch if missing
    if not html:
        from_cache = False
        html = fetcher.get(url)
        if html:
            cache.save(url, html)
    
    if not html:
        logging.warning(f"Failed to get content for {url}")
        state.mark_product_done(url, "error")
        return

    # 3. Parse
    try:
        raw_record = EpeyParser.parse_product(html, url)
        clean_record = EpeyParser.normalize_record(raw_record)
        
        # 4. Write
        json_line = json.dumps(clean_record, ensure_ascii=False)
        with writer_lock:
            with open(jsonl_path, 'a', encoding='utf-8') as f:
                f.write(json_line + "\n")
        
        state.mark_product_done(url, "done")
        
        status = "Cached" if from_cache else "Downloaded"
        logging.info(f"[{status}] Parsed: {clean_record.get('name', 'Unknown')[:30]}...")

    except Exception as e:
        logging.error(f"Error parsing {url}: {e}")
        state.mark_product_done(url, "error")

def generate_csv_from_jsonl(jsonl_path: str, csv_path: str):
    """Safely converts JSONL to CSV at the end."""
    if not os.path.exists(jsonl_path):
        logging.warning("No JSONL file found, skipping CSV generation.")
        return

    logging.info("Generating CSV from JSONL...")
    try:
        # First pass to verify validity
        valid_rows = []
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    valid_rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        if not valid_rows:
            logging.warning("No valid records found.")
            return

        # Write CSV
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(valid_rows)
        logging.info(f"CSV saved to {csv_path} ({len(valid_rows)} rows)")

    except Exception as e:
        logging.error(f"Failed to generate CSV: {e}")

def main():
    parser = argparse.ArgumentParser(description="Epey Laptop Scraper")
    parser.add_argument("--start-url", action='append', default=[], help="Listing page URL(s)")
    parser.add_argument("--max-pages", type=int, default=50, help="Max listing pages per seed")
    parser.add_argument("--workers", type=int, default=4, help="Concurrency level")
    parser.add_argument("--time-budget", type=int, default=2700, help="Max execution time (seconds)")
    parser.add_argument("--out-jsonl", default="out/epey_products.jsonl")
    parser.add_argument("--out-csv", default="out/epey_laptops.csv")
    parser.add_argument("--cache-dir", default="cache_html")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh")
    parser.add_argument("--min-delay", type=float, default=1.5)
    parser.add_argument("--max-delay", type=float, default=3.0)
    parser.add_argument("--max-retries", type=int, default=3)
    
    args = parser.parse_args()

    # Logging Setup
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Defaults
    if not args.start_url:
        args.start_url = ["https://www.epey.com/laptop/"]
    
    # Directories
    os.makedirs(os.path.dirname(args.out_jsonl), exist_ok=True)
    
    # Init Components
    state_file = "state.json"
    if args.no_resume and os.path.exists(state_file):
        os.remove(state_file)
        if os.path.exists(args.out_jsonl): os.remove(args.out_jsonl)
    
    state = StateManager(state_file, not args.no_resume)
    cache = HtmlCache(args.cache_dir, not args.no_cache)
    fetcher = Fetcher(args.min_delay, args.max_delay, args.max_retries)
    
    start_time = time.time()
    
    print("=== EPEY SCRAPER STARTED ===")
    print(f"Seeds: {args.start_url}")
    print(f"Workers: {args.workers} | Time Budget: {args.time_budget}s")

    # PHASE 1: Crawl Listings
    logging.info("--- PHASE 1: DISCOVERING PRODUCTS ---")
    
    for seed in args.start_url:
        current_url = seed
        pages_crawled = 0
        
        while current_url and pages_crawled < args.max_pages:
            if time.time() - start_time > args.time_budget:
                logging.info("Time budget exceeded during listing crawl.")
                break
            
            if STOP_EVENT.is_set():
                break

            if state.is_listing_visited(current_url):
                logging.info(f"Skipping visited listing: {current_url}")
                # We can't easily guess the next URL if we skip, 
                # but typically resume handles products, so we might re-parse listing to find next.
                # For robustness, we re-download listing to check for new products or next page, 
                # but respect cache.
                pass 

            logging.info(f"Fetching listing: {current_url}")
            html = fetcher.get(current_url)
            
            if not html:
                logging.warning(f"Could not fetch listing {current_url}")
                break
                
            prod_urls, next_page = EpeyParser.parse_listing(html, current_url)
            
            new_count = 0
            for p_url in prod_urls:
                if p_url not in state.data["found_products"]:
                    state.add_product(p_url)
                    new_count += 1
            
            state.add_listing_page(current_url)
            state.save()
            
            logging.info(f"Page {pages_crawled+1}: Found {len(prod_urls)} products ({new_count} new). Next: {next_page}")
            
            current_url = next_page
            pages_crawled += 1

    # PHASE 2: Crawl Products
    logging.info("--- PHASE 2: PROCESSING PRODUCTS ---")
    
    pending_urls = state.get_pending_products()
    logging.info(f"Total products to process: {len(pending_urls)}")
    
    writer_lock = threading.Lock()
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = []
        for url in pending_urls:
            if time.time() - start_time > args.time_budget:
                logging.warning("Time budget exceeded. Stopping pool submission.")
                break
            if STOP_EVENT.is_set():
                break
                
            futures.append(
                executor.submit(process_product, url, fetcher, cache, state, writer_lock, args.out_jsonl)
            )
        
        # Monitor Loop
        completed = 0
        for f in as_completed(futures):
            completed += 1
            if completed % 10 == 0:
                state.save()
                elapsed = time.time() - start_time
                logging.info(f"Progress: {completed}/{len(pending_urls)} | Elapsed: {int(elapsed)}s")
            
            if STOP_EVENT.is_set():
                logging.critical("Stopping threads due to block.")
                executor.shutdown(wait=False, cancel_futures=True)
                break

    state.save()
    
    # PHASE 3: CSV Generation
    generate_csv_from_jsonl(args.out_jsonl, args.out_csv)
    
    logging.info("=== DONE ===")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Interrupted by user.")
        sys.exit(0)