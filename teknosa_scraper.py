
# teknosa_scraper.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE = "https://www.teknosa.com"
CATEGORY_LAPTOPS = f"{BASE}/laptop-notebook-c-116004"
ROBOTS_URL = f"{BASE}/robots.txt"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.7,en;q=0.6",
}

RETRY_STATUSES = {429, 500, 502, 503, 504}

PRICE_RE = re.compile(
    r"(\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{2})?)\s*(?:TL|\u20ba)",
    re.IGNORECASE,
)

SCREEN_RE = re.compile(r"\b(\d{1,2}(?:[.,]\d)?)\s*(?:\"|in|inch|inc)\b", re.IGNORECASE)
RAM_EXPLICIT_RE = re.compile(
    r"\b(\d{1,3})\s*GB\s*(?:RAM|DDR[345]|LPDDR[345]|DDR[345]X)\b",
    re.IGNORECASE,
)
SSD_EXPLICIT_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(TB|GB)\s*(?:SSD|NVME|M\.2|PCIe|PCI-E)\b",
    re.IGNORECASE,
)

CPU_PATTERNS = [
    re.compile(r"Core\s+Ultra\s+\d+\s*\d{3}[A-Z]?", re.IGNORECASE),
    re.compile(r"Core\s+i[3579]\s*[-]?\s*\d{4,5}[A-Z]{0,2}", re.IGNORECASE),
    re.compile(r"\bi[3579]\s*[-]?\s*\d{4,5}[A-Z]{0,2}\b", re.IGNORECASE),
    re.compile(r"Ryzen\s+AI\s+\d+\s+\w+\s*\d{3,4}[A-Z]?", re.IGNORECASE),
    re.compile(r"Ryzen\s+[3579]\s+\d{4,5}[A-Z]{0,2}", re.IGNORECASE),
    re.compile(r"Ryzen\s+\d+\s+[A-Za-z]{0,2}\d{3,4}[A-Z]?", re.IGNORECASE),
    re.compile(r"Intel\s+N\d{2,3}", re.IGNORECASE),
    re.compile(r"\bN\d{2,3}\b", re.IGNORECASE),
    re.compile(r"Apple\s+M\d\s*(?:Pro|Max|Ultra)?", re.IGNORECASE),
    re.compile(r"\bM\d\s*(?:Pro|Max|Ultra)?\b", re.IGNORECASE),
    re.compile(r"Celeron\s+[A-Za-z0-9\-]+", re.IGNORECASE),
    re.compile(r"Pentium\s+[A-Za-z0-9\-]+", re.IGNORECASE),
    re.compile(r"Athlon\s+[A-Za-z0-9\-]+", re.IGNORECASE),
]

OS_PATTERNS = [
    (re.compile(r"\bFree\s*DOS\b|\bFreeDOS\b|\bDOS\b", re.IGNORECASE), "FreeDOS"),
    (re.compile(r"\bWindows\s*11\s*Pro\b|\bWin\s*11\s*Pro\b|\bW11\s*Pro\b", re.IGNORECASE), "Windows 11 Pro"),
    (
        re.compile(r"\bWindows\s*11\s*Home\b|\bWin\s*11\s*Home\b|\bW11\s*Home\b|\bW11H\b", re.IGNORECASE),
        "Windows 11 Home",
    ),
    (re.compile(r"\bWindows\s*11\b|\bWin\s*11\b|\bW11\b", re.IGNORECASE), "Windows 11"),
    (re.compile(r"\bWindows\s*10\b|\bWin\s*10\b|\bW10\b", re.IGNORECASE), "Windows 10"),
    (re.compile(r"\bUbuntu\b", re.IGNORECASE), "Ubuntu"),
    (re.compile(r"\bLinux\b", re.IGNORECASE), "Linux"),
    (re.compile(r"\bChrome\s*OS\b", re.IGNORECASE), "ChromeOS"),
    (re.compile(r"\bmacOS\b|\bMac\s*OS\b", re.IGNORECASE), "macOS"),
]

GPU_PATTERNS = [
    re.compile(r"RTX\s?\d{3,4}\s*(?:Ti)?", re.IGNORECASE),
    re.compile(r"GTX\s?\d{3,4}", re.IGNORECASE),
    re.compile(r"MX\s?\d{3,4}", re.IGNORECASE),
    re.compile(r"Arc\s?[A-Z]\d{3,4}", re.IGNORECASE),
    re.compile(r"Iris\s?Xe", re.IGNORECASE),
    re.compile(r"Iris", re.IGNORECASE),
    re.compile(r"UHD\s?Graphics", re.IGNORECASE),
    re.compile(r"Radeon\s?[A-Za-z0-9 ]+", re.IGNORECASE),
]

