import re
from typing import Any, List, Tuple

import numpy as np
import pandas as pd

from .normalize import (
    _normalize_title_text,
    _normalize_capacity_gb,
    _coerce_int,
    _is_valid_ssd_value,
    _pick_best_ssd,
    _find_larger_ssd_in_title,
    parse_ram_gb,
    sanitize_ram,
    parse_ssd_gb,
    parse_screen_size,
    normalize_cpu,
    normalize_gpu,
    SSD_COMMON_GB,
    SSD_TINY_GB,
    SSD_FORM_FACTOR_GB,
    SSD_MIN_GB,
    SSD_MAX_GB,
    RAM_STORAGE_SWAP_GB,
)
from .validate import validate_record
from .read import _standardize_columns
from ..recommend.engine import get_cpu_score, get_gpu_score, gpu_normalize_and_score
from ..utils.logging import get_logger

logger = get_logger(__name__)

def clean_ram_value(ram_str):
    """RAM değerini düzgün temizle"""
    if pd.isna(ram_str):
        return 8

    ram_str = str(ram_str).upper()

    # Önce parantez içindeki değerleri kontrol et
    match = re.search(r'\((\d+)\s*GB\)', ram_str)
    if match:
        return int(match.group(1))

    # Normal pattern
    numbers = re.findall(r'(\d+)\s*GB', ram_str)
    if numbers:
        # En büyük değeri al (bazen "8GB + 8GB = 16GB" gibi yazılıyor)
        return max(int(n) for n in numbers)

    # Sadece sayı varsa
    numbers = re.findall(r'\d+', ram_str)
    if numbers:
        num = int(numbers[0])
        # Mantıklı RAM değerleri: 4, 8, 12, 16, 24, 32, 48, 64
        if num in [4, 8, 12, 16, 24, 32, 48, 64, 128]:
            return num

    return 8  # Varsayılan

def clean_ssd_value(storage_str):
    """SSD degerini duzgun temizle"""
    if pd.isna(storage_str):
        return np.nan

    s = _normalize_title_text(storage_str)
    if not s:
        return np.nan

    # Düz sayı girişi (kolon verisinde "512" gibi)
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        gb_val = _normalize_capacity_gb(float(s))
        gb_int = _coerce_int(gb_val)
        return gb_int if _is_valid_ssd_value(gb_int) else np.nan

    # Ortak aday-skorlama mantığına delege et
    result = _pick_best_ssd(s)
    return result if result is not None else np.nan

def clean_price(price_str):
    """Fiyat temizleme"""
    if pd.isna(price_str):
        return None

    if isinstance(price_str, (int, float)):
        return int(price_str)

    price_str = str(price_str)
    price_str = re.sub(r'[^\d]', '', price_str)

    try:
        price = int(price_str)
        if price < 1000 or price > 500000:
            return None
        return price
    except (ValueError, TypeError):
        return None

def extract_brand(name):
    """İsimden marka çıkar"""
    if pd.isna(name):
        return 'other'

    name_lower = str(name).lower()

    # Öncelik sırasına göre kontrol
    brand_keywords = {
        'apple': ['apple', 'macbook', 'mac '],
        'lenovo': ['lenovo', 'thinkpad', 'ideapad', 'yoga', 'legion'],
        'asus': ['asus', 'rog', 'zenbook', 'vivobook', 'tuf'],
        'dell': ['dell', 'alienware', 'xps', 'inspiron', 'latitude'],
        'hp': ['hp ', 'hewlett', 'omen', 'pavilion', 'elitebook', 'victus', 'omnibook'],
        'msi': ['msi ', 'msi-', 'msi_'],
        'acer': ['acer', 'predator', 'aspire', 'nitro'],
        'microsoft': ['microsoft', 'surface'],
        'huawei': ['huawei', 'matebook'],
        'samsung': ['samsung', 'galaxy book'],
        'monster': ['monster', 'tulpar', 'abra'],
        'casper': ['casper', 'excalibur', 'nirvana'],
    }

    for brand, keywords in brand_keywords.items():
        for keyword in keywords:
            if keyword in name_lower:
                return brand

    return 'other'

