# incehesap_scraper.py
# Python 3.10+
# pip install requests beautifulsoup4 lxml

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


# =========================
# Ayarlar
# =========================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}

PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)\s*TL", re.IGNORECASE)
GB_TB_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(TB|GB)", re.IGNORECASE)
INCH_RE = re.compile(r"(\d{1,2}(?:[.,]\d)?)\s*(?:\"|inÃ§|inch)", re.IGNORECASE)

# ÃœrÃ¼n URL'leri genelde "...-fiyati-80155/" gibi bitiyor
PRODUCT_URL_RE = re.compile(r"-fiyati-\d+/?$")

# Detay sayfasÄ±ndaki "Ã–zellikleri" bÃ¶lÃ¼mÃ¼nde gÃ¶rdÃ¼ÄŸÃ¼mÃ¼z anahtarlar
KEYS_WANTED = {
    "ekran_size": ["Ekran Ã–zelliÄŸi", "Ekran Boyutu", "Ekran"],
    "cpu": ["Ä°ÅŸlemci Modeli", "Ä°ÅŸlemci"],
    "ram": ["Sistem BelleÄŸi", "RAM", "Bellek"],
    "gpu": ["Ekran KartÄ±", "Grafik KartÄ±"],
    "os": ["Ä°ÅŸletim Sistemi"],
    "ssd": ["SSD", "Kapasite", "Depolama", "SSD Kapasitesi"],
}

GPU_INTEGRATED_HINTS = [
    "iris", "uhd", "hd graphics", "intel", "radeon graphics", "adreno"
]

CSV_COLUMNS = ["url", "name", "price", "screen_size", "ssd", "cpu", "ram", "os", "gpu"]
DEFAULT_MAIN_CSV = "data/incehesap_laptops.csv"
DEFAULT_RAW_CSV = "data/incehesap_laptops_raw.csv"
DEFAULT_FIXED_CSV = "data/incehesap_laptops_fixed.csv"
DEFAULT_REPORT_JSON = "data/incehesap_fix_report.json"

# =========================
# Fix pipeline constants
# =========================

COMMON_SSD_CAPS = {128, 256, 512, 1024, 2048, 3072, 4096}
ALLOWED_RAM = {4, 8, 12, 16, 24, 32, 40, 48, 64, 96, 128, 192}

TR_CHAR_MAP = str.maketrans(
    {
        "\u0130": "I",
        "\u0131": "i",
        "\u015e": "S",
        "\u015f": "s",
        "\u011e": "G",
        "\u011f": "g",
        "\u00dc": "U",
        "\u00fc": "u",
        "\u00d6": "O",
        "\u00f6": "o",
        "\u00c7": "C",
        "\u00e7": "c",
    }
)

CAPACITY_RE = re.compile(r"(?<!\d)(\d{1,4}(?:[.,]\d+)?)\s*(tb|gb)\b", re.IGNORECASE)
SSD_NO_UNIT_RE = re.compile(
    r"(?<!\d)(\d{3,4})\s*(?:gb)?\s*(ssd|nvme|m\.2|m2|pcie|pci-e)\b",
    re.IGNORECASE,
)
RAM_MULT_RE = re.compile(r"(?<!\d)(\d{1,3})\s*[xÃ—]\s*(\d{1,3})\s*gb\b", re.IGNORECASE)
RAM_RE = re.compile(r"(?<!\d)(\d{1,3})\s*gb\b", re.IGNORECASE)

SSD_POS_RE = re.compile(r"\b(?:ssd|nvme|m\.2|m2|pcie|pci-e)\b", re.IGNORECASE)
SSD_WEAK_RE = re.compile(r"\b(?:depolama|storage|disk|dahili)\b", re.IGNORECASE)
SSD_NEG_RE = re.compile(r"\b(?:hdd|sata)\b", re.IGNORECASE)
RAM_HINT_RE = re.compile(r"\b(?:ram|lpddr\d*|ddr\d*)\b", re.IGNORECASE)
GPU_HINT_RE = re.compile(
    r"\b(?:rtx|gtx|gddr\d*|vram|geforce|radeon|arc|mx\d{2,3})\b",
    re.IGNORECASE,
)
STORAGE_HINT_RE = re.compile(
    r"\b(?:ssd|nvme|hdd|m\.2|m2|pcie|pci-e|depolama|storage|disk)\b",
    re.IGNORECASE,
)

INTEL_MODEL_RE = re.compile(r"\b(i[3579])[-\s]?(\d{4,5}[a-z]{0,2})\b", re.IGNORECASE)
INTEL_GENERIC_RE = re.compile(r"\b(i[3579])\b", re.IGNORECASE)
ULTRA_MODEL_RE = re.compile(
    r"\b(?:core\s*)?ultra\s*([579])\s*[-\s]?(\d{3,5}[a-z]{0,2})\b",
    re.IGNORECASE,
)
ULTRA_SHORT_RE = re.compile(r"\bu([579])[-\s]?(\d{3,5}[a-z]{0,2})\b", re.IGNORECASE)
ULTRA_GENERIC_RE = re.compile(r"\b(?:core\s*)?ultra\s*([579])\b", re.IGNORECASE)
RYZEN_MODEL_RE = re.compile(r"\bryzen\s*([3579])\s*(\d{4,5}[a-z]{0,2})\b", re.IGNORECASE)
RYZEN_SHORT_RE = re.compile(r"\br([3579])\s*[-\s]?(\d{4,5}[a-z]{0,2})\b", re.IGNORECASE)
RYZEN_GENERIC_RE = re.compile(r"\bryzen\s*([3579])\b", re.IGNORECASE)