BLOCKED_TITLE_KEYWORDS = [
    "just a moment",
    "attention required",
    "access denied",
    "checking your browser",
    "verify you are human",
]

BLOCKED_BODY_KEYWORDS = [
    "/cdn-cgi/",
    "cf-ray",
    "cloudflare",
    "cf-challenge",
    "captcha",
    "g-recaptcha",
    "hcaptcha",
    "security check",
    "enable cookies",
]

PRODUCT_URL_RE = re.compile(r"-p-\d+", re.IGNORECASE)


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
            "screen_size": self.screen_size or "",
            "ssd": self.ssd or "",
            "cpu": self.cpu or "",
            "ram": self.ram or "",
            "os": self.os or "",
            "gpu": self.gpu or "",
        }


@dataclass
class FetchResult:
    url: str
    status: Optional[int]
    text: Optional[str]
    source: str
    from_cache: bool = False
    html_path: Optional[Path] = None
    blocked_reason: Optional[str] = None
    blocked_path: Optional[Path] = None
    screenshot_path: Optional[Path] = None
    error: Optional[str] = None


@dataclass
class BlockedEvent:
    step: str
    url: str
    reason: str
    source: str
    html_path: Optional[Path]
    screenshot_path: Optional[Path]


class RateLimiter:
    def __init__(self, min_delay: float, max_delay: float) -> None:
        self.min_delay = max(0.0, min_delay)
        self.max_delay = max(self.min_delay, max_delay)
        self._last = 0.0
        self._lock = None

    def wait(self) -> None:
        if self._lock is None:
            import threading

            self._lock = threading.Lock()
        with self._lock:
            target = random.uniform(self.min_delay, self.max_delay)
            now = time.time()
            delta = now - self._last
            if delta < target:
                time.sleep(target - delta)
            self._last = time.time()


class CacheStore:
    def __init__(self, base_dir: Path, read_enabled: bool, write_enabled: bool) -> None:
        self.base_dir = base_dir
        self.read_enabled = read_enabled
        self.write_enabled = write_enabled
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for sub in ("list", "product", "sitemap", "blocked", "screenshots"):
            (self.base_dir / sub).mkdir(parents=True, exist_ok=True)

    def _path_for(self, kind: str, key: str, ext: str) -> Path:
        slug = safe_slug(key)
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        return self.base_dir / kind / f"{slug}_{digest}{ext}"

    def read(self, kind: str, url: str) -> Optional[str]:
        if not self.read_enabled:
            return None
        path = self._path_for(kind, url, ".html")
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")
        return None

    def write(self, kind: str, url: str, text: str, ext: str = ".html") -> Optional[Path]:
        if not self.write_enabled:
            return None
        path = self._path_for(kind, url, ext)
        path.write_text(text, encoding="utf-8")
        return path

    def save_blocked(self, kind: str, url: str, text: str) -> Optional[Path]:
        key = f"{kind}:{url}"
        return self.write("blocked", key, text, ext=".html")

    def save_screenshot(self, kind: str, url: str) -> Optional[Path]:
        if not self.write_enabled:
            return None
        key = f"{kind}:{url}"
        return self._path_for("screenshots", key, ".png")


class Stats:
    def __init__(self, columns: Sequence[str]) -> None:
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


def safe_slug(text: str, max_len: int = 80) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")
    if not slug:
        slug = "page"
    if len(slug) > max_len:
        slug = slug[:max_len]
    return slug


def strip_diacritics(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def normalize_text(text: str) -> str:
    text = strip_diacritics(text or "")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).lower().strip()
    return re.sub(r"\s+", " ", text)

def detect_blocked(text: str, status_code: Optional[int]) -> Optional[str]:
    if status_code in (401, 403, 429, 503):
        return f"http_{status_code}"
    if not text:
        return "empty_response"
    low = text.lower()
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip().lower()
    if title:
        for kw in BLOCKED_TITLE_KEYWORDS:
            if kw in title:
                return f"title_{kw.replace(' ', '_')}"
    for kw in BLOCKED_BODY_KEYWORDS:
        if kw in low:
            return f"body_{kw.replace('/', '').replace(' ', '_')}"
    return None


def tr_price_to_float(text: str) -> Optional[float]:
    if not text:
        return None
    m = PRICE_RE.search(text)
    if not m:
        return None
    s = m.group(1).replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def normalize_storage(amount: str, unit: str) -> str:
    amt = amount.replace(",", ".")
    unit = unit.upper()
    try:
        val = float(amt)
        if abs(val - round(val)) < 0.01:
            amt = str(int(round(val)))
        else:
            amt = f"{val:.2f}".rstrip("0").rstrip(".")
    except ValueError:
        amt = amount
    return f"{amt}{unit}"