def clean_data(df):
    """Veriyi temizle - OS tespiti + başlıktan normalize parsing"""
    logger.info("Veriler temizleniyor...")

    df = _standardize_columns(df)

    # Fiyat temizleme
    if 'price' in df.columns:
        df['price'] = df['price'].apply(clean_price)
    elif 'fiyat' in df.columns:
        df['price'] = df['fiyat'].apply(clean_price)

    # Vatan kategori/placeholder satırları filtrele
    if 'url' in df.columns:
        url_series = df['url'].fillna("").astype(str)
        url_lower = url_series.str.lower()
        vatan_mask = url_lower.str.contains("vatanbilgisayar.com", na=False)
        if vatan_mask.any():
            product_mask = url_lower.str.contains(r"\.html(?:$|[?#])", na=False)
            before = len(df)
            df = df.loc[~vatan_mask | product_mask].copy()
            removed = before - len(df)
            if removed > 0:
                logger.info("Vatan filter: removed %d non-product rows", removed)

    # Marka çıkar
    df['brand'] = df['name'].apply(extract_brand)

    # Başlıktan normalize edilmiş alanlar
    df['cpu'] = df.apply(lambda r: normalize_cpu(r.get('name'), r.get('brand')), axis=1)
    df['gpu'] = df.apply(lambda r: normalize_gpu(r.get('name'), r.get('brand')), axis=1)
    df['gpu'] = df['gpu'].apply(lambda x: "integrated" if pd.isna(x) or str(x).strip() == "" else x)
    title_series = df['name'].fillna('').astype(str)
    ram_from_title = title_series.apply(parse_ram_gb)
    ssd_from_title = title_series.apply(parse_ssd_gb)

    ram_from_col = pd.Series(np.nan, index=df.index)
    if 'ram' in df.columns:
        ram_from_col = df['ram'].apply(
            lambda x: clean_ram_value(x) if pd.notna(x) and re.search(r"\d", str(x)) else np.nan
        )
    df['ram_gb'] = ram_from_title.fillna(ram_from_col)

    ssd_from_col = pd.Series(np.nan, index=df.index)
    if 'ssd' in df.columns:
        ssd_from_col = df['ssd'].apply(
            lambda x: clean_ssd_value(x) if pd.notna(x) and re.search(r"\d", str(x)) else np.nan
        )
        df['ssd_gb'] = ssd_from_col.fillna(ssd_from_title)
    else:
        df['ssd_gb'] = ssd_from_title

    screen_from_col = pd.Series(np.nan, index=df.index)
    if 'screen_size' in df.columns:
        screen_from_col = df['screen_size'].apply(parse_screen_size)
    screen_from_title = title_series.apply(parse_screen_size)
    df['screen_size'] = screen_from_col.fillna(screen_from_title)

    df['ram_gb'] = pd.to_numeric(df['ram_gb'], errors='coerce')
    df['ssd_gb'] = pd.to_numeric(df['ssd_gb'], errors='coerce')
    df['screen_size'] = pd.to_numeric(df['screen_size'], errors='coerce')

    title_ssd_hint = title_series.apply(_find_larger_ssd_in_title)
    ssd_overrides_small_to_large = 0
    ssd_swap_fixes = 0

    small_override_mask = (
        df['ssd_gb'].isin(SSD_TINY_GB)
        & title_ssd_hint.notna()
        & (title_ssd_hint > df['ssd_gb'])
    )
    if small_override_mask.any():
        df.loc[small_override_mask, 'ssd_gb'] = title_ssd_hint[small_override_mask]
        ssd_overrides_small_to_large = int(small_override_mask.sum())

    new_ram = df['ram_gb'].copy()
    new_ssd = df['ssd_gb'].copy()

    def _pick_ram_val(idx):
        for val in (ram_from_col.at[idx], ram_from_title.at[idx]):
            if pd.notna(val) and float(val) <= 128:
                return float(val)
        return np.nan

    def _pick_ssd_val(idx):
        for val in (ssd_from_col.at[idx], ssd_from_title.at[idx], title_ssd_hint.at[idx]):
            if pd.notna(val) and _is_valid_ssd_value(val):
                return float(val)
        return np.nan

    for idx in df.index:
        ram_val = new_ram.at[idx]
        ssd_val = new_ssd.at[idx]
        candidate_ram = _pick_ram_val(idx)
        candidate_ssd = _pick_ssd_val(idx)

        new_ram_val = ram_val
        new_ssd_val = ssd_val

        if (
            pd.notna(ram_val)
            and ram_val > 128
            and (pd.isna(ssd_val) or ssd_val < SSD_MIN_GB or ssd_val in SSD_FORM_FACTOR_GB)
        ):
            if pd.isna(candidate_ssd) and ram_val in SSD_COMMON_GB:
                candidate_ssd = float(ram_val)
            if pd.notna(candidate_ssd):
                new_ssd_val = candidate_ssd
                new_ram_val = candidate_ram if pd.notna(candidate_ram) else np.nan

        if (
            pd.notna(new_ssd_val)
            and int(new_ssd_val) in {8, 16, 32}
            and (pd.isna(new_ram_val) or new_ram_val in RAM_STORAGE_SWAP_GB)
        ):
            swap_target = candidate_ssd
            if pd.notna(new_ram_val) and new_ram_val in RAM_STORAGE_SWAP_GB:
                swap_target = float(new_ram_val)
            if pd.notna(swap_target) and swap_target not in SSD_TINY_GB:
                new_ram_val = new_ssd_val
                new_ssd_val = swap_target

        if new_ram_val != ram_val or new_ssd_val != ssd_val:
            ssd_swap_fixes += 1
            new_ram.at[idx] = new_ram_val
            new_ssd.at[idx] = new_ssd_val

    df['ram_gb'] = new_ram
    df['ssd_gb'] = new_ssd

    implausible_ssd_mask = (
        df['ssd_gb'].isin(SSD_FORM_FACTOR_GB)
        | (df['ssd_gb'] <= 64)
    )
    implausible_ssd_count = int(implausible_ssd_mask.sum())

    invalid_ssd_mask = (
        df['ssd_gb'].isin(SSD_FORM_FACTOR_GB)
        | (df['ssd_gb'] < SSD_MIN_GB)
        | (df['ssd_gb'] > SSD_MAX_GB)
    )
    invalid_ssd_count = int(invalid_ssd_mask.sum())
    df.loc[invalid_ssd_mask, 'ssd_gb'] = np.nan

    df['parse_warnings'] = df.apply(
        lambda r: validate_record(
            r.get('name'),
            r.get('cpu'),
            r.get('gpu'),
            r.get('ram_gb'),
            r.get('ssd_gb'),
            r.get('screen_size'),
        ),
        axis=1,
    )
    df.loc[df['parse_warnings'].apply(lambda x: not x), 'parse_warnings'] = None

    # CPU ve GPU skorlama
    df['cpu_score'] = df['cpu'].apply(get_cpu_score)

    # GPU: tek pass'ta normalize + skor hesapla
    _gpu_pairs = df['gpu'].apply(gpu_normalize_and_score)
    df['gpu_norm'] = _gpu_pairs.apply(lambda t: t[0])
    df['gpu_score'] = _gpu_pairs.apply(lambda t: t[1])

    # OS temizleme
    def detect_os(row):
        """OS'u kolon veya ürün adından tespit et"""
        if 'os' in row.index and pd.notna(row['os']):
            os_str = str(row['os']).lower()
            if any(x in os_str for x in ['windows', 'win11', 'win10', 'w11', 'w10']):
                return 'windows'
            elif any(x in os_str for x in ['mac', 'macos', 'os x']):
                return 'macos'
            elif any(x in os_str for x in ['ubuntu', 'linux', 'debian']):
                return 'linux'
            elif any(x in os_str for x in ['dos', 'free', 'yok', 'none']):
                return 'freedos'

        if 'name' in row.index and pd.notna(row['name']):
            name_lower = str(row['name']).lower()
            if any(x in name_lower for x in ['windows 11', 'win11', 'w11', '/w11', 'windows 10', 'win10']):
                return 'windows'
            elif 'macbook' in name_lower or 'mac ' in name_lower:
                return 'macos'
            elif any(x in name_lower for x in ['freedos', 'free dos', 'fdos', 'dos', '/dos']):
                return 'freedos'

        if 'brand' in row.index and row['brand'] == 'apple':
            return 'macos'

        return 'freedos'

    df['os'] = df.apply(detect_os, axis=1)

    # Kritik kolonları filtrele
    df = df.dropna(subset=['price', 'name'])
    df = df[df['price'] > 5000]

    # Eksik değerleri doldur
    # Eksik RAM/SSD/screen değerleri skor/filtre adımlarında default ile ele alınır.
    df['cpu_score'] = df['cpu_score'].fillna(5.0)
    df['gpu_score'] = df['gpu_score'].fillna(3.0)

    logger.info("Data quality report")
    if 'url' in df.columns:
        def _infer_vendor(url: Any) -> str:
            u = str(url or "").lower()
            if "amazon" in u:
                return "amazon"
            if "vatanbilgisayar.com" in u:
                return "vatan"
            if "incehesap" in u:
                return "incehesap"
            return "other"

        vendor_series = df['url'].apply(_infer_vendor)
    else:
        vendor_series = pd.Series(["unknown"] * len(df), index=df.index)

    for vendor in ("amazon", "vatan", "incehesap", "other", "unknown"):
        mask = vendor_series == vendor
        if not mask.any():
            continue
        total = int(mask.sum())
        screen_missing = df.loc[mask, 'screen_size'].isna().mean() * 100
        ram_missing = df.loc[mask, 'ram_gb'].isna().mean() * 100
        ssd_missing = df.loc[mask, 'ssd_gb'].isna().mean() * 100
        logger.info(
            "  %s: rows=%d, missing screen=%.1f%%, ram=%.1f%%, ssd=%.1f%%",
            vendor, total, screen_missing, ram_missing, ssd_missing,
        )

    logger.info(
        "  implausible_ssd_count=%d, invalid_ssd_count=%d",
        implausible_ssd_count, invalid_ssd_count,
    )
    logger.info(
        "  ssd_overrides_small_to_large=%d, ssd_swap_fixes=%d",
        ssd_overrides_small_to_large, ssd_swap_fixes,
    )

    logger.info("Temizleme tamamlandı: %d laptop", len(df))
    return df
