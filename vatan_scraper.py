#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VatanBilgisayar laptop scraper.

Output CSV columns:
url,name,price,screen_size,ssd,cpu,ram,os,gpu
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse, urlencode

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


DEFAULT_START_URL = "https://www.vatanbilgisayar.com/notebook/"
DEFAULT_OUT = "data/vatan_laptops.csv"
DEFAULT_REPORT = "data/vatan_scrape_report.json"
DEFAULT_RAW_DIR = os.path.join("raw", "vatan_html")
LIST_SUBDIR = "list"
PRODUCT_SUBDIR = "product"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

PRICE_RE = re.compile(r"(\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{2})?)\s*(?:TL|\u20ba)", re.I)
CAPACITY_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(TB|GB)", re.I)

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "yclid",
    "ref",
    "referrer",
    "aff",
    "aff_id",
    "affiliate",
    "campaign",
    "banner",
}

SCREEN_LABELS = [
    "ekran boyutu",
    "ekran ebati",
    "ekran",
    "inch",
    "inc",
    "ekran ozelligi",
]
SSD_LABELS = [
    "ssd",
    "ssd kapasitesi",
    "disk kapasitesi",
    "depolama",
    "kapasite",
    "hdd",
    "emmc",
    "ufs",
    "nvme",
]
RAM_LABELS = [
    "ram",
    "bellek",
    "sistem bellegi",
]
OS_LABELS = [
    "isletim sistemi",
    "os",
]
GPU_LABELS = [
    "ekran karti",
    "grafik kart",
    "gpu",
    "vga",
    "ekran kart chipset",
    "grafik islemci",
]
CPU_LABELS = [
    "islemci",
    "islemci modeli",
    "islemci numarasi",
    "islemci teknolojisi",
    "islemci tipi",
    "cpu",
]


_thread_local = threading.local()

class RateLimiter:
    """Global rate limiter shared across threads."""

    def __init__(self, min_delay: float, max_delay: float) -> None:
        self.min_delay = max(0.0, min_delay)
        self.max_delay = max(self.min_delay, max_delay)
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            target = random.uniform(self.min_delay, self.max_delay)
            now = time.time()
            delta = now - self._last
            if delta < target:
                time.sleep(target - delta)
            self._last = time.time()


class HtmlStore:
    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        self.list_dir = os.path.join(base_dir, LIST_SUBDIR)
        self.product_dir = os.path.join(base_dir, PRODUCT_SUBDIR)
        self._lock = threading.Lock()
        os.makedirs(self.list_dir, exist_ok=True)
        os.makedirs(self.product_dir, exist_ok=True)

    def save_list(self, index: int, url: str, html: str) -> None:
        self._save(self.list_dir, "list", index, url, html)

    def save_product(self, index: int, url: str, html: str) -> None:
        self._save(self.product_dir, "product", index, url, html)

    def _save(self, directory: str, prefix: str, index: int, url: str, html: str) -> None:
        slug = slugify(url)
        filename = f"{prefix}_{index:04d}_{slug}.html"
        path = os.path.join(directory, filename)
        with self._lock:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)


@dataclass
class LaptopRow:
    url: str
    name: str
    price: Optional[float]
    screen_size: str
    ssd: str
    cpu: str
    ram: str
    os: str
    gpu: str

    def to_csv_row(self) -> Dict[str, str]:
        return {
            "url": self.url,
            "name": self.name,
            "price": "" if self.price is None else f"{self.price:.2f}",
            "screen_size": self.screen_size,
            "ssd": self.ssd,
            "cpu": self.cpu,
            "ram": self.ram,
            "os": self.os,
            "gpu": self.gpu,
        }


class Stats:
    def __init__(self, columns: Iterable[str]) -> None:
        self.columns = list(columns)
        self.total_rows = 0
        self.filled = {c: 0 for c in self.columns}

    def add(self, row: LaptopRow) -> None:
        self.total_rows += 1
        data = row.to_csv_row()
        for col in self.columns:
            if data.get(col):
                self.filled[col] += 1

    def completeness(self) -> Dict[str, float]:
        if self.total_rows == 0:
            return {c: 0.0 for c in self.columns}
        return {c: (self.filled[c] / self.total_rows) * 100.0 for c in self.columns}

    def missing_counts(self) -> Dict[str, int]:
        return {c: self.total_rows - self.filled[c] for c in self.columns}