RTX_RE = re.compile(r"\brtx\s*[-\s]?(\d{3,4})\s*(ti)?\b", re.IGNORECASE)
GTX_RE = re.compile(r"\bgtx\s*[-\s]?(\d{3,4})\s*(ti)?\b", re.IGNORECASE)
RX_RE = re.compile(r"\brx\s*[-\s]?(\d{3,4}[a-z]?)\b", re.IGNORECASE)
ARC_RE = re.compile(r"\barc\s*([a-z]?\d{3,4})\b", re.IGNORECASE)
MX_RE = re.compile(r"\bmx\s*[-\s]?(\d{2,3})\b", re.IGNORECASE)

INTEGRATED_HINTS = [
    "iris",
    "uhd",
    "hd graphics",
    "integrated",
    "radeon graphics",
    "vega",
]


def canonicalize_url(url: str) -> str:
    """Query paramlarÄ± (srsltid vb.) temizle, sadece path bÄ±rak."""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def ensure_dataframe(rows_or_df: Union[pd.DataFrame, List[Dict[str, object]]]) -> pd.DataFrame:
    if isinstance(rows_or_df, pd.DataFrame):
        return rows_or_df.copy()
    return pd.DataFrame(rows_or_df)


def write_rows_csv(
    rows_or_df: Union[pd.DataFrame, List[Dict[str, object]]], path: str
) -> int:
    df = ensure_dataframe(rows_or_df)
    df = df.reindex(columns=CSV_COLUMNS)
    safe_mkdir(os.path.dirname(path) or ".")
    df.to_csv(path, index=False)
    print(f"[OK] wrote: {path} (rows={len(df)})")
    return len(df)


def slug_id_from_url(url: str) -> str:
    # "...-fiyati-80155/" -> "80155"
    m = re.search(r"-fiyati-(\d+)/?$", url)
    return m.group(1) if m else hashlib.md5(url.encode("utf-8")).hexdigest()[:10]


def parse_price_to_float(price_str: str) -> Optional[float]:
    """
    '31.599 TL' -> 31599.0
    '24.509 TL' -> 24509.0
    """
    m = PRICE_RE.search(price_str)
    if not m:
        return None
    s = m.group(1).strip()
    # TR format: . binlik, , ondalÄ±k
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def normalize_gb_tb(text: str) -> Optional[str]:
    m = GB_TB_RE.search(text)
    if not m:
        return None
    num = m.group(1).replace(",", ".")
    unit = m.group(2).upper()
    # 1.0 TB gibi yazÄ±mlarÄ± sadeleÅŸtir
    if unit == "TB":
        try:
            f = float(num)
            if abs(f - round(f)) < 1e-9:
                num = str(int(round(f)))
        except Exception:
            pass
        return f"{num}TB"
    else:
        try:
            f = float(num)
            if abs(f - round(f)) < 1e-9:
                num = str(int(round(f)))
        except Exception:
            pass
        return f"{num}GB"


def normalize_screen_size(text: str) -> Optional[str]:
    m = INCH_RE.search(text)
    if not m:
        return None
    val = m.group(1).replace(",", ".")
    return f'{val}"'


def guess_integrated_gpu(gpu_text: str) -> str:
    t = gpu_text.lower()
    if any(h in t for h in GPU_INTEGRATED_HINTS):
        return "integrated"
    return gpu_text.strip()


@dataclass
class ScrapeConfig:
    base_categories: List[str]
    max_pages: int = 5
    sleep_range: Tuple[float, float] = (0.8, 1.6)  # nazik scraping
    timeout: int = 25
    retries: int = 3
    raw_dir: str = "raw/incehesap_html"
    out_csv: str = DEFAULT_MAIN_CSV
    workers: int = 6  # requests iÃ§in thread ile kullanÄ±labilir ama basit tuttum