def extract_screen_size(title: str) -> str:
    if not title:
        return ""
    m = SCREEN_RE.search(title)
    if not m:
        return ""
    raw = m.group(1).replace(",", ".")
    try:
        val = float(raw)
    except ValueError:
        return ""
    if val < 10 or val > 20:
        return ""
    if abs(val - round(val)) < 0.01:
        size = str(int(round(val)))
    else:
        size = f"{val:.1f}".rstrip("0").rstrip(".")
    return f'{size}"'


def extract_ram(title: str) -> str:
    if not title:
        return ""
    m = RAM_EXPLICIT_RE.search(title)
    if m:
        return f"{m.group(1)}GB"
    candidates: List[int] = []
    for m in re.finditer(r"\b(\d{1,3})\s*GB\b", title, re.IGNORECASE):
        val = int(m.group(1))
        context = title[max(0, m.start() - 12) : m.end() + 12].lower()
        if any(k in context for k in ("ssd", "nvme", "m.2", "hdd")):
            continue
        if any(k in context for k in ("rtx", "gtx", "mx", "gddr")):
            continue
        if 2 <= val <= 128:
            candidates.append(val)
    if not candidates:
        return ""
    return f"{min(candidates)}GB"


def extract_ssd(title: str) -> str:
    if not title:
        return ""
    m = SSD_EXPLICIT_RE.search(title)
    if m:
        return normalize_storage(m.group(1), m.group(2))
    best: Tuple[float, str] = (0.0, "")
    for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*(TB|GB)\b", title, re.IGNORECASE):
        num = m.group(1)
        unit = m.group(2).upper()
        context = title[max(0, m.start() - 12) : m.end() + 12].lower()
        if any(k in context for k in ("ram", "ddr", "lpddr")):
            continue
        val = 0.0
        try:
            val = float(num.replace(",", "."))
        except ValueError:
            continue
        if unit == "TB":
            val *= 1024
        if val > best[0]:
            best = (val, normalize_storage(num, unit))
    return best[1]


def extract_cpu(title: str) -> str:
    if not title:
        return ""
    for pat in CPU_PATTERNS:
        m = pat.search(title)
        if not m:
            continue
        raw = re.sub(r"\s+", " ", m.group(0)).strip()
        low = raw.lower()
        if low.startswith("core ultra"):
            return raw.title().replace("Ultra", "Ultra")
        if "core" in low and "i" in low:
            mi = re.search(r"(i[3579])\s*[-]?\s*(\d{4,5}[A-Z]{0,2})", raw, re.IGNORECASE)
            if mi:
                return f"{mi.group(1).lower()}-{mi.group(2).upper()}"
        if "ryzen" in low:
            return raw.title().replace("Ai", "AI")
        if "intel n" in low:
            m2 = re.search(r"N\d{2,3}", raw, re.IGNORECASE)
            return m2.group(0).upper() if m2 else raw.upper()
        if re.fullmatch(r"N\d{2,3}", raw, re.IGNORECASE):
            return raw.upper()
        if "apple" in low:
            return raw.title()
        return raw
    return ""


def extract_os(title: str) -> str:
    if not title:
        return ""
    for pat, label in OS_PATTERNS:
        if pat.search(title):
            return label
    return ""


def extract_gpu(title: str) -> str:
    if not title:
        return "integrated"
    for pat in GPU_PATTERNS:
        m = pat.search(title)
        if not m:
            continue
        g = re.sub(r"\s+", " ", m.group(0)).strip()
        return g.upper() if g.lower().startswith(("rtx", "gtx", "mx")) else g.title()
    return "integrated"


def extract_from_title(title: str) -> Dict[str, str]:
    return {
        "screen_size": extract_screen_size(title),
        "ram": extract_ram(title),
        "ssd": extract_ssd(title),
        "cpu": extract_cpu(title),
        "os": extract_os(title),
        "gpu": extract_gpu(title),
    }


def extract_json_ld_product(soup: BeautifulSoup) -> Dict:
    scripts = soup.select('script[type="application/ld+json"]')
    for sc in scripts:
        txt = (sc.get_text() or "").strip()
        if not txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") in ("Product", "product"):
                    return item
        elif isinstance(data, dict):
            if data.get("@type") in ("Product", "product"):
                return data
            graph = data.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict) and item.get("@type") in ("Product", "product"):
                        return item
    return {}


def list_page_url(page: int, sort: str = "%3Arelevance") -> str:
    return f"{CATEGORY_LAPTOPS}?page={page}&s={sort}"