def debug_log(enabled: bool, msg: str) -> None:
    if enabled:
        print(msg)


def slugify(text: str) -> str:
    if not text:
        return "page"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip())
    slug = slug.strip("_")
    if len(slug) > 80:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
        slug = f"{slug[:70]}_{digest}"
    return slug or "page"


def get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        s.headers.update(DEFAULT_HEADERS)
        _thread_local.session = s
    return _thread_local.session


def safe_get(url: str, limiter: RateLimiter, timeout: int = 25, tries: int = 5) -> str:
    last_err: Optional[Exception] = None
    for attempt in range(1, tries + 1):
        try:
            limiter.wait()
            resp = get_session().get(url, timeout=timeout)
            if resp.status_code in (403, 429):
                time.sleep(min(60.0, (2.2 ** attempt) + random.uniform(0.5, 1.5)))
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code} for {url}")
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception as exc:
            last_err = exc
            time.sleep(min(60.0, (1.7 ** attempt) + random.uniform(0.2, 0.6)))
    raise RuntimeError(f"GET failed after {tries} tries: {url} | last_err={last_err}")


def make_soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def normalize_url(url: str, drop_query: bool) -> str:
    parts = urlparse(url)
    scheme = parts.scheme or "https"
    netloc = parts.netloc.lower()
    if netloc == "vatanbilgisayar.com":
        netloc = "www.vatanbilgisayar.com"
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    query = "" if drop_query else parts.query
    return urlunparse((scheme, netloc, path, "", query, ""))


def normalize_product_url(url: str) -> str:
    return normalize_url(url, drop_query=True)


def normalize_list_url(url: str) -> str:
    return normalize_url(url, drop_query=False)


def is_product_url(url: str) -> bool:
    parts = urlparse(url)
    host = parts.netloc.lower()
    if not host:
        return False
    if host == "vatanbilgisayar.com":
        host = "www.vatanbilgisayar.com"
    if host != "www.vatanbilgisayar.com":
        return False
    path = (parts.path or "").lower()
    if not path.endswith(".html"):
        return False
    if "/notebook/" in path and not path.endswith(".html"):
        return False
    query = parts.query.lower()
    if "opf=" in query:
        return False
    q = parse_qs(parts.query)
    for key in q:
        k = key.lower()
        if k.startswith("utm_") or k in TRACKING_PARAMS:
            return False
    if re.search(r"(campaign|kampanya|affiliate|banner)", query):
        return False
    return True