class InceHesapScraper:
    def __init__(self, cfg: ScrapeConfig):
        self.cfg = cfg
        self.sess = requests.Session()
        self.sess.headers.update(DEFAULT_HEADERS)

        safe_mkdir(self.cfg.raw_dir)
        safe_mkdir(os.path.dirname(self.cfg.out_csv) or ".")

        self.raw_list_dir = os.path.join(self.cfg.raw_dir, "list")
        self.raw_prod_dir = os.path.join(self.cfg.raw_dir, "product")
        safe_mkdir(self.raw_list_dir)
        safe_mkdir(self.raw_prod_dir)
        self.last_collected_urls = 0
        self.last_scraped_pages = 0

    def _polite_sleep(self) -> None:
        a, b = self.cfg.sleep_range
        time.sleep(random.uniform(a, b))

    def fetch_html(self, url: str) -> Optional[str]:
        last_err = None
        for attempt in range(1, self.cfg.retries + 1):
            try:
                r = self.sess.get(url, timeout=self.cfg.timeout)
                if r.status_code in (429, 503):
                    # rate-limit / temporary
                    wait = 2.0 * attempt
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.text
            except Exception as e:
                last_err = e
                time.sleep(0.8 * attempt)
        print(f"[fetch_html] FAILED url={url} err={last_err}")
        return None

    def save_raw(self, html: str, folder: str, name: str) -> None:
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def build_list_url(self, category_base: str, page: int) -> str:
        base = category_base if category_base.endswith("/") else category_base + "/"
        if page == 1:
            return base
        return urljoin(base, f"sayfa-{page}/")

    def extract_product_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        urls: List[str] = []
        for a in soup.select("a[href]"):
            href = a.get("href", "").strip()
            if not href:
                continue
            full = urljoin(base_url, href)
            full = canonicalize_url(full)
            if "incehesap.com" not in full:
                continue
            if PRODUCT_URL_RE.search(full):
                urls.append(full)
        # dedupe preserve order
        seen = set()
        out = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def parse_list_page_minimal(self, html: str, page_url: str) -> Dict[str, Dict]:
        """
        Liste sayfasÄ±ndan:
        - url
        - name (kart baÅŸlÄ±ÄŸÄ±)
        - price (kart iÃ§indeki TL)
        gibi minimal alanlarÄ± yakalamaya Ã§alÄ±ÅŸÄ±r.
        """
        soup = BeautifulSoup(html, "lxml")
        product_urls = self.extract_product_links(soup, page_url)

        out: Dict[str, Dict] = {}
        for u in product_urls:
            out[u] = {"url": u}

        # Ä°yileÅŸtirme: link etrafÄ±ndaki container'dan name/price yakala
        for a in soup.select("a[href]"):
            href = a.get("href", "").strip()
            if not href:
                continue
            full = canonicalize_url(urljoin(page_url, href))
            if full not in out:
                continue

            name = " ".join(a.get_text(" ", strip=True).split())
            if name and len(name) > 5:
                out[full]["name"] = name

            # parent zincirinde fiyat ara
            parent = a
            for _ in range(6):
                if parent is None:
                    break
                text = " ".join(parent.get_text(" ", strip=True).split())
                pr = parse_price_to_float(text)
                if pr is not None:
                    out[full]["price"] = pr
                    break
                parent = parent.parent

        return out

    def parse_detail_specs(self, html: str) -> Dict[str, str]:
        """
        Detay sayfasÄ±ndaki specs'i key->value dict olarak toplamaya Ã§alÄ±ÅŸÄ±r.
        1) table tr (th/td veya td/td)
        2) dl dt/dd
        3) fallback: metin satÄ±rlarÄ±nda "Key Value"
        """
        soup = BeautifulSoup(html, "lxml")
        specs: Dict[str, str] = {}

        # --- 1) TABLE ---
        for table in soup.select("table"):
            rows = table.select("tr")
            for tr in rows:
                cells = tr.find_all(["th", "td"])
                if len(cells) >= 2:
                    k = " ".join(cells[0].get_text(" ", strip=True).split())
                    v = " ".join(cells[1].get_text(" ", strip=True).split())
                    if k and v and len(k) <= 80:
                        specs.setdefault(k, v)

        # --- 2) DL ---
        for dl in soup.select("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            if len(dts) == len(dds) and len(dts) > 0:
                for dt, dd in zip(dts, dds):
                    k = " ".join(dt.get_text(" ", strip=True).split())
                    v = " ".join(dd.get_text(" ", strip=True).split())
                    if k and v and len(k) <= 80:
                        specs.setdefault(k, v)

        # --- 3) FALLBACK TEXT ---
        text = soup.get_text("\n", strip=True)
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        # "Notebook Ã–zellikleri" sonrasÄ±nÄ± yakalamaya Ã§alÄ±ÅŸ
        start_idx = 0
        for i, ln in enumerate(lines):
            if "Ã–zellikleri" in ln and "Notebook" in ln:
                start_idx = i
                break
        tail = lines[start_idx:start_idx + 200]  # Ã§ok uzamasÄ±n

        # "Ekran Ã–zelliÄŸi 15.6\"" gibi satÄ±rlarÄ± split et
        # Basit heuristic: bilinen anahtarlar satÄ±r baÅŸÄ±nda geÃ§iyorsa al
        for ln in tail:
            for group in KEYS_WANTED.values():
                for keyname in group:
                    if ln.startswith(keyname + " "):
                        val = ln[len(keyname):].strip()
                        if val:
                            specs.setdefault(keyname, val)

        return specs

    def parse_detail_page(self, url: str, html: str, list_hint: Optional[Dict] = None) -> Dict:
        soup = BeautifulSoup(html, "lxml")

        # name
        h1 = soup.find("h1")
        name = " ".join(h1.get_text(" ", strip=True).split()) if h1 else None
        if not name and list_hint:
            name = list_hint.get("name")

        # price: detay sayfada bulunamazsa list_hint'ten gelsin
        price = None
        if list_hint and isinstance(list_hint.get("price"), (int, float)):
            price = float(list_hint["price"])

        # Yine de detay sayfada TL arayalÄ±m (bazÄ± Ã¼rÃ¼nlerde var)
        if price is None:
            t = soup.get_text(" ", strip=True)
            price = parse_price_to_float(t)

        specs = self.parse_detail_specs(html)

        def pick(keys: List[str]) -> Optional[str]:
            for k in keys:
                if k in specs:
                    return specs[k]
            return None

        screen_raw = pick(KEYS_WANTED["ekran_size"]) or (name or "")
        cpu_raw = pick(KEYS_WANTED["cpu"]) or (name or "")
        ram_raw = pick(KEYS_WANTED["ram"]) or (name or "")
        gpu_raw = pick(KEYS_WANTED["gpu"]) or (name or "")
        os_raw = pick(KEYS_WANTED["os"]) or (name or "")
        ssd_raw = pick(KEYS_WANTED["ssd"]) or (name or "")

        screen_size = normalize_screen_size(screen_raw)
        ram = normalize_gb_tb(ram_raw)
        ssd = normalize_gb_tb(ssd_raw)
        cpu = cpu_raw.strip() if isinstance(cpu_raw, str) else None
        os_name = os_raw.strip() if isinstance(os_raw, str) else None
        gpu = gpu_raw.strip() if isinstance(gpu_raw, str) else None
        gpu_norm = guess_integrated_gpu(gpu) if gpu else None

        row = {
            "url": url,
            "name": name,
            "price": price,
            "screen_size": screen_size,
            "ssd": ssd,
            "cpu": cpu,
            "ram": ram,
            "os": os_name,
            "gpu": gpu_norm,
        }
        return row

    def crawl(self) -> List[Dict]:
        # 1) Listelerden URL + price hint topla
        url2hint: Dict[str, Dict] = {}

        for cat in self.cfg.base_categories:
            for page in range(1, self.cfg.max_pages + 1):
                list_url = self.build_list_url(cat, page)
                print(f"[LIST] {list_url}")
                html = self.fetch_html(list_url)
                if not html:
                    break
                self.save_raw(html, self.raw_list_dir, f"{slug_id_from_url(list_url)}.html")

                hints = self.parse_list_page_minimal(html, list_url)

                # sayfada hiÃ§ Ã¼rÃ¼n yoksa dur
                if not hints:
                    break

                # merge
                for u, h in hints.items():
                    url2hint.setdefault(u, {}).update(h)

                self._polite_sleep()

        # 2) Detay sayfalarÄ±
        results: List[Dict] = []
        all_urls = list(url2hint.keys())
        self.last_collected_urls = len(all_urls)
        print(f"[INFO] total product urls collected: {self.last_collected_urls}")

        for i, u in enumerate(all_urls, 1):
            print(f"[DETAIL {i}/{len(all_urls)}] {u}")
            html = self.fetch_html(u)
            if not html:
                continue
            self.save_raw(html, self.raw_prod_dir, f"{slug_id_from_url(u)}.html")

            row = self.parse_detail_page(u, html, list_hint=url2hint.get(u))
            results.append(row)

            self._polite_sleep()

        self.last_scraped_pages = len(results)
        return results

    def write_csv(
        self,
        rows_or_df: Union[pd.DataFrame, List[Dict[str, object]]],
        path: Optional[str] = None,
    ) -> None:
        out_path = path or self.cfg.out_csv
        write_rows_csv(rows_or_df, out_path)


# =========================
# Fix pipeline helpers
# =========================


def normalize_text_for_match(text: Optional[str]) -> str:
    if text is None:
        return ""
    s = str(text)
    s = s.translate(TR_CHAR_MAP)
    s = s.replace("\u2033", '"').replace("\u201d", '"').replace("\u201c", '"')
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s


def coerce_int(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, int):
        return int(value)
    s = str(value).strip()
    if not s:
        return None
    m = re.search(r"\d+", s)
    if not m:
        return None
    try:
        return int(float(m.group(0)))
    except ValueError:
        return None


def coerce_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", ".")
    if not s:
        return None
    m = re.search(r"\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def capacity_to_gb(num_str: str, unit: str) -> Optional[int]:
    try:
        value = float(num_str.replace(",", "."))
    except ValueError:
        return None
    if unit.lower() == "tb":
        value *= 1024
    if abs(value - round(value)) < 1e-6:
        value = round(value)
    return int(value)


def window_text(text: str, start: int, end: int, span: int = 24) -> str:
    left = max(0, start - span)
    right = min(len(text), end + span)
    return text[left:right]


def extract_ssd_capacity(name: Optional[str]) -> Tuple[Optional[int], int, Optional[str]]:
    text = normalize_text_for_match(name)
    if not text:
        return None, 0, None
    candidates: List[Tuple[int, int, str]] = []

    for m in CAPACITY_RE.finditer(text):
        value = capacity_to_gb(m.group(1), m.group(2))
        if value is None or value in (2242, 2280):
            continue
        if value < 64 or value > 8192:
            continue
        window = window_text(text, m.start(), m.end())
        score = 0
        if SSD_POS_RE.search(window):
            score += 3
        if SSD_WEAK_RE.search(window):
            score += 1
        if SSD_NEG_RE.search(window):
            score -= 2
        if RAM_HINT_RE.search(window):
            score -= 3
        if GPU_HINT_RE.search(window):
            score -= 2
        if value in COMMON_SSD_CAPS:
            score += 2
        if m.group(2).lower() == "tb":
            score += 1
        candidates.append((score, value, m.group(0)))

    for m in SSD_NO_UNIT_RE.finditer(text):
        value = int(m.group(1))
        if value not in COMMON_SSD_CAPS:
            continue
        window = window_text(text, m.start(), m.end())
        score = 4
        if SSD_NEG_RE.search(window):
            score -= 2
        if RAM_HINT_RE.search(window):
            score -= 3
        if GPU_HINT_RE.search(window):
            score -= 2
        candidates.append((score, value, m.group(0)))

    if not candidates:
        return None, 0, None
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    score, value, raw = candidates[0]
    if score < 2:
        return None, score, raw
    return value, score, raw


def extract_ram_gb(name: Optional[str]) -> Tuple[Optional[int], int, Optional[str]]:
    text = normalize_text_for_match(name)
    if not text:
        return None, 0, None
    candidates: List[Tuple[int, int, str]] = []

    for m in RAM_MULT_RE.finditer(text):
        total = int(m.group(1)) * int(m.group(2))
        window = window_text(text, m.start(), m.end())
        score = 4
        if RAM_HINT_RE.search(window):
            score += 2
        if STORAGE_HINT_RE.search(window):
            score -= 3
        if GPU_HINT_RE.search(window):
            score -= 3
        if total in ALLOWED_RAM:
            score += 2
        elif 4 <= total <= 256:
            score += 1
        candidates.append((score, total, m.group(0)))

    for m in RAM_RE.finditer(text):
        value = int(m.group(1))
        window = window_text(text, m.start(), m.end())
        score = 0
        if RAM_HINT_RE.search(window):
            score += 4
        if STORAGE_HINT_RE.search(window):
            score -= 3
        if GPU_HINT_RE.search(window):
            score -= 3
        if value in ALLOWED_RAM:
            score += 2
        elif 4 <= value <= 256:
            score += 1
        else:
            score -= 3
        candidates.append((score, value, m.group(0)))

    if not candidates:
        return None, 0, None
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    score, value, raw = candidates[0]
    if score < 2:
        return None, score, raw
    return value, score, raw


def extract_cpu_from_text(text: Optional[str]) -> Tuple[Optional[str], int]:
    norm = normalize_text_for_match(text)
    if not norm:
        return None, 0

    m = ULTRA_MODEL_RE.search(norm)
    if m:
        return f"ultra{m.group(1)}-{m.group(2).lower()}", 4
    m = ULTRA_SHORT_RE.search(norm)
    if m:
        return f"ultra{m.group(1)}-{m.group(2).lower()}", 4
    m = INTEL_MODEL_RE.search(norm)
    if m:
        return f"{m.group(1).lower()}-{m.group(2).lower()}", 4
    m = RYZEN_MODEL_RE.search(norm)
    if m:
        return f"ryzen {m.group(1)} {m.group(2).lower()}", 4
    m = RYZEN_SHORT_RE.search(norm)
    if m:
        return f"ryzen {m.group(1)} {m.group(2).lower()}", 4
    m = ULTRA_GENERIC_RE.search(norm)
    if m:
        return f"ultra{m.group(1)}", 2
    m = INTEL_GENERIC_RE.search(norm)
    if m:
        return m.group(1).lower(), 2
    m = RYZEN_GENERIC_RE.search(norm)
    if m:
        return f"ryzen {m.group(1)}", 2
    return None, 0


def normalize_cpu_value(text: Optional[str]) -> Optional[str]:
    parsed, _ = extract_cpu_from_text(text)
    if parsed:
        return parsed
    norm = normalize_text_for_match(text).strip()
    return norm or None


def is_cpu_generic(cpu: Optional[str]) -> bool:
    if not cpu:
        return True
    return bool(re.fullmatch(r"i[3579]|ryzen [3579]|ultra[579]", cpu))


def extract_gpu_from_text(text: Optional[str]) -> Tuple[Optional[str], int, Optional[str]]:
    norm = normalize_text_for_match(text)
    if not norm:
        return None, 0, None

    m = RTX_RE.search(norm)
    if m:
        suffix = " ti" if m.group(2) else ""
        return f"rtx {m.group(1)}{suffix}", 4, None
    m = GTX_RE.search(norm)
    if m:
        num = int(m.group(1))
        suffix = " ti" if m.group(2) else ""
        if num >= 5000:
            return f"rtx {num}{suffix}", 3, "corrected_gtx_to_rtx"
        return f"gtx {num}{suffix}", 3, None
    m = RX_RE.search(norm)
    if m:
        return f"rx {m.group(1)}", 3, None
    m = ARC_RE.search(norm)
    if m:
        return f"arc {m.group(1)}", 2, None
    m = MX_RE.search(norm)
    if m:
        return f"mx {m.group(1)}", 2, None
    if any(hint in norm for hint in INTEGRATED_HINTS):
        return "integrated", 1, None
    return None, 0, None


def is_missing_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def is_valid_price(value: object) -> bool:
    num = coerce_float(value)
    return num is not None and 1000 <= num <= 500000


def is_valid_screen_size(value: object) -> bool:
    num = coerce_float(value)
    return num is not None and 10 <= num <= 20


def is_valid_ram(value: object) -> bool:
    num = coerce_int(value)
    return num is not None and 4 <= num <= 256


def is_valid_ssd(value: object) -> bool:
    num = coerce_int(value)
    return num is not None and 64 <= num <= 8192 and num not in (2242, 2280)


def is_valid_cpu(value: object) -> bool:
    if is_missing_value(value):
        return False
    return str(value).strip().lower() != "unknown"


def is_valid_gpu(value: object) -> bool:
    if is_missing_value(value):
        return False
    return str(value).strip().lower() != "unknown"


def print_missing_invalid_table(df: pd.DataFrame, label: str) -> Dict[str, Dict[str, int]]:
    validators = {
        "price": is_valid_price,
        "screen_size": is_valid_screen_size,
        "ssd": is_valid_ssd,
        "ram": is_valid_ram,
        "cpu": is_valid_cpu,
        "gpu": is_valid_gpu,
    }
    print(f"[{label}] missing/invalid counts")
    print(f"{'column':<12} {'missing':>7} {'invalid':>7}")
    stats: Dict[str, Dict[str, int]] = {}
    for col in ["price", "screen_size", "ssd", "ram", "cpu", "gpu"]:
        series = df[col] if col in df.columns else pd.Series([])
        missing = int(series.apply(is_missing_value).sum())
        invalid = int(series.apply(lambda v: False if is_missing_value(v) else not validators[col](v)).sum())
        stats[col] = {"missing": missing, "invalid": invalid}
        print(f"{col:<12} {missing:>7} {invalid:>7}")
    return stats


def collect_invalid_examples(df: pd.DataFrame, max_examples: int = 5) -> Dict[str, Dict[str, object]]:
    validators = {
        "price": is_valid_price,
        "screen_size": is_valid_screen_size,
        "ssd": is_valid_ssd,
        "ram": is_valid_ram,
        "cpu": is_valid_cpu,
        "gpu": is_valid_gpu,
    }
    issues: Dict[str, Dict[str, object]] = {}
    for col, validator in validators.items():
        if col not in df.columns:
            continue
        mask = df[col].apply(lambda v: False if is_missing_value(v) else not validator(v))
        count = int(mask.sum())
        if count:
            sample = df.loc[mask, ["url", "name", col]].head(max_examples).to_dict(orient="records")
            issues[col] = {"count": count, "examples": sample}
    return issues


def fix_incehesap_dataframe(
    rows_or_df: Union[pd.DataFrame, List[Dict[str, object]]], max_examples: int = 5
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    df = ensure_dataframe(rows_or_df)
    fix_counts = Counter()
    reason_counts: Dict[str, Counter] = defaultdict(Counter)
    fix_examples: Dict[str, List[Dict[str, object]]] = defaultdict(list)

    rows: List[Dict[str, object]] = []
    for idx, row in df.iterrows():
        record = row.to_dict()
        name = record.get("name") or ""
        url = record.get("url") or ""

        # SSD
        current_ssd = coerce_int(record.get("ssd"))
        parsed_ssd, ssd_score, _ = extract_ssd_capacity(name)
        new_ssd = current_ssd
        ssd_reason = None
        if parsed_ssd is not None:
            if current_ssd in (2242, 2280):
                new_ssd = parsed_ssd
                ssd_reason = f"replaced_formfactor_{current_ssd}_with_{parsed_ssd}"
            elif current_ssd is None:
                new_ssd = parsed_ssd
                ssd_reason = f"filled_missing_with_{parsed_ssd}"
            elif current_ssd < 64 or current_ssd > 8192:
                new_ssd = parsed_ssd
                ssd_reason = f"replaced_invalid_{current_ssd}_with_{parsed_ssd}"
            elif current_ssd not in COMMON_SSD_CAPS and parsed_ssd in COMMON_SSD_CAPS and ssd_score >= 3:
                new_ssd = parsed_ssd
                ssd_reason = f"replaced_uncommon_{current_ssd}_with_{parsed_ssd}"
        elif current_ssd in (2242, 2280):
            new_ssd = None
            ssd_reason = f"removed_formfactor_{current_ssd}_no_replacement"

        # RAM
        current_ram = coerce_int(record.get("ram"))
        parsed_ram, ram_score, _ = extract_ram_gb(name)
        new_ram = current_ram
        ram_reason = None
        if parsed_ram is not None:
            if current_ram is None:
                new_ram = parsed_ram
                ram_reason = f"filled_missing_with_{parsed_ram}"
            elif current_ram < 4 or current_ram > 256:
                new_ram = parsed_ram
                ram_reason = f"replaced_invalid_{current_ram}_with_{parsed_ram}"
            elif current_ram > 128 and ram_score >= 3:
                new_ram = parsed_ram
                ram_reason = f"replaced_implausible_{current_ram}_with_{parsed_ram}"
            elif current_ram not in ALLOWED_RAM and parsed_ram in ALLOWED_RAM and ram_score >= 3:
                new_ram = parsed_ram
                ram_reason = f"replaced_uncommon_{current_ram}_with_{parsed_ram}"
            elif ram_score >= 3 and current_ram != parsed_ram:
                new_ram = parsed_ram
                ram_reason = f"replaced_with_title_{current_ram}_to_{parsed_ram}"

        # CPU
        current_cpu_raw = record.get("cpu")
        current_cpu_norm = normalize_cpu_value(current_cpu_raw)
        parsed_cpu, cpu_score = extract_cpu_from_text(name)
        new_cpu = current_cpu_norm
        cpu_reason = None
        if parsed_cpu:
            if not current_cpu_norm:
                new_cpu = parsed_cpu
                cpu_reason = f"filled_missing_with_{parsed_cpu}"
            elif is_cpu_generic(current_cpu_norm) and cpu_score >= 4:
                new_cpu = parsed_cpu
                cpu_reason = f"upgraded_generic_{current_cpu_norm}_to_{parsed_cpu}"
            elif cpu_score >= 4 and current_cpu_norm != parsed_cpu:
                new_cpu = parsed_cpu
                cpu_reason = f"replaced_with_title_{current_cpu_norm}_to_{parsed_cpu}"
        if not cpu_reason and current_cpu_raw and current_cpu_norm != current_cpu_raw:
            cpu_reason = "normalized_cpu"

        # GPU
        current_gpu_raw = record.get("gpu")
        current_gpu_norm, current_gpu_score, current_gpu_reason = extract_gpu_from_text(current_gpu_raw)
        parsed_gpu, parsed_gpu_score, parsed_gpu_reason = extract_gpu_from_text(name)
        new_gpu = current_gpu_norm
        gpu_reason = None
        if current_gpu_reason == "corrected_gtx_to_rtx":
            gpu_reason = "corrected_gtx_to_rtx"
        if parsed_gpu:
            if not current_gpu_norm:
                new_gpu = parsed_gpu
                gpu_reason = f"filled_missing_with_{parsed_gpu}"
            elif current_gpu_norm == "integrated" and parsed_gpu != "integrated" and parsed_gpu_score >= 3:
                new_gpu = parsed_gpu
                gpu_reason = f"replaced_integrated_with_{parsed_gpu}"
            elif parsed_gpu_score > current_gpu_score and parsed_gpu != current_gpu_norm:
                new_gpu = parsed_gpu
                gpu_reason = f"replaced_with_title_{current_gpu_norm}_to_{parsed_gpu}"
            if parsed_gpu_reason == "corrected_gtx_to_rtx":
                gpu_reason = "corrected_gtx_to_rtx"
        elif not current_gpu_norm and current_gpu_raw:
            new_gpu = "unknown"
            gpu_reason = "unparsed_gpu"

        record["ssd"] = new_ssd
        record["ram"] = new_ram
        record["cpu"] = new_cpu
        record["gpu"] = new_gpu

        rows.append(record)

        for field, reason, before, after in [
            ("ssd", ssd_reason, current_ssd, new_ssd),
            ("ram", ram_reason, current_ram, new_ram),
            ("cpu", cpu_reason, current_cpu_raw, new_cpu),
            ("gpu", gpu_reason, current_gpu_raw, new_gpu),
        ]:
            if reason:
                fix_counts[field] += 1
                reason_counts[field][reason] += 1
                if len(fix_examples[field]) < max_examples:
                    fix_examples[field].append(
                        {
                            "row_index": int(idx),
                            "url": url,
                            "name": name,
                            "before": before,
                            "after": after,
                            "reason": reason,
                        }
                    )

    fixed = pd.DataFrame(rows, columns=CSV_COLUMNS)
    fixed["ssd"] = fixed["ssd"].astype("Int64")
    fixed["ram"] = fixed["ram"].astype("Int64")

    report = {
        "row_count": int(len(fixed)),
        "fix_counts": dict(fix_counts),
        "fix_examples": dict(fix_examples),
        "top_fix_reasons": {
            field: reason_counts[field].most_common(10) for field in ["ssd", "ram", "cpu", "gpu"]
        },
    }
    return fixed, report


def build_fix_report(
    report: Dict[str, object],
    input_label: Optional[str],
    output_csv: str,
    before_stats: Dict[str, Dict[str, int]],
    after_stats: Dict[str, Dict[str, int]],
    fixed: pd.DataFrame,
) -> Dict[str, object]:
    invalid_examples = collect_invalid_examples(fixed)
    self_checks = []
    if (fixed["ssd"] == 2242).any() or (fixed["ssd"] == 2280).any():
        self_checks.append("ssd_formfactor_still_present")

    report.update(
        {
            "input_csv": input_label,
            "output_csv": output_csv,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "missing_invalid_before": before_stats,
            "missing_invalid_after": after_stats,
            "invalid_examples_after": invalid_examples,
            "self_checks": self_checks,
        }
    )
    return report


def write_fix_report(report: Dict[str, object], report_path: Optional[str]) -> None:
    if not report_path:
        return
    safe_mkdir(os.path.dirname(report_path) or ".")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def print_fix_summary(report: Dict[str, object], after_stats: Dict[str, Dict[str, int]]) -> None:
    total = report.get("row_count", 0)
    print("[summary]")
    print(f"total rows: {total}")
    for field in ["ssd", "ram", "cpu", "gpu"]:
        fixed_count = report.get("fix_counts", {}).get(field, 0)
        pct = (fixed_count / total * 100) if total else 0.0
        print(f"{field} fixed: {fixed_count} ({pct:.1f}%)")
    print(
        "invalid after: "
        f"ssd={after_stats['ssd']['invalid']} "
        f"ram={after_stats['ram']['invalid']} "
        f"cpu={after_stats['cpu']['invalid']} "
        f"gpu={after_stats['gpu']['invalid']}"
    )


def run_fix_pipeline_data(
    data: Union[pd.DataFrame, List[Dict[str, object]]],
    output_csv: str,
    report_path: Optional[str],
    input_label: Optional[str],
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    df = ensure_dataframe(data)
    before_stats = print_missing_invalid_table(df, "before")
    fixed, report = fix_incehesap_dataframe(df)
    after_stats = print_missing_invalid_table(fixed, "after")

    write_rows_csv(fixed, output_csv)

    report = build_fix_report(report, input_label, output_csv, before_stats, after_stats, fixed)
    write_fix_report(report, report_path)
    print_fix_summary(report, after_stats)
    return fixed, report


def run_fix_pipeline(input_csv: str, output_csv: str, report_path: Optional[str]) -> None:
    df = pd.read_csv(input_csv)
    run_fix_pipeline_data(df, output_csv, report_path, input_label=input_csv)


def build_scrape_config(out_csv: str) -> ScrapeConfig:
    return ScrapeConfig(
        base_categories=[
            "https://www.incehesap.com/notebook-fiyatlari/",
            # Ä°stersen ayrÄ± ayrÄ± da gezebilirsin:
            "https://www.incehesap.com/gaming-notebook-fiyatlari/",
        ],
        max_pages=3,  # ilk deneme iÃ§in dÃ¼ÅŸÃ¼k tut
        out_csv=out_csv,
        raw_dir="raw/incehesap_html",
        retries=3,
        sleep_range=(0.8, 1.6),
    )


def run_scrape_only(output_csv: str) -> None:
    cfg = build_scrape_config(output_csv)
    scraper = InceHesapScraper(cfg)
    rows = scraper.crawl()
    wrote_rows = write_rows_csv(rows, output_csv)
    print(f"[count] collected urls: {scraper.last_collected_urls}")
    print(f"[count] scraped product pages: {scraper.last_scraped_pages}")
    print(f"[count] wrote rows: {wrote_rows}")


def scrape_then_fix(
    output_csv: str = DEFAULT_MAIN_CSV,
    raw_output_csv: Optional[str] = DEFAULT_RAW_CSV,
    report_path: Optional[str] = DEFAULT_REPORT_JSON,
) -> None:
    cfg = build_scrape_config(output_csv)
    scraper = InceHesapScraper(cfg)
    rows = scraper.crawl()
    print(f"[count] collected urls: {scraper.last_collected_urls}")
    print(f"[count] scraped product pages: {scraper.last_scraped_pages}")

    raw_df = pd.DataFrame(rows)
    input_label = raw_output_csv or "in-memory"
    if raw_output_csv:
        write_rows_csv(raw_df, raw_output_csv)

    fixed_df, _ = run_fix_pipeline_data(raw_df, output_csv, report_path, input_label=input_label)
    print(f"[count] wrote rows: {len(fixed_df)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="InceHesap scraper and post-fix tool")
    subparsers = parser.add_subparsers(dest="command")

    fix_parser = subparsers.add_parser("fix", help="Fix and normalize an existing CSV")
    fix_parser.add_argument("--input", default=DEFAULT_MAIN_CSV, help="Input CSV path")
    fix_parser.add_argument("--output", default=DEFAULT_FIXED_CSV, help="Output CSV path")
    fix_parser.add_argument("--report", default=DEFAULT_REPORT_JSON, help="Report JSON path")
    fix_parser.add_argument("--no-report", action="store_true", help="Skip writing the report file")

    scrape_parser = subparsers.add_parser("scrape", help="Scrape, fix, and save (default)")
    scrape_parser.add_argument("--output", default=DEFAULT_MAIN_CSV, help="Fixed output CSV path")
    scrape_parser.add_argument("--raw-output", default=DEFAULT_RAW_CSV, help="Raw output CSV path")
    scrape_parser.add_argument("--report", default=DEFAULT_REPORT_JSON, help="Report JSON path")
    scrape_parser.add_argument("--no-raw", action="store_true", help="Skip writing the raw CSV")
    scrape_parser.add_argument("--no-report", action="store_true", help="Skip writing the report file")

    scrape_only_parser = subparsers.add_parser("scrape-only", help="Scrape and save raw CSV only")
    scrape_only_parser.add_argument("--output", default=DEFAULT_RAW_CSV, help="Raw output CSV path")

    args = parser.parse_args()

    if args.command in (None, "scrape"):
        output_csv = getattr(args, "output", DEFAULT_MAIN_CSV)
        raw_output = None if getattr(args, "no_raw", False) else getattr(
            args, "raw_output", DEFAULT_RAW_CSV
        )
        report_path = None if getattr(args, "no_report", False) else getattr(
            args, "report", DEFAULT_REPORT_JSON
        )
        scrape_then_fix(output_csv=output_csv, raw_output_csv=raw_output, report_path=report_path)
    elif args.command == "scrape-only":
        output_csv = getattr(args, "output", DEFAULT_RAW_CSV)
        run_scrape_only(output_csv)
    elif args.command == "fix":
        input_csv = args.input
        output_csv = args.output
        report_path = None if args.no_report else args.report
        run_fix_pipeline(input_csv, output_csv, report_path)


if __name__ == "__main__":
    main()