def is_laptop_candidate(name: str, url: str) -> bool:
    hay = normalize_text(f"{name} {url}")
    hay_compact = hay.replace(" ", "")
    keywords = ("laptop", "notebook", "dizustu")
    if any(k in hay for k in keywords):
        return True
    return "dizustu" in hay_compact


def parse_list(html: str) -> List[Tuple[str, str, Optional[float]]]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.prd, li.prd, div.product-list-item, div.product-item")
    items: List[Tuple[str, str, Optional[float]]] = []

    for c in cards:
        title = ""
        tnode = c.select_one(".prd-name, .product-name, h3, h4, a[title]")
        if tnode:
            title = tnode.get_text(" ", strip=True)
        if not title:
            img = c.select_one("img[alt]")
            if img and img.get("alt"):
                title = img.get("alt").strip()

        href = None
        a = c.select_one("a[href*='-p-'], a[href^='/'][href*='-p-']")
        if a and a.get("href"):
            href = a.get("href")
        if not href:
            for attr in ("data-url", "data-href", "data-product-url"):
                if c.has_attr(attr):
                    href = c.get(attr)
                    break
        if not href:
            a2 = c.select_one("a[href^='/']")
            if a2 and a2.get("href"):
                href = a2.get("href")

        if not href:
            continue
        product_url = urljoin(BASE, href)

        price = None
        text_blob = c.get_text("\n", strip=True)
        prices = PRICE_RE.findall(text_blob)
        if prices:
            floats = []
            for p in prices:
                f = tr_price_to_float(p + " TL")
                if f is not None:
                    floats.append(f)
            if floats:
                price = min(floats)

        items.append((product_url, title or "", price))

    if not items:
        for a in soup.select("a[href*='-p-']"):
            href = a.get("href")
            if not href:
                continue
            title = a.get_text(" ", strip=True)
            if not title:
                img = a.find("img", alt=True)
                if img:
                    title = img.get("alt", "").strip()
            product_url = urljoin(BASE, href)
            context = a.find_parent()
            price = tr_price_to_float(context.get_text(" ", strip=True) if context else "")
            items.append((product_url, title or "", price))

    seen = set()
    uniq = []
    for u, t, p in items:
        if u in seen:
            continue
        seen.add(u)
        uniq.append((u, t, p))
    return uniq


def parse_product(html: str, url: str, hinted_title: str = "", hinted_price: Optional[float] = None) -> Optional[LaptopRow]:
    soup = BeautifulSoup(html, "lxml")
    name = ""

    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(" ", strip=True)
    if not name:
        ogt = soup.find("meta", {"property": "og:title"})
        if ogt and ogt.get("content"):
            name = ogt["content"].strip()
    if not name:
        name = hinted_title.strip()

    price = hinted_price
    if price is None:
        prod = extract_json_ld_product(soup)
        try:
            offers = prod.get("offers", {})
            if isinstance(offers, list) and offers:
                offers = offers[0]
            if isinstance(offers, dict) and offers.get("price"):
                price = float(str(offers["price"]).replace(",", "."))
        except Exception:
            price = None
    if price is None:
        price = tr_price_to_float(soup.get_text(" ", strip=True))

    if not name and price is None:
        return None

    specs = extract_from_title(name)
    return LaptopRow(
        url=url,
        name=name,
        price=price,
        screen_size=specs["screen_size"],
        ssd=specs["ssd"],
        cpu=specs["cpu"],
        ram=specs["ram"],
        os=specs["os"],
        gpu=specs["gpu"],
    )


def get_sitemap_locs(xml_text: str) -> List[str]:
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    return [loc.text.strip() for loc in root.findall(f".//{ns}loc") if loc.text]

def fetch_requests(
    url: str,
    kind: str,
    cache: Optional[CacheStore],
    limiter: RateLimiter,
    timeout: int,
    retries: int,
) -> FetchResult:
    cached = cache.read(kind, url) if cache else None
    if cached:
        blocked = detect_blocked(cached, None)
        return FetchResult(
            url=url,
            status=None,
            text=cached,
            source="cache",
            from_cache=True,
            html_path=cache._path_for(kind, url, ".html") if cache else None,
            blocked_reason=blocked,
            blocked_path=cache._path_for(kind, url, ".html") if blocked and cache else None,
        )

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    last_err: Optional[str] = None
    for attempt in range(1, retries + 1):
        limiter.wait()
        try:
            resp = session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            last_err = str(exc)
            time.sleep((1.6 ** attempt) + random.uniform(0.0, 0.4))
            continue

        status = resp.status_code
        text = resp.text or ""
        blocked = detect_blocked(text, status)
        if blocked:
            blocked_path = cache.save_blocked(kind, url, text) if cache else None
            return FetchResult(
                url=url,
                status=status,
                text=text,
                source="requests",
                blocked_reason=blocked,
                blocked_path=blocked_path,
            )
        if status == 200 and text:
            html_path = cache.write(kind, url, text) if cache else None
            return FetchResult(
                url=url,
                status=status,
                text=text,
                source="requests",
                html_path=html_path,
            )
        if status in RETRY_STATUSES:
            time.sleep((1.6 ** attempt) + random.uniform(0.0, 0.4))
            continue
        return FetchResult(
            url=url,
            status=status,
            text=text,
            source="requests",
            error=f"http_{status}",
        )

    return FetchResult(
        url=url,
        status=None,
        text=None,
        source="requests",
        error=last_err or "request_failed",
    )