def strip_diacritics(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def normalize_label(text: str) -> str:
    t = strip_diacritics(text)
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def clean_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def extract_canonical_url(soup: BeautifulSoup, url: str) -> str:
    link = soup.find("link", rel=lambda v: v and "canonical" in v.lower())
    if link and link.get("href"):
        return normalize_product_url(urljoin(url, link["href"].strip()))
    return normalize_product_url(url)


def extract_jsonld_product(soup: BeautifulSoup) -> Optional[Dict]:
    for s in soup.find_all("script", type="application/ld+json"):
        raw = (s.string or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        def find_product(obj: object) -> Optional[Dict]:
            if isinstance(obj, dict):
                t = obj.get("@type")
                if isinstance(t, list) and any(x == "Product" for x in t):
                    return obj
                if t == "Product":
                    return obj
                for v in obj.values():
                    found = find_product(v)
                    if found:
                        return found
            elif isinstance(obj, list):
                for item in obj:
                    found = find_product(item)
                    if found:
                        return found
            return None

        product = find_product(data)
        if product:
            return product
    return None


def extract_specs_from_jsonld(product: Optional[Dict]) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    if not product:
        return specs
    props = product.get("additionalProperty")
    if isinstance(props, list):
        for item in props:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            value = item.get("value")
            if name and value:
                specs[str(name).strip()] = str(value).strip()
    return specs


def _add_spec(specs: Dict[str, str], label: str, value: str) -> None:
    if not label or not value:
        return
    specs.setdefault(label.strip(), value.strip())


def extract_specs_from_html(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    containers: List[BeautifulSoup] = []
    for sel in ["#urun-ozellikleri", ".urun-ozellikleri", ".product-specs", ".product-feature"]:
        container = soup.select_one(sel)
        if container:
            containers.append(container)
    if not containers:
        containers = [soup]

    for container in containers:
        for tr in container.select("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if len(cells) >= 2:
                _add_spec(specs, cells[0], cells[1])
        for dt in container.select("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                _add_spec(specs, dt.get_text(" ", strip=True), dd.get_text(" ", strip=True))
        for li in container.select("li"):
            text = li.get_text(" ", strip=True)
            if ":" in text:
                label, value = text.split(":", 1)
                _add_spec(specs, label, value)

    if specs:
        return specs

    for tr in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) >= 2:
            _add_spec(specs, cells[0], cells[1])
    return specs


def normalize_specs_map(primary: Dict[str, str], secondary: Dict[str, str]) -> Dict[str, str]:
    merged = dict(primary)
    for k, v in secondary.items():
        merged.setdefault(k, v)
    normalized: Dict[str, str] = {}
    for label, value in merged.items():
        n = normalize_label(label)
        if not n or not value:
            continue
        normalized.setdefault(n, value.strip())
    return normalized


def extract_title(soup: BeautifulSoup, product: Optional[Dict]) -> str:
    if product and product.get("name"):
        return clean_text(str(product["name"]))
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return clean_text(h1.get_text(" ", strip=True))
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return clean_text(og["content"])
    title = soup.find("title")
    return clean_text(title.get_text(" ", strip=True)) if title else ""


def normalize_price(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def extract_price(soup: BeautifulSoup, product: Optional[Dict]) -> Optional[float]:
    if product:
        offers = product.get("offers")
        if isinstance(offers, dict):
            price = normalize_price(offers.get("price"))
            if price is not None:
                return price
        elif isinstance(offers, list):
            for offer in offers:
                if isinstance(offer, dict):
                    price = normalize_price(offer.get("price"))
                    if price is not None:
                        return price
    el = soup.select_one('[itemprop="price"]')
    if el:
        if el.has_attr("content"):
            price = normalize_price(el["content"])
            if price is not None:
                return price
        price = normalize_price(el.get_text(" ", strip=True))
        if price is not None:
            return price
    for sel in [
        ".product-detail__price",
        ".product-list__price--new",
        ".product-list__price-new",
        ".product-list__price",
        "[data-price]",
        ".basketMobile_price",
    ]:
        el = soup.select_one(sel)
        if not el:
            continue
        if el.has_attr("data-price"):
            price = normalize_price(el["data-price"])
        else:
            price = normalize_price(el.get_text(" ", strip=True))
        if price is not None:
            return price
    html = str(soup)
    m = PRICE_RE.search(html)
    if m:
        return normalize_price(m.group(1))
    return None


def parse_screen_size(text: str) -> str:
    if not text:
        return ""
    t = text.replace(",", ".")
    m = re.search(r"(\d{1,2}(?:\.\d{1,2})?)\s*(?:\"|inch|inc|in\u00e7)", t, re.I)
    if not m:
        m = re.search(r"\b(\d{2}(?:\.\d{1,2})?)\b", t)
    if not m:
        return ""
    try:
        val = float(m.group(1))
    except ValueError:
        return ""
    if val < 10 or val > 20:
        return ""
    if abs(val - round(val)) < 0.01:
        out = str(int(round(val)))
    else:
        out = f"{val:.2f}".rstrip("0").rstrip(".")
    return f"{out}\""


def format_capacity(num: str, unit: str) -> str:
    try:
        value = float(num.replace(",", "."))
    except ValueError:
        return ""
    unit = unit.upper()
    gb = int(round(value * 1024)) if unit == "TB" else int(round(value))
    return str(gb)


def parse_capacity(text: str, require_anchor: bool) -> str:
    if not text:
        return ""
    t = text.upper()
    matches = list(CAPACITY_RE.finditer(t))
    for m in matches:
        window = t[max(0, m.start() - 25) : min(len(t), m.end() + 25)]
        if require_anchor and not any(
            k in window for k in ["SSD", "NVME", "M.2", "EMMC", "UFS", "DEPOLAMA", "DISK", "HDD"]
        ):
            continue
        return format_capacity(m.group(1), m.group(2))
    return ""


def parse_ram(text: str) -> str:
    if not text:
        return ""
    t = text.upper()
    m = re.search(r"(\d+)\s*X\s*(\d+)\s*GB", t)
    if m:
        total = int(m.group(1)) * int(m.group(2))
        return str(total)
    matches = re.findall(r"(\d+)\s*GB", t)
    if matches:
        nums = [int(n) for n in matches if int(n) <= 128]
        return str(max(nums)) if nums else ""
    return ""


def normalize_os(text: str) -> str:
    if not text:
        return ""
    t = text.lower()
    if "freedos" in t or "free dos" in t:
        return "FreeDOS"
    if "windows 11" in t or "win11" in t or "w11" in t:
        if "pro" in t:
            return "Windows 11 Pro"
        if "home" in t:
            return "Windows 11 Home"
        return "Windows 11"
    if "windows 10" in t or "win10" in t or "w10" in t:
        return "Windows 10"
    if "macos" in t or "mac os" in t:
        return "macOS"
    if "linux" in t:
        return "Linux"
    return clean_text(text)


def normalize_cpu(cpu_text: str, title: str) -> str:
    raw = clean_text(" ".join(x for x in [cpu_text, title] if x))
    if not raw:
        return ""
    m = re.search(r"core\s+ultra\s+([3579])\s*([0-9]{3}[a-z]{0,2})", raw, re.I)
    if m:
        return f"ultra{m.group(1)}-{m.group(2).lower()}"
    m = re.search(r"\bcore\s+([3579])\s*([0-9]{3}[a-z]{0,2})\b", raw, re.I)
    if m:
        return f"core{m.group(1)}-{m.group(2).lower()}"
    m = re.search(r"\b(i[3579])\s*[- ]?\s*(\d{4,5}[a-z]{0,2})\b", raw, re.I)
    if m:
        return f"{m.group(1).lower()}-{m.group(2).lower()}"
    m = re.search(r"\bx\d[p]?-\d{2}-\d{3}\b", raw, re.I)
    if m:
        return m.group(0).lower()
    m = re.search(r"ryzen\s+ai\s+([3579])\s*(hx|h)?\s*([0-9]{3})", raw, re.I)
    if m:
        suffix = f"{m.group(2)}" if m.group(2) else ""
        return f"ryzenai{m.group(1)}-{(suffix + m.group(3)).lower()}".strip("-")
    m = re.search(r"ryzen\s+(?:ai\s+)?([3579])\s*[- ]?\s*(\d{3,5}[a-z]{0,2})", raw, re.I)
    if m:
        return f"ryzen{m.group(1)}-{m.group(2).lower()}"
    m = re.search(r"\bR([3579])\s*[- ]?\s*(\d{4,5}[a-z]{0,2})\b", raw, re.I)
    if m:
        return f"ryzen{m.group(1)}-{m.group(2).lower()}"
    m = re.search(r"\b(celeron|pentium|athlon)\s+([a-z0-9\-]+)\b", raw, re.I)
    if m:
        return f"{m.group(1).lower()} {m.group(2).lower()}"
    m = re.search(r"\bN(\d{3})\b", raw, re.I)
    if m:
        return f"n{m.group(1)}"
    m = re.search(r"\bM([1-5])\s*(pro|max|ultra)?\b", raw, re.I)
    if m:
        suffix = m.group(2) or ""
        return f"m{m.group(1)}{suffix.lower()}".strip()
    return ""


def extract_discrete_gpu(text: str) -> str:
    if not text:
        return ""
    t = text.lower()
    m = re.search(r"rtx\s*a?\s*(\d{3,4})\s*(ti|super)?", t)
    if m:
        suffix = f" {m.group(2)}" if m.group(2) else ""
        return f"rtx {m.group(1)}{suffix}".strip()
    m = re.search(r"gtx\s*(\d{3,4})\s*(ti)?", t)
    if m:
        suffix = f" {m.group(2)}" if m.group(2) else ""
        return f"gtx {m.group(1)}{suffix}".strip()
    m = re.search(r"mx\s*(\d{3})", t)
    if m:
        return f"mx {m.group(1)}"
    m = re.search(r"rx\s*(\d{3,4}[a-z]?)", t)
    if m:
        return f"rx {m.group(1)}"
    m = re.search(r"arc\s*([a-z]?\d{3,4}m?)", t)
    if m:
        return f"arc {m.group(1)}"
    return ""


def extract_integrated_gpu(text: str) -> str:
    if not text:
        return ""
    t = text.lower()
    if "iris xe" in t:
        return "iris xe"
    if "iris" in t:
        return "iris"
    if "uhd" in t:
        return "uhd"
    m = re.search(r"radeon\s+(\d{3}m)", t)
    if m:
        return f"radeon {m.group(1)}"
    if "radeon" in t and "rx" not in t:
        return "radeon"
    if "intel" in t and "graphics" in t:
        return "integrated"
    if any(k in t for k in ["entegre", "dahili", "paylasim", "shared", "onboard", "integrated"]):
        return "integrated"
    return ""


def normalize_gpu(gpu_text: str, title: str) -> str:
    raw = clean_text(" ".join(x for x in [gpu_text, title] if x))
    model = extract_discrete_gpu(raw)
    if model:
        return model
    integrated = extract_integrated_gpu(raw)
    if integrated:
        return integrated
    return "integrated"


def pick_spec_value(specs: Dict[str, str], labels: List[str]) -> Tuple[str, str]:
    for key in labels:
        for label, value in specs.items():
            if key in label:
                return value, label
    return "", ""


def extract_screen_size(specs: Dict[str, str], title: str) -> Tuple[str, str]:
    value, label = pick_spec_value(specs, SCREEN_LABELS)
    if value:
        parsed = parse_screen_size(value)
        if parsed:
            return parsed, label
    parsed = parse_screen_size(title)
    return (parsed, "title") if parsed else ("", "")


def extract_ssd(specs: Dict[str, str], title: str) -> Tuple[str, str]:
    candidates: List[Tuple[int, str, str]] = []
    for label, value in specs.items():
        if not any(k in label for k in SSD_LABELS):
            continue
        score = 0
        l = label
        v = value.lower()
        if "ssd" in l or "ssd" in v or "nvme" in v or "m.2" in v:
            score += 3
        if "ufs" in l or "emmc" in l or "ufs" in v or "emmc" in v:
            score += 2
        if "hdd" in l or "hdd" in v:
            score -= 1
        if "depolama" in l or "disk kapasitesi" in l:
            score += 1
        candidates.append((score, label, value))
    candidates.sort(reverse=True)
    for _, label, value in candidates:
        cap = parse_capacity(value, require_anchor=False)
        if cap:
            return cap, label
    cap = parse_capacity(title, require_anchor=True)
    return (cap, "title") if cap else ("", "")


def extract_ram(specs: Dict[str, str], title: str) -> Tuple[str, str]:
    value, label = pick_spec_value(specs, RAM_LABELS)
    if value:
        parsed = parse_ram(value)
        if parsed:
            return parsed, label
    parsed = parse_ram(title)
    return (parsed, "title") if parsed else ("", "")


def extract_os(specs: Dict[str, str], title: str) -> Tuple[str, str]:
    value, label = pick_spec_value(specs, OS_LABELS)
    if value:
        parsed = normalize_os(value)
        if parsed:
            return parsed, label
    parsed = normalize_os(title)
    return (parsed, "title") if parsed else ("", "")


def extract_cpu(specs: Dict[str, str], title: str) -> Tuple[str, str]:
    cpu_val, label = pick_spec_value(specs, CPU_LABELS)
    cpu = normalize_cpu(cpu_val, title)
    if cpu:
        return cpu, label
    cpu = normalize_cpu("", title)
    return (cpu, "title") if cpu else ("", "")


def extract_gpu(specs: Dict[str, str], title: str) -> Tuple[str, str]:
    value, label = pick_spec_value(specs, GPU_LABELS)
    gpu = normalize_gpu(value, title)
    return gpu, label or "title"


def is_bad_name(name: str) -> bool:
    if not name:
        return True
    clean = clean_text(name)
    if len(clean) < 6:
        return True
    if clean.strip().lower() == "notebook":
        return True
    return False


def extract_product_links(html: str, base_url: str, debug: bool = False) -> List[str]:
    soup = make_soup(html)
    anchors = soup.select("a.product-list-link[href]")
    if not anchors:
        anchors = soup.select(".product-list a[href]")
    if not anchors:
        anchors = soup.select("a[href]")

    ordered: List[str] = []
    seen: Set[str] = set()
    for a in anchors:
        href = a.get("href", "").strip()
        if not href:
            continue
        full = urljoin(base_url, href)
        full = normalize_url(full, drop_query=False)
        if not is_product_url(full):
            continue
        normalized = normalize_product_url(full)
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)

    debug_log(debug, f"[extract_product_links] found={len(ordered)} on {base_url}")
    return ordered


def extract_next_page_url(html: str, current_url: str) -> Optional[str]:
    soup = make_soup(html)
    link = soup.find("link", rel=lambda v: v and "next" in v.lower())
    if link and link.get("href"):
        return urljoin(current_url, link["href"].strip())
    a = soup.select_one('a[rel="next"][href]')
    if a:
        return urljoin(current_url, a["href"])
    for a in soup.find_all("a", href=True):
        text = (a.get_text(" ", strip=True) or "").lower()
        if "sonraki" in text or "next" in text:
            return urljoin(current_url, a["href"])
    return None


def build_page_url(base_url: str, page: int) -> str:
    parts = urlparse(base_url)
    q = parse_qs(parts.query)
    q["page"] = [str(page)]
    new_query = urlencode(q, doseq=True)
    return urlunparse(parts._replace(query=new_query))


def collect_product_urls(
    start_url: str,
    limiter: RateLimiter,
    max_pages: int,
    debug: bool,
    html_store: HtmlStore,
) -> Tuple[List[str], int, int]:
    visited: Set[str] = set()
    product_urls: List[str] = []
    total_links = 0

    url = normalize_list_url(start_url)
    page_count = 0
    while url and page_count < max_pages:
        if url in visited:
            break
        visited.add(url)
        page_count += 1

        debug_log(debug, f"[list] {url}")
        html = safe_get(url, limiter)
        html_store.save_list(page_count, url, html)

        new_links = extract_product_links(html, base_url=url, debug=debug)
        total_links += len(new_links)
        for link in new_links:
            if link not in product_urls:
                product_urls.append(link)

        next_url = extract_next_page_url(html, current_url=url)
        if not next_url:
            parsed = urlparse(url)
            q = parse_qs(parsed.query)
            if "page" in q:
                try:
                    page = int(q["page"][0]) + 1
                    next_url = build_page_url(url, page)
                except Exception:
                    next_url = None
            else:
                next_url = build_page_url(url, page_count + 1)

        if next_url and next_url not in visited:
            url = normalize_list_url(next_url)
        else:
            break

    return product_urls, page_count, total_links


def is_product_page(html: str, url: str, debug: bool = False) -> bool:
    if not is_product_url(url):
        debug_log(debug, f"[is_product_page] url not product: {url}")
        return False
    soup = make_soup(html)
    jsonld = extract_jsonld_product(soup) is not None
    has_specs = soup.select_one("#urun-ozellikleri") is not None
    has_h1 = soup.find("h1") is not None
    has_price = PRICE_RE.search(html) is not None
    result = jsonld or (has_specs and has_h1 and has_price)
    if debug:
        debug_log(
            True,
            f"[is_product_page] url={url} jsonld={jsonld} specs={has_specs} h1={has_h1} price={has_price} -> {result}",
        )
    return result


def parse_product(
    html: str,
    url: str,
    debug: bool,
) -> Tuple[Optional[LaptopRow], str]:
    soup = make_soup(html)
    canonical = extract_canonical_url(soup, url)
    if not is_product_url(canonical):
        return None, "not_product_url"
    if not is_product_page(html, canonical, debug=debug):
        return None, "not_product_url"

    product = extract_jsonld_product(soup)
    name = extract_title(soup, product)
    if is_bad_name(name):
        return None, "name_notebook"

    price = extract_price(soup, product)
    if price is None:
        return None, "missing_price"

    specs_jsonld = extract_specs_from_jsonld(product)
    specs_html = extract_specs_from_html(soup)
    specs = normalize_specs_map(specs_jsonld, specs_html)

    screen_size, screen_src = extract_screen_size(specs, name)
    ssd, ssd_src = extract_ssd(specs, name)
    cpu, cpu_src = extract_cpu(specs, name)
    ram, ram_src = extract_ram(specs, name)
    os_val, os_src = extract_os(specs, name)
    gpu, gpu_src = extract_gpu(specs, name)

    if debug:
        debug_log(debug, f"[field] screen_size ({screen_src}): {screen_size or '-'}")
        debug_log(debug, f"[field] ssd ({ssd_src}): {ssd or '-'}")
        debug_log(debug, f"[field] cpu ({cpu_src}): {cpu or '-'}")
        debug_log(debug, f"[field] ram ({ram_src}): {ram or '-'}")
        debug_log(debug, f"[field] os ({os_src}): {os_val or '-'}")
        debug_log(debug, f"[field] gpu ({gpu_src}): {gpu or '-'}")

    row = LaptopRow(
        url=canonical,
        name=name,
        price=price,
        screen_size=screen_size,
        ssd=ssd,
        cpu=cpu,
        ram=ram,
        os=os_val,
        gpu=gpu,
    )
    return row, ""


def write_csv(path: str, rows: Iterable[LaptopRow]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fieldnames = ["url", "name", "price", "screen_size", "ssd", "cpu", "ram", "os", "gpu"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", "--start-url", dest="start_url", default=DEFAULT_START_URL)
    ap.add_argument("--max-pages", type=int, default=60)
    ap.add_argument("--max-products", type=int, default=0, help="0 means no limit")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--raw-dir", default=DEFAULT_RAW_DIR)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--min-delay", type=float, default=0.8)
    ap.add_argument("--max-delay", type=float, default=1.6)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    limiter = RateLimiter(min_delay=args.min_delay, max_delay=args.max_delay)
    html_store = HtmlStore(args.raw_dir)

    print("VATAN LAPTOP SCRAPER")
    print(f"start_url={args.start_url}")
    print(f"out={args.out} max_pages={args.max_pages} workers={args.workers}")

    product_urls, list_pages, total_links = collect_product_urls(
        start_url=args.start_url,
        limiter=limiter,
        max_pages=args.max_pages,
        debug=args.debug,
        html_store=html_store,
    )

    if not product_urls:
        raise SystemExit("No product URLs found. The site structure may have changed.")

    if args.max_products and len(product_urls) > args.max_products:
        product_urls = product_urls[: args.max_products]

    print(f"[done] product urls collected: {len(product_urls)}")

    seen_canonical: Set[str] = set()
    seen_lock = threading.Lock()
    rows: List[LaptopRow] = []
    stats = Stats(["name", "price", "screen_size", "ssd", "cpu", "ram", "os", "gpu"])
    dropped = {
        "not_product_url": 0,
        "name_notebook": 0,
        "missing_price": 0,
        "parse_failed": 0,
        "duplicate": 0,
    }
    errors: List[str] = []
    detail_pages_fetched = 0

    def worker(u: str, idx: int) -> Tuple[Optional[LaptopRow], str]:
        html = safe_get(u, limiter)
        html_store.save_product(idx, u, html)
        row, reason = parse_product(html, u, debug=args.debug)
        return row, reason

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(worker, u, i + 1) for i, u in enumerate(product_urls)]
        for i, fut in enumerate(as_completed(futures), start=1):
            try:
                row, reason = fut.result()
                detail_pages_fetched += 1
            except Exception as exc:
                errors.append(str(exc))
                debug_log(args.debug, f"[detail] fail: {exc}")
                continue
            if reason:
                if reason not in dropped:
                    dropped[reason] = 0
                dropped[reason] += 1
                continue
            if not row:
                dropped["parse_failed"] += 1
                continue
            with seen_lock:
                if row.url in seen_canonical:
                    dropped["duplicate"] += 1
                    continue
                seen_canonical.add(row.url)
            rows.append(row)
            stats.add(row)
            if args.debug:
                debug_log(args.debug, f"[{i}/{len(product_urls)}] OK | {row.price} | {row.name[:70]}")

    if rows:
        write_csv(args.out, rows)
        print(f"[done] written -> {args.out}")
    else:
        print("[done] no rows written")

    completeness = stats.completeness()
    missing_counts = stats.missing_counts()

    report = {
        "start_url": args.start_url,
        "list_pages_visited": list_pages,
        "total_links_extracted": total_links,
        "total_unique_product_urls": len(product_urls),
        "detail_pages_fetched": detail_pages_fetched,
        "rows_written": stats.total_rows,
        "dropped": dropped,
        "missing_counts": missing_counts,
        "completeness_pct": completeness,
        "errors": errors[:50],
    }

    if args.report:
        os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    print("\nSUMMARY")
    print(f"list_pages_visited: {list_pages}")
    print(f"discovered_product_links: {total_links}")
    print(f"unique_product_urls: {len(product_urls)}")
    print(f"detail_pages_fetched: {detail_pages_fetched}")
    print(f"written_rows: {stats.total_rows}")
    print("column_completeness:")
    for col in ["name", "price", "cpu", "ram", "ssd", "os", "screen_size", "gpu"]:
        print(f"  {col}: {completeness.get(col, 0.0):.1f}%")
    print("dropped_rows:")
    for key, val in dropped.items():
        print(f"  {key}: {val}")


if __name__ == "__main__":
    main()
