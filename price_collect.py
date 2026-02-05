#!/usr/bin/env python3
"""
Retailer price collector and matcher for laptop catalog.
Outputs offers_raw.jsonl, offers_latest.csv, products_clean.csv, and run_report.json.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import unicodedata

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except Exception:
    BS4_AVAILABLE = False

from laprop.processing import normalize as lap_norm


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PriceCollector/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

BRAND_HINTS = {
    "lenovo",
    "hp",
    "dell",
    "asus",
    "acer",
    "msi",
    "apple",
    "samsung",
    "casper",
    "monster",
    "huawei",
    "lg",
    "toshiba",
    "xiaomi",
}


class WarningCollector:
    def __init__(self) -> None:
        self.messages: List[str] = []

    def add(self, message: str) -> None:
        if message:
            self.messages.append(message)


def strip_accents(text: Optional[str]) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_whitespace(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(str(text).strip().split())


def normalize_label(text: Optional[str]) -> str:
    if not text:
        return ""
    cleaned = strip_accents(text).lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return " ".join(cleaned.split())


def normalize_brand(brand_raw: Optional[str], title_raw: Optional[str]) -> Optional[str]:
    if brand_raw:
        return normalize_label(brand_raw)
    title = normalize_label(title_raw)
    for hint in BRAND_HINTS:
        if hint in title:
            return hint
    return None


def parse_price_try(raw: Optional[str], warnings: WarningCollector, context: str) -> Optional[float]:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.,]", "", str(raw))
    if not cleaned:
        warnings.add(f"{context}: empty price")
        return None
    try:
        if "." in cleaned and "," in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        return float(cleaned)
    except ValueError:
        warnings.add(f"{context}: invalid price '{raw}'")
        return None


def parse_ram_gb(title_raw: str, warnings: WarningCollector) -> Optional[int]:
    return lap_norm.parse_ram_gb(title_raw)


def parse_storage_gb(title_raw: str, warnings: WarningCollector, field_name: str) -> Optional[int]:
    return lap_norm.parse_ssd_gb(title_raw)


def parse_screen_size_inch(title_raw: str, warnings: WarningCollector) -> Optional[float]:
    return lap_norm.parse_screen_size(title_raw)


def normalize_cpu(title_raw: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    brand = normalize_brand(None, title_raw)
    cpu_model = lap_norm.normalize_cpu(title_raw, brand)
    return None, None, cpu_model


def _infer_gpu_vendor(model: str) -> Optional[str]:
    if not model:
        return None
    lowered = strip_accents(model).lower()
    if lowered.startswith("rtx") or lowered.startswith("gtx") or lowered.startswith("mx"):
        return "nvidia"
    if lowered.startswith("rx") or lowered.startswith("radeon"):
        return "amd"
    if lowered.startswith("arc") or lowered.startswith("iris") or lowered.startswith("intel"):
        return "intel"
    if "apple" in lowered or lowered.startswith("m"):
        return "apple"
    return None


def normalize_gpu(title_raw: str) -> Tuple[Optional[str], Optional[str]]:
    brand = normalize_brand(None, title_raw)
    gpu_model = lap_norm.normalize_gpu(title_raw, brand)
    return _infer_gpu_vendor(gpu_model or ""), gpu_model


def build_model_key(features: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    brand = normalize_label(features.get("brand_norm"))
    model = normalize_label(features.get("model_family_raw"))
    if not brand or not model:
        weak = f"{brand}::{model}".strip(":") or None
        return None, weak
    parts = [
        brand,
        model,
        normalize_label(features.get("cpu_model_norm")),
        normalize_label(features.get("gpu_model_norm")),
        str(features.get("ram_gb") or ""),
        str(features.get("storage_ssd_gb") or ""),
        str(features.get("screen_size_inch") or ""),
    ]
    strong = "::".join(p for p in parts if p)
    weak = f"{brand}::{model}"
    return strong or None, weak or None

SOURCE_CONFIG = {
    "amazon": {
        "base": "https://www.amazon.com.tr",
        "search": "https://www.amazon.com.tr/s?k={query}",
    },
    "mediamarkt": {
        "base": "https://www.mediamarkt.com.tr",
        "search": "https://www.mediamarkt.com.tr/tr/search.html?query={query}",
    },
    "vatan": {
        "base": "https://www.vatanbilgisayar.com",
        "search": "https://www.vatanbilgisayar.com/arama/{query}/",
    },
    "incehesap": {
        "base": "https://www.incehesap.com",
        "search": "https://www.incehesap.com/arama/{query}/",
    },
    "inche": {
        "base": "https://www.incehesap.com",
        "search": "https://www.incehesap.com/arama/{query}/",
    },
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


class JsonFormatter(logging.Formatter):
    STANDARD_ATTRS = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
    }

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in self.STANDARD_ATTRS:
                continue
            data[key] = value
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging(log_level: str, log_path: str) -> logging.Logger:
    ensure_dir(os.path.dirname(log_path))
    logger = logging.getLogger("price_collect")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers = []
    formatter = JsonFormatter()
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


class RateLimiter:
    def __init__(self, rps: float) -> None:
        self.min_interval = 1.0 / rps if rps and rps > 0 else 0.0
        self.lock = threading.Lock()
        self.next_time = time.monotonic()

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        sleep_time = 0.0
        with self.lock:
            now = time.monotonic()
            if now < self.next_time:
                sleep_time = self.next_time - now
                self.next_time += self.min_interval
            else:
                self.next_time = now + self.min_interval
        if sleep_time > 0:
            time.sleep(sleep_time)


class SimpleHttpClient:
    def __init__(
        self,
        rate_limit_rps: float,
        timeout_s: int,
        retry_max: int,
        backoff_base: float,
        user_agent: Optional[str],
        logger: logging.Logger,
    ) -> None:
        self.rate_limiter = RateLimiter(rate_limit_rps)
        self.timeout_s = timeout_s
        self.retry_max = retry_max
        self.backoff_base = backoff_base
        self.user_agent = user_agent or DEFAULT_HEADERS["User-Agent"]
        self.logger = logger
        self._session = requests.Session()
        retry = Retry(
            total=self.retry_max,
            backoff_factor=self.backoff_base,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    def _headers(self, referer: Optional[str]) -> Dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        headers["User-Agent"] = self.user_agent
        if referer:
            headers["Referer"] = referer
        return headers

    def get(self, url: str, referer: Optional[str] = None) -> Tuple[Optional[str], Optional[int]]:
        for attempt in range(self.retry_max + 1):
            self.rate_limiter.wait()
            try:
                resp = self._session.get(url, headers=self._headers(referer), timeout=self.timeout_s)
            except requests.RequestException as exc:
                backoff = self.backoff_base ** attempt
                self.logger.warning("request_error", extra={"url": url, "error": str(exc), "backoff_s": backoff})
                time.sleep(backoff)
                continue
            if resp.status_code == 200:
                return resp.text, resp.status_code
            if resp.status_code in {403, 429}:
                return resp.text, resp.status_code
            if resp.status_code >= 500:
                backoff = self.backoff_base ** attempt
                self.logger.warning(
                    "server_error",
                    extra={"url": url, "status": resp.status_code, "backoff_s": backoff},
                )
                time.sleep(backoff)
                continue
            return resp.text, resp.status_code
        return None, None


class RobotsManager:
    def __init__(self, client: SimpleHttpClient, mode: str = "strict") -> None:
        self.client = client
        self.mode = mode
        self.cache: Dict[str, Tuple[float, List[str]]] = {}
        self.ttl_s = 24 * 3600

    def _fetch_robots(self, domain: str) -> Optional[List[str]]:
        url = f"https://{domain}/robots.txt"
        text, status = self.client.get(url, referer=f"https://{domain}/")
        if not text or status != 200:
            return None
        disallow = []
        current_agent = None
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("user-agent"):
                current_agent = line.split(":", 1)[1].strip().lower()
                continue
            if line.lower().startswith("disallow") and (current_agent in (None, "*")):
                path = line.split(":", 1)[1].strip()
                if path:
                    disallow.append(path)
        return disallow

    def is_allowed(self, url: str) -> bool:
        if self.mode == "skip":
            return True
        parsed = urlparse(url)
        domain = parsed.netloc
        now = time.time()
        cached = self.cache.get(domain)
        if cached and now - cached[0] < self.ttl_s:
            disallow = cached[1]
        else:
            disallow = self._fetch_robots(domain)
            if disallow is None:
                return False
            self.cache[domain] = (now, disallow)
        path = parsed.path or "/"
        for rule in disallow:
            if rule == "/":
                return False
            if path.startswith(rule):
                return False
        return True


def extract_price_text(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)\s*(?:TL|\u20ba)", text)
    if not match:
        return None
    return f"{match.group(1)} TL"


def parse_price_value(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    warnings = WarningCollector()
    return parse_price_try(raw, warnings, "price_collect")


def parse_html(text: str) -> Any:
    if not BS4_AVAILABLE:
        raise RuntimeError("beautifulsoup4 is required for price parsing")
    return BeautifulSoup(text, "html.parser")


def is_laptop_title(text: str) -> bool:
    lowered = strip_accents(text).lower()
    return any(keyword in lowered for keyword in ["laptop", "notebook", "dizustu", "dizustu", "notebook"])


def parse_amazon(html_text: str, base_url: str, max_results: int) -> List[Dict[str, Any]]:
    soup = parse_html(html_text)
    offers: List[Dict[str, Any]] = []
    for item in soup.select("div.s-result-item"):
        title_el = item.select_one("h2 a span")
        link_el = item.select_one("h2 a")
        if not title_el or not link_el:
            continue
        title = normalize_whitespace(title_el.get_text(" ", strip=True))
        if not title:
            continue
        price_text = None
        price_offscreen = item.select_one("span.a-offscreen")
        if price_offscreen:
            price_text = price_offscreen.get_text(strip=True)
        else:
            whole = item.select_one("span.a-price-whole")
            frac = item.select_one("span.a-price-fraction")
            if whole:
                frac_text = frac.get_text(strip=True) if frac else "00"
                price_text = f"{whole.get_text(strip=True)},{frac_text} TL"
        price_try = parse_price_value(price_text)
        url = urljoin(base_url, link_el.get("href"))
        offers.append(
            {
                "offer_url": url,
                "title_raw": title,
                "price_try": price_try,
                "seller_raw": None,
                "in_stock": None,
            }
        )
        if len(offers) >= max_results:
            break
    return offers


def parse_generic(html_text: str, base_url: str, max_results: int) -> List[Dict[str, Any]]:
    soup = parse_html(html_text)
    offers: List[Dict[str, Any]] = []
    for link in soup.find_all("a", href=True):
        title = normalize_whitespace(link.get_text(" ", strip=True))
        if len(title) < 10:
            continue
        if not is_laptop_title(title):
            continue
        parent = link.parent
        context_text = normalize_whitespace(parent.get_text(" ", strip=True)) if parent else title
        price_raw = extract_price_text(context_text)
        if not price_raw:
            continue
        url = urljoin(base_url, link["href"])
        price_try = parse_price_value(price_raw)
        in_stock = None
        stock_text = strip_accents(context_text).lower()
        if "stokta yok" in stock_text or "tukendi" in stock_text:
            in_stock = False
        offers.append(
            {
                "offer_url": url,
                "title_raw": title,
                "price_try": price_try,
                "seller_raw": None,
                "in_stock": in_stock,
            }
        )
        if len(offers) >= max_results:
            break
    return offers


def build_search_query(entry: Dict[str, Any]) -> Optional[str]:
    parts: List[str] = []
    brand = entry.get("brand_norm")
    model = entry.get("model_family_raw") or entry.get("title_raw")
    if brand:
        parts.append(brand)
    if model:
        parts.append(model)
    cpu = entry.get("cpu_model_norm")
    gpu = entry.get("gpu_model_norm")
    if cpu:
        parts.append(cpu)
    if gpu:
        parts.append(gpu)
    if entry.get("ram_gb"):
        parts.append(f'{entry.get("ram_gb")} GB')
    if entry.get("storage_ssd_gb"):
        parts.append(f'{entry.get("storage_ssd_gb")} GB')
    if entry.get("screen_size_inch"):
        parts.append(f'{entry.get("screen_size_inch")} inch')
    query = normalize_whitespace(" ".join(parts))
    return query or None


def derive_model_family(title_raw: str, brand_norm: Optional[str]) -> Optional[str]:
    text = strip_accents(title_raw).lower()
    if brand_norm:
        brand_token = strip_accents(brand_norm).lower()
        text = re.sub(rf"\b{re.escape(brand_token)}\b", " ", text)
    text = re.sub(r"\b\d{1,3}\s*(gb|tb)\b", " ", text)
    text = re.sub(r"\b(i[3579]-?\d+|ultra\s*\d+|ryzen\s*\d+|m[1-9]\w*)\b", " ", text)
    text = re.sub(r"\b(rtx\s*\d+|gtx\s*\d+|rx\s*\d+|iris\s*xe|uhd\s*graphics)\b", " ", text)
    text = re.sub(r"\b(inc|inch|hz|ips|oled|freedos|windows|linux|macos)\b", " ", text)
    text = normalize_whitespace(text)
    tokens = text.split()[:4]
    return " ".join(tokens) if tokens else None


def tokenize(text: Optional[str]) -> set:
    if not text:
        return set()
    cleaned = strip_accents(text).lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return {token for token in cleaned.split() if len(token) >= 2}


def gpu_tier(model: Optional[str]) -> Optional[Tuple[str, int]]:
    if not model:
        return None
    match = re.search(r"(rtx|gtx|rx)\s*(\d{3,4})", strip_accents(model).lower())
    if not match:
        return None
    return match.group(1), int(match.group(2))


def extract_offer_features(title_raw: str) -> Dict[str, Any]:
    brand = normalize_brand(None, title_raw)
    cpu_brand, cpu_series, cpu_model = normalize_cpu(title_raw)
    gpu_vendor, gpu_model = normalize_gpu(title_raw)
    warnings = WarningCollector()
    ram_gb = parse_ram_gb(title_raw, warnings)
    ssd_gb = parse_storage_gb(title_raw, warnings, "storage_ssd_gb")
    screen_inch = parse_screen_size_inch(title_raw, warnings)
    model_family = derive_model_family(title_raw, brand)
    return {
        "brand_norm": brand,
        "model_family_raw": model_family,
        "title_raw": title_raw,
        "cpu_model_norm": cpu_model,
        "gpu_model_norm": gpu_model,
        "ram_gb": ram_gb,
        "storage_ssd_gb": ssd_gb,
        "screen_size_inch": screen_inch,
    }


def score_candidate(offer_feat: Dict[str, Any], candidate: Dict[str, Any]) -> Tuple[float, str]:
    score = 0.0
    reasons: List[str] = []
    offer_brand = offer_feat.get("brand_norm")
    cand_brand = candidate.get("brand_norm")
    if offer_brand and cand_brand and normalize_label(offer_brand) == normalize_label(cand_brand):
        score += 0.2
        reasons.append("brand")
    offer_model_tokens = tokenize(offer_feat.get("model_family_raw") or offer_feat.get("title_raw"))
    cand_model_tokens = tokenize(candidate.get("model_family_raw") or candidate.get("title_raw"))
    if cand_model_tokens:
        overlap = len(offer_model_tokens & cand_model_tokens) / max(1, len(cand_model_tokens))
        if overlap > 0:
            score += 0.25 * overlap
            reasons.append("model_overlap")
    offer_cpu = offer_feat.get("cpu_model_norm")
    cand_cpu = candidate.get("cpu_model_norm")
    if offer_cpu and cand_cpu and tokenize(offer_cpu) & tokenize(cand_cpu):
        score += 0.15
        reasons.append("cpu")
    offer_gpu = offer_feat.get("gpu_model_norm")
    cand_gpu = candidate.get("gpu_model_norm")
    if offer_gpu and cand_gpu and tokenize(offer_gpu) & tokenize(cand_gpu):
        score += 0.15
        reasons.append("gpu")
    if offer_feat.get("ram_gb") and candidate.get("ram_gb"):
        if offer_feat["ram_gb"] == candidate["ram_gb"]:
            score += 0.1
            reasons.append("ram")
        else:
            score -= 0.05
    if offer_feat.get("storage_ssd_gb") and candidate.get("storage_ssd_gb"):
        if offer_feat["storage_ssd_gb"] == candidate["storage_ssd_gb"]:
            score += 0.1
            reasons.append("ssd")
        else:
            score -= 0.05
    offer_tier = gpu_tier(offer_gpu)
    cand_tier = gpu_tier(cand_gpu)
    if offer_tier and cand_tier and offer_tier[0] == cand_tier[0] and offer_tier[1] != cand_tier[1]:
        score -= 0.2
        reasons.append("gpu_conflict")
    score = max(0.0, min(1.0, score))
    reason = "+".join(reasons) if reasons else "no_signal"
    return score, reason


def match_offer(
    offer: Dict[str, Any],
    catalog_by_key: Dict[str, Dict[str, Any]],
    catalog_by_weak: Dict[str, List[Dict[str, Any]]],
    catalog_by_brand: Dict[str, List[Dict[str, Any]]],
    threshold: float,
) -> Tuple[Optional[str], List[Dict[str, Any]], bool]:
    features = extract_offer_features(offer["title_raw"])
    model_key_guess, model_key_weak = build_model_key(features)
    offer["model_key_guess"] = model_key_guess or model_key_weak
    if model_key_guess and model_key_guess in catalog_by_key:
        return model_key_guess, [
            {
                "catalog_model_key": model_key_guess,
                "match_score": 1.0,
                "reason": "exact_model_key",
            }
        ], False

    candidates = []
    pool = []
    if model_key_weak and model_key_weak in catalog_by_weak:
        pool = catalog_by_weak[model_key_weak]
        if len(pool) == 1:
            only = pool[0]
            return only.get("model_key"), [
                {
                    "catalog_model_key": only.get("model_key"),
                    "match_score": 0.85,
                    "reason": "exact_model_key_weak",
                }
            ], False
    elif features.get("brand_norm") and features["brand_norm"] in catalog_by_brand:
        pool = catalog_by_brand[features["brand_norm"]]
    else:
        pool = list(catalog_by_key.values())[:200]

    for cand in pool[:200]:
        score, reason = score_candidate(features, cand)
        candidates.append(
            {
                "catalog_model_key": cand.get("model_key"),
                "match_score": round(score, 3),
                "reason": reason,
            }
        )
    candidates.sort(key=lambda x: x["match_score"], reverse=True)
    top = candidates[:5]
    matched = None
    ambiguous = False
    if top:
        if top[0]["match_score"] >= threshold:
            matched = top[0]["catalog_model_key"]
            if len(top) > 1 and top[1]["match_score"] >= threshold and abs(top[0]["match_score"] - top[1]["match_score"]) < 0.05:
                ambiguous = True
    return matched, top, ambiguous


def load_catalog(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not record.get("model_key"):
                model_key, model_key_weak = build_model_key(record)
                record["model_key"] = model_key
                record["model_key_weak"] = model_key_weak
            records.append(record)
    return records


def write_jsonl(path: str, records: Iterable[Dict[str, Any]]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: str, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            cleaned = {k: ("" if row.get(k) is None else row.get(k)) for k in fieldnames}
            writer.writerow(cleaned)


def build_offers_latest(offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for offer in offers:
        key = (offer.get("matched_model_key"), offer.get("source"))
        if not key[0] or offer.get("price_try") is None:
            continue
        current = best.get(key)
        if current is None or offer["price_try"] < current["price_try"]:
            best[key] = offer
    rows: List[Dict[str, Any]] = []
    for offer in best.values():
        rows.append(
            {
                "matched_model_key": offer.get("matched_model_key"),
                "snapshot_at": offer.get("scraped_at"),
                "source": offer.get("source"),
                "seller_raw": offer.get("seller_raw"),
                "price_try": offer.get("price_try"),
                "offer_url": offer.get("offer_url"),
                "in_stock": offer.get("in_stock"),
            }
        )
    return rows


def build_products_clean(catalog: List[Dict[str, Any]], offers_latest: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best_by_key: Dict[str, Dict[str, Any]] = {}
    for offer in offers_latest:
        key = offer.get("matched_model_key")
        if not key or offer.get("price_try") is None:
            continue
        current = best_by_key.get(key)
        if current is None or offer["price_try"] < current["price_try"]:
            best_by_key[key] = offer

    rows: List[Dict[str, Any]] = []
    for entry in catalog:
        model_key = entry.get("model_key")
        best_offer = best_by_key.get(model_key)
        rows.append(
            {
                "model_key": model_key,
                "model_key_weak": entry.get("model_key_weak"),
                "best_price_try": best_offer.get("price_try") if best_offer else None,
                "best_source": best_offer.get("source") if best_offer else None,
                "best_offer_url": best_offer.get("offer_url") if best_offer else None,
                "snapshot_at": best_offer.get("snapshot_at") if best_offer else None,
                "brand_norm": entry.get("brand_norm"),
                "model_family_raw": entry.get("model_family_raw"),
                "cpu_model_norm": entry.get("cpu_model_norm"),
                "gpu_model_norm": entry.get("gpu_model_norm"),
                "ram_gb": entry.get("ram_gb"),
                "storage_ssd_gb": entry.get("storage_ssd_gb"),
                "screen_size_inch": entry.get("screen_size_inch"),
                "screen_resolution_px": entry.get("screen_resolution_px"),
                "os_norm": entry.get("os_norm"),
                "title_raw": entry.get("title_raw"),
                "epey_url": entry.get("epey_url"),
                "epey_slug": entry.get("epey_slug"),
            }
        )
    return rows


def run_collect(args: argparse.Namespace) -> None:
    output_dir = args.output_dir or "data"
    ensure_dir(output_dir)
    log_path = os.path.join("logs", "run.log")
    logger = setup_logging(args.log_level, log_path)
    if not BS4_AVAILABLE:
        print("beautifulsoup4 not installed. Install with: pip install beautifulsoup4")
        logger.error("bs4_missing")
        return
    catalog = load_catalog(args.catalog_path)
    if not catalog:
        logger.warning("catalog_missing_or_empty", extra={"path": args.catalog_path})
        return

    catalog_by_key = {entry.get("model_key"): entry for entry in catalog if entry.get("model_key")}
    catalog_by_weak: Dict[str, List[Dict[str, Any]]] = {}
    catalog_by_brand: Dict[str, List[Dict[str, Any]]] = {}
    for entry in catalog:
        weak = entry.get("model_key_weak")
        if weak:
            catalog_by_weak.setdefault(weak, []).append(entry)
        brand = entry.get("brand_norm")
        if brand:
            catalog_by_brand.setdefault(brand, []).append(entry)

    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    sources = [s for s in sources if s in SOURCE_CONFIG]
    if not sources:
        logger.warning("no_sources_selected")
        return

    client = SimpleHttpClient(
        rate_limit_rps=args.rate_limit_rps,
        timeout_s=args.timeout_s,
        retry_max=args.retry_max,
        backoff_base=args.backoff_base,
        user_agent=args.user_agent,
        logger=logger,
    )
    robots = RobotsManager(client, mode=args.robots_mode)

    offers_raw: List[Dict[str, Any]] = []
    unmatched_samples: List[Dict[str, Any]] = []
    ambiguous_samples: List[Dict[str, Any]] = []
    stats_lock = threading.Lock()
    offers_lock = threading.Lock()
    per_source: Dict[str, Dict[str, int]] = {
        src: {"attempted": 0, "fetched": 0, "blocked": 0, "offers_found": 0, "errors": 0}
        for src in sources
    }

    def fetch_for_entry(source: str, entry: Dict[str, Any]) -> None:
        query = build_search_query(entry)
        if not query:
            return
        search_url = SOURCE_CONFIG[source]["search"].format(query=quote_plus(query))
        base = SOURCE_CONFIG[source]["base"]
        with stats_lock:
            per_source[source]["attempted"] += 1
        if not robots.is_allowed(search_url):
            with stats_lock:
                per_source[source]["blocked"] += 1
            logger.warning("robots_blocked", extra={"source": source, "url": search_url})
            return
        html_text, status = client.get(search_url, referer=base)
        if status in {403, 429}:
            with stats_lock:
                per_source[source]["blocked"] += 1
            logger.warning("blocked", extra={"source": source, "url": search_url, "status": status})
            return
        if not html_text:
            with stats_lock:
                per_source[source]["errors"] += 1
            return
        with stats_lock:
            per_source[source]["fetched"] += 1
        try:
            if source == "amazon":
                found = parse_amazon(html_text, base, args.max_results)
            else:
                found = parse_generic(html_text, base, args.max_results)
        except Exception as exc:
            with stats_lock:
                per_source[source]["errors"] += 1
            logger.warning("parse_failed", extra={"source": source, "error": str(exc)})
            return
        with stats_lock:
            per_source[source]["offers_found"] += len(found)
        for offer in found:
            offer["source"] = source
            offer["scraped_at"] = now_iso()
            with offers_lock:
                offers_raw.append(offer)

    tasks: List[Tuple[str, Dict[str, Any]]] = []
    for entry in catalog:
        for source in sources:
            tasks.append((source, entry))

    if args.workers > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            list(executor.map(lambda t: fetch_for_entry(*t), tasks))
    else:
        for task in tasks:
            fetch_for_entry(*task)

    matched_count = 0
    for offer in offers_raw:
        matched_key, candidates, ambiguous = match_offer(
            offer,
            catalog_by_key,
            catalog_by_weak,
            catalog_by_brand,
            args.match_threshold,
        )
        offer["match_candidates"] = candidates
        offer["matched_model_key"] = matched_key
        if matched_key:
            matched_count += 1
        else:
            if len(unmatched_samples) < 10:
                unmatched_samples.append(offer)
        if ambiguous and len(ambiguous_samples) < 10:
            ambiguous_samples.append(offer)

    offers_path = os.path.join(output_dir, "offers_raw.jsonl")
    write_jsonl(offers_path, offers_raw)
    logger.info("output_written", extra={"path": offers_path, "records": len(offers_raw)})

    offers_latest = build_offers_latest(offers_raw)
    offers_latest_path = os.path.join(output_dir, "offers_latest.csv")
    write_csv(
        offers_latest_path,
        offers_latest,
        [
            "matched_model_key",
            "snapshot_at",
            "source",
            "seller_raw",
            "price_try",
            "offer_url",
            "in_stock",
        ],
    )
    logger.info("output_written", extra={"path": offers_latest_path, "records": len(offers_latest)})

    products_clean = build_products_clean(catalog, offers_latest)
    products_clean_path = os.path.join(output_dir, "products_clean.csv")
    write_csv(
        products_clean_path,
        products_clean,
        [
            "model_key",
            "model_key_weak",
            "best_price_try",
            "best_source",
            "best_offer_url",
            "snapshot_at",
            "brand_norm",
            "model_family_raw",
            "cpu_model_norm",
            "gpu_model_norm",
            "ram_gb",
            "storage_ssd_gb",
            "screen_size_inch",
            "screen_resolution_px",
            "os_norm",
            "title_raw",
            "epey_url",
            "epey_slug",
        ],
    )
    logger.info("output_written", extra={"path": products_clean_path, "records": len(products_clean)})

    offers_count = len(offers_raw)
    match_rate = matched_count / offers_count if offers_count else 0.0
    per_source_report = {}
    for source, stats in per_source.items():
        attempted = stats["attempted"]
        fetched = stats["fetched"]
        offers_found = stats["offers_found"]
        per_source_report[source] = {
            "attempted": attempted,
            "fetched": fetched,
            "blocked": stats["blocked"],
            "offers_found": offers_found,
            "errors": stats["errors"],
            "success_rate": offers_found / fetched if fetched else 0.0,
        }

    report = {
        "catalog_count": len(catalog),
        "offers_count": offers_count,
        "match_rate": match_rate,
        "unmatched_offers_sample": unmatched_samples,
        "ambiguous_matches_sample": ambiguous_samples,
        "per_source": per_source_report,
        "recommended_next_steps": (
            "Run a focused rerun with a lower threshold if matching is weak: "
            "python price_collect.py --sources amazon,mediamarkt,vatan,incehesap --out data --match-threshold 0.7"
        ),
    }
    report_path = os.path.join(output_dir, "run_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    logger.info("output_written", extra={"path": report_path})


def build_arg_parser() -> argparse.ArgumentParser:
    epilog = (
        "Examples (PowerShell):\n"
        "  python price_collect.py --sources amazon,mediamarkt,vatan,incehesap --out data\n"
        "  python price_collect.py --sources amazon --out data --rate 0.5 --workers 1\n"
        "  python price_collect.py --catalog data/catalog.jsonl --out data\n"
    )
    parser = argparse.ArgumentParser(
        description="Retailer price collector for laptop catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument("--catalog", dest="catalog_path", default="data/catalog.jsonl")
    parser.add_argument("--sources", default="amazon,mediamarkt,vatan,incehesap")
    parser.add_argument("--out", dest="output_dir", default="data")
    parser.add_argument("--rate", dest="rate_limit_rps", type=float, default=0.5)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout-s", dest="timeout_s", type=int, default=20)
    parser.add_argument("--retry-max", dest="retry_max", type=int, default=2)
    parser.add_argument("--backoff-base", dest="backoff_base", type=float, default=1.5)
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--match-threshold", type=float, default=0.75)
    parser.add_argument("--robots-mode", choices=["strict", "skip"], default="strict")
    parser.add_argument("--user-agent", default=None)
    parser.add_argument("--log-level", default="INFO")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    run_collect(args)


if __name__ == "__main__":
    main()