class PlaywrightFetcher:
    def __init__(
        self,
        profile_dir: Path,
        headless: bool,
        cache: Optional[CacheStore],
        limiter: RateLimiter,
        challenge_wait: int,
    ) -> None:
        self.profile_dir = profile_dir
        self.headless = headless
        self.cache = cache
        self.limiter = limiter
        self.challenge_wait = challenge_wait
        self._pw = None
        self._context = None
        self._page = None

    def _ensure(self) -> None:
        if self._context:
            return
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._context = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=self.headless,
            locale="tr-TR",
            user_agent=DEFAULT_HEADERS["User-Agent"],
        )
        self._page = self._context.new_page()
        self._page.set_extra_http_headers({"Accept-Language": DEFAULT_HEADERS["Accept-Language"]})

    def close(self) -> None:
        if self._context:
            self._context.close()
        if self._pw:
            self._pw.stop()
        self._context = None
        self._pw = None
        self._page = None

    def _auto_wait_for_clearance(self) -> Optional[str]:
        start = time.time()
        while time.time() - start < self.challenge_wait:
            time.sleep(2)
            html = self._page.content()
            if not detect_blocked(html, None):
                return html
        return None

    def fetch(self, url: str, kind: str, timeout_ms: int = 60000) -> FetchResult:
        try:
            self._ensure()
        except Exception as exc:
            return FetchResult(url=url, status=None, text=None, source="playwright", error=str(exc))
        self.limiter.wait()
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as exc:
            return FetchResult(url=url, status=None, text=None, source="playwright", error=str(exc))

        html = self._page.content()
        blocked = detect_blocked(html, None)
        if blocked:
            cleared = self._auto_wait_for_clearance()
            if cleared:
                html = cleared
                blocked = None

        if blocked:
            screenshot_path = self.cache.save_screenshot(kind, url) if self.cache else None
            if screenshot_path:
                try:
                    self._page.screenshot(path=str(screenshot_path), full_page=True)
                except Exception:
                    screenshot_path = None

            if not self.headless:
                print("[manual] Challenge detected. Solve it in the opened browser window.")
                resp = input("Press Enter when solved, or type 'abort' to stop: ").strip().lower()
                if resp in ("abort", "q", "quit", "exit"):
                    blocked_path = self.cache.save_blocked(kind, url, html) if self.cache else None
                    return FetchResult(
                        url=url,
                        status=None,
                        text=html,
                        source="playwright",
                        blocked_reason="manual_abort",
                        blocked_path=blocked_path,
                        screenshot_path=screenshot_path,
                    )
                html = self._page.content()
                blocked = detect_blocked(html, None)

        if blocked:
            blocked_path = self.cache.save_blocked(kind, url, html) if self.cache else None
            return FetchResult(
                url=url,
                status=None,
                text=html,
                source="playwright",
                blocked_reason=blocked,
                blocked_path=blocked_path,
                screenshot_path=screenshot_path,
            )

        html_path = self.cache.write(kind, url, html) if self.cache else None
        return FetchResult(
            url=url,
            status=200,
            text=html,
            source="playwright",
            html_path=html_path,
        )


def collect_from_category(
    max_pages: int,
    sort: str,
    cache: Optional[CacheStore],
    limiter: RateLimiter,
    timeout: int,
    retries: int,
    playwright: Optional[PlaywrightFetcher],
    blocked_events: List[BlockedEvent],
) -> Tuple[List[Tuple[str, str, Optional[float]]], bool]:
    items: List[Tuple[str, str, Optional[float]]] = []
    aborted = False

    for page in range(1, max_pages + 1):
        url = list_page_url(page=page, sort=sort)
        res = fetch_requests(url, "list", cache, limiter, timeout, retries)

        if res.blocked_reason:
            blocked_events.append(
                BlockedEvent(
                    step="list",
                    url=url,
                    reason=res.blocked_reason,
                    source=res.source,
                    html_path=res.blocked_path or res.html_path,
                    screenshot_path=res.screenshot_path,
                )
            )
            if playwright:
                res = playwright.fetch(url, kind="list")
                if res.blocked_reason:
                    blocked_events.append(
                        BlockedEvent(
                            step="list",
                            url=url,
                            reason=res.blocked_reason,
                            source=res.source,
                            html_path=res.blocked_path or res.html_path,
                            screenshot_path=res.screenshot_path,
                        )
                    )
                    if res.blocked_reason == "manual_abort":
                        aborted = True
                    break
            else:
                break

        if not res.text:
            print(f"[list] page={page} failed: {url}")
            continue

        parsed = parse_list(res.text)
        print(f"[list] page={page} items={len(parsed)}")
        if not parsed:
            break
        items.extend(parsed)

    return items, aborted

def fetch_robots_sitemaps(
    cache: Optional[CacheStore],
    limiter: RateLimiter,
    timeout: int,
    retries: int,
    blocked_events: Optional[List[BlockedEvent]] = None,
) -> List[str]:
    res = fetch_requests(ROBOTS_URL, "sitemap", cache, limiter, timeout, retries)
    if res.blocked_reason:
        if blocked_events is not None:
            blocked_events.append(
                BlockedEvent(
                    step="robots",
                    url=ROBOTS_URL,
                    reason=res.blocked_reason,
                    source=res.source,
                    html_path=res.blocked_path or res.html_path,
                    screenshot_path=res.screenshot_path,
                )
            )
        return []
    if not res.text:
        return []
    urls = []
    for line in res.text.splitlines():
        if line.lower().startswith("sitemap:"):
            urls.append(line.split(":", 1)[1].strip())
    return urls


def collect_from_sitemap(
    cache: Optional[CacheStore],
    limiter: RateLimiter,
    timeout: int,
    retries: int,
    sitemap_url: str,
    blocked_events: Optional[List[BlockedEvent]] = None,
) -> List[Tuple[str, str, Optional[float]]]:
    sitemap_urls: List[str] = []
    if sitemap_url:
        sitemap_urls = [sitemap_url]
    else:
        sitemap_urls = fetch_robots_sitemaps(cache, limiter, timeout, retries, blocked_events)
        if not sitemap_urls:
            sitemap_urls = [f"{BASE}/siteharitasi.xml", f"{BASE}/sitemap.xml"]

    product_sitemaps: List[str] = []
    for sm in sitemap_urls:
        res = fetch_requests(sm, "sitemap", cache, limiter, timeout, retries)
        if res.blocked_reason:
            if blocked_events is not None:
                blocked_events.append(
                    BlockedEvent(
                        step="sitemap_index",
                        url=sm,
                        reason=res.blocked_reason,
                        source=res.source,
                        html_path=res.blocked_path or res.html_path,
                        screenshot_path=res.screenshot_path,
                    )
                )
            continue
        if not res.text:
            continue
        locs = get_sitemap_locs(res.text)
        for loc in locs:
            if loc.lower().endswith(".xml") and "product" in loc.lower():
                product_sitemaps.append(loc)

    if not product_sitemaps:
        product_sitemaps = [sm for sm in sitemap_urls if "product" in sm.lower()]

    product_urls: List[str] = []
    for sm in product_sitemaps:
        res = fetch_requests(sm, "sitemap", cache, limiter, timeout, retries)
        if res.blocked_reason:
            if blocked_events is not None:
                blocked_events.append(
                    BlockedEvent(
                        step="sitemap_products",
                        url=sm,
                        reason=res.blocked_reason,
                        source=res.source,
                        html_path=res.blocked_path or res.html_path,
                        screenshot_path=res.screenshot_path,
                    )
                )
            continue
        if not res.text:
            continue
        locs = get_sitemap_locs(res.text)
        for loc in locs:
            if PRODUCT_URL_RE.search(loc):
                product_urls.append(loc)

    seen = set()
    uniq = []
    for u in product_urls:
        if u in seen:
            continue
        seen.add(u)
        uniq.append((u, "", None))
    return uniq


def fetch_product_requests(
    url: str,
    hinted_title: str,
    hinted_price: Optional[float],
    cache: Optional[CacheStore],
    limiter: RateLimiter,
    timeout: int,
    retries: int,
    require_laptop: bool,
) -> Tuple[Optional[LaptopRow], Optional[BlockedEvent], str]:
    res = fetch_requests(url, "product", cache, limiter, timeout, retries)
    if res.blocked_reason:
        blocked = BlockedEvent(
            step="product",
            url=url,
            reason=res.blocked_reason,
            source=res.source,
            html_path=res.blocked_path or res.html_path,
            screenshot_path=res.screenshot_path,
        )
        return None, blocked, "blocked"
    if not res.text:
        return None, None, "error"
    row = parse_product(res.text, url=url, hinted_title=hinted_title, hinted_price=hinted_price)
    if not row:
        return None, None, "parse_failed"
    if require_laptop and not is_laptop_candidate(row.name, url):
        return None, None, "not_laptop"
    return row, None, ""


def fetch_product_playwright(
    playwright: PlaywrightFetcher,
    url: str,
    hinted_title: str,
    hinted_price: Optional[float],
    require_laptop: bool,
) -> Tuple[Optional[LaptopRow], Optional[BlockedEvent], str]:
    res = playwright.fetch(url, kind="product")
    if res.blocked_reason:
        blocked = BlockedEvent(
            step="product",
            url=url,
            reason=res.blocked_reason,
            source=res.source,
            html_path=res.blocked_path or res.html_path,
            screenshot_path=res.screenshot_path,
        )
        return None, blocked, "blocked"
    if not res.text:
        return None, None, "error"
    row = parse_product(res.text, url=url, hinted_title=hinted_title, hinted_price=hinted_price)
    if not row:
        return None, None, "parse_failed"
    if require_laptop and not is_laptop_candidate(row.name, url):
        return None, None, "not_laptop"
    return row, None, ""


def write_csv(path: Path, rows: Iterable[LaptopRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["url", "name", "price", "screen_size", "ssd", "cpu", "ram", "os", "gpu"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row.to_csv_row())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", choices=["auto", "category", "sitemap"], default="auto")
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--max-products", type=int, default=0, help="0 means no limit")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--delay", type=float, default=None, help="Fixed delay. Overrides min/max.")
    ap.add_argument("--min-delay", type=float, default=0.6)
    ap.add_argument("--max-delay", type=float, default=1.2)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--sort", type=str, default="%3Arelevance", help="s= param for list pages")
    ap.add_argument("--out", type=str, default="data/teknosa_laptops.csv")
    ap.add_argument("--raw-dir", type=str, default="raw/teknosa_html")
    ap.add_argument("--no-raw", action="store_true", help="Disable raw HTML saving")
    ap.add_argument("--no-cache", action="store_true", help="Disable cache reads")
    ap.add_argument("--profile-dir", type=str, default="raw/teknosa_profile")
    ap.add_argument("--headless", action="store_true", help="Run Playwright headless")
    ap.add_argument("--no-playwright", action="store_true", help="Disable Playwright usage")
    ap.add_argument("--challenge-wait", type=int, default=90)
    ap.add_argument("--sitemap-url", type=str, default="", help="Override sitemap index URL")
    args = ap.parse_args()

    if args.delay is not None:
        min_delay = max(0.2, args.delay)
        max_delay = min_delay
    else:
        min_delay = max(0.2, args.min_delay)
        max_delay = max(min_delay, args.max_delay)

    limiter = RateLimiter(min_delay=min_delay, max_delay=max_delay)

    raw_dir = None if args.no_raw else Path(args.raw_dir)
    cache = None
    if raw_dir:
        cache = CacheStore(raw_dir, read_enabled=not args.no_cache, write_enabled=True)

    playwright: Optional[PlaywrightFetcher] = None
    if not args.no_playwright:
        try:
            import playwright.sync_api  # noqa: F401
        except Exception as exc:
            print(f"[playwright] unavailable: {exc}")
            playwright = None
        else:
            playwright = PlaywrightFetcher(
                profile_dir=Path(args.profile_dir),
                headless=args.headless,
                cache=cache,
                limiter=limiter,
                challenge_wait=args.challenge_wait,
            )

    out_csv = Path(args.out)
    blocked_events: List[BlockedEvent] = []
    seed_used = args.seed

    print("TEKNOSA LAPTOP SCRAPER")
    print(f"seed={args.seed} out={out_csv} workers={args.workers}")

    items: List[Tuple[str, str, Optional[float]]] = []
    aborted = False
    if args.seed in ("auto", "category"):
        items, aborted = collect_from_category(
            max_pages=args.max_pages,
            sort=args.sort,
            cache=cache,
            limiter=limiter,
            timeout=args.timeout,
            retries=args.retries,
            playwright=playwright,
            blocked_events=blocked_events,
        )
        if aborted:
            seed_used = "category"
        if items:
            seed_used = "category"

    if not items and not aborted and args.seed in ("auto", "sitemap"):
        seed_used = "sitemap"
        items = collect_from_sitemap(
            cache=cache,
            limiter=limiter,
            timeout=args.timeout,
            retries=args.retries,
            sitemap_url=args.sitemap_url,
            blocked_events=blocked_events,
        )
        print(f"[sitemap] product urls: {len(items)}")

    if aborted:
        if playwright:
            playwright.close()
        print("[blocked] manual_abort: profile clearance required")
        print_summary(seed_used, 0, blocked_events, rows=[], stats=None)
        return

    if not items:
        if playwright:
            playwright.close()
        print("[list] no product urls found")
        print_summary(seed_used, 0, blocked_events, rows=[], stats=None)
        return

    if args.max_products and len(items) > args.max_products:
        items = items[: args.max_products]

    require_laptop = seed_used == "sitemap"
    rows: List[LaptopRow] = []
    stats = Stats(["name", "price", "screen_size", "ssd", "cpu", "ram", "os", "gpu"])
    blocked_for_playwright: List[Tuple[str, str, Optional[float]]] = []
    skipped_not_laptop = 0
    hints: Dict[str, Tuple[str, Optional[float]]] = {u: (t, p) for u, t, p in items}

    def worker(task: Tuple[str, str, Optional[float]]) -> Tuple[Optional[LaptopRow], Optional[BlockedEvent], str]:
        u, t, p = task
        return fetch_product_requests(
            url=u,
            hinted_title=t,
            hinted_price=p,
            cache=cache,
            limiter=limiter,
            timeout=args.timeout,
            retries=args.retries,
            require_laptop=require_laptop,
        )

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(worker, task) for task in items]
        for fut in as_completed(futures):
            row, blocked, reason = fut.result()
            if blocked:
                blocked_events.append(blocked)
                hint = hints.get(blocked.url, ("", None))
                blocked_for_playwright.append((blocked.url, hint[0], hint[1]))
                continue
            if reason == "not_laptop":
                skipped_not_laptop += 1
                continue
            if row:
                rows.append(row)
                stats.add(row)

    if blocked_for_playwright and playwright:
        print(f"[playwright] retrying blocked products: {len(blocked_for_playwright)}")
        for url, t, p in blocked_for_playwright:
            row, blocked, reason = fetch_product_playwright(
                playwright=playwright,
                url=url,
                hinted_title=t,
                hinted_price=p,
                require_laptop=require_laptop,
            )
            if blocked:
                blocked_events.append(blocked)
                continue
            if reason == "not_laptop":
                skipped_not_laptop += 1
                continue
            if row:
                rows.append(row)
                stats.add(row)

    if playwright:
        playwright.close()

    rows = dedupe_rows(rows)
    write_csv(out_csv, rows)

    print_summary(seed_used, len(items), blocked_events, rows, stats, skipped_not_laptop)


def dedupe_rows(rows: List[LaptopRow]) -> List[LaptopRow]:
    seen = set()
    out: List[LaptopRow] = []
    for row in rows:
        if row.url in seen:
            continue
        seen.add(row.url)
        out.append(row)
    return out


def print_summary(
    seed_used: str,
    product_urls: int,
    blocked_events: List[BlockedEvent],
    rows: List[LaptopRow],
    stats: Optional[Stats],
    skipped_not_laptop: int = 0,
) -> None:
    print("\nSUMMARY")
    print(f"seed_used: {seed_used}")
    print(f"product_urls: {product_urls}")
    print(f"rows_written: {len(rows)}")
    if skipped_not_laptop:
        print(f"skipped_not_laptop: {skipped_not_laptop}")
    if stats:
        completeness = stats.completeness()
        print("column_completeness:")
        for col in ["name", "price", "screen_size", "ssd", "ram", "os", "cpu", "gpu"]:
            print(f"  {col}: {completeness.get(col, 0.0):.1f}%")

    if blocked_events:
        print("\nBLOCKED EVENTS")
        for ev in blocked_events:
            html_path = str(ev.html_path) if ev.html_path else "-"
            shot_path = str(ev.screenshot_path) if ev.screenshot_path else "-"
            print(f"  step={ev.step} source={ev.source} reason={ev.reason}")
            print(f"  url={ev.url}")
            print(f"  html_dump={html_path}")
            print(f"  screenshot={shot_path}")

    if not rows:
        print("\nACTION")
        if any(ev.reason == "manual_abort" for ev in blocked_events):
            print("  Run with --headful and --profile-dir to solve the challenge once.")
        elif seed_used != "sitemap":
            print("  Try --seed sitemap if category pages are blocked.")
        else:
            print("  Check blocked dumps or retry later.")


if __name__ == "__main__":
    main()
