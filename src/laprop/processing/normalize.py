import re
from typing import Optional, Tuple, List, Any

import numpy as np
import pandas as pd
def normalize_gpu_model(gpu_text: str) -> str:
    """
    Ham GPU metnini ortak bir etikete normalize eder.
    Örnek çıktılar:
      - "GeForce RTX 4060"
      - "GeForce GTX 1650"
      - "NVIDIA MX 550"
      - "Radeon RX 7600M" / "Radeon RX 6600 XT"
      - "Intel Arc A370M"
      - "Intel Iris Xe (iGPU)"
      - "Radeon 780M (iGPU)"
      - "Integrated (generic)"
      - "Discrete GPU (Unknown)"
      - "GPU (Unlabeled)"
    """
    if pd.isna(gpu_text) or str(gpu_text).strip() == "":
        return "Integrated (generic)"

    s = str(gpu_text).lower().strip()

    # =========================
    # 1) NVIDIA GeForce RTX
    # - 'rtx 4060', 'rtx4060', 'rtx-4060', 'geforce rtx 4060 laptop gpu' ...
    # - 'ti/super/max-q' vb. ekleri görmezden gel (isteğe bağlı eklenebilir)
    # =========================
    m = re.search(r'\brtx[\s\-]?(\d{3,4})(?:\s*(ti|super|max\-q|laptop)?)?\b', s)
    if m:
        num = m.group(1)
        return f"GeForce RTX {num}"

    # =========================
    # 2) NVIDIA GeForce GTX
    # - 'gtx 1660', 'gtx-1650', 'gtx1050 ti' vb.
    # =========================
    m = re.search(r'\bgtx[\s\-]?(\d{3,4})(?:\s*(ti|super))?\b', s)
    if m:
        num = m.group(1)
        suf = m.group(2)
        return f"GeForce GTX {num} {suf.upper()}" if suf else f"GeForce GTX {num}"

    # =========================
    # 3) NVIDIA MX
    # - 'mx550', 'mx 350', 'mx-450'
    # =========================
    m = re.search(r'\bmx[\s\-]?(\d{2,3})\b', s)
    if m:
        return f"NVIDIA MX {m.group(1)}"

    # =========================
    # 4) AMD Radeon RX
    # - 'rx 7600', 'rx-7600m', 'rx6600 xt', 'rx 6600xt'
    # =========================
    m = re.search(r'\brx[\s\-]?(\d{3,4})(?:\s*([ms]|xt|xtx))?\b', s.replace(' ', ''))
    if m:
        num = m.group(1)
        suf = m.group(2)
        if suf:
            suf = suf.upper()
            # tek harf (M/S) ise büyük harf, diğerleri XT/ XTX zaten büyük
            return f"Radeon RX {num}{suf}"
        return f"Radeon RX {num}"

    # =========================
    # 5) Intel Arc
    # - 'arc a370m', 'intel arc a750m' ...
    # =========================
    m = re.search(r'\barc[\s\-]?([a-z]?\d{3,4}m?)\b', s)
    if m:
        return f"Intel Arc {m.group(1).upper()}"

    # =========================
    # 6) Apple M serisi (iGPU)
    # - 'm1/m2/m3/m4' (Mac'lerde entegre GPU)
    # =========================
    m = re.search(r'\bm([1-4])\b', s)
    if m:
        return f"Apple M{m.group(1)} GPU"

    # =========================
    # 7) Intel iGPU
    # =========================
    if "iris xe" in s:
        return "Intel Iris Xe (iGPU)"
    if "iris plus" in s:
        return "Intel Iris Plus (iGPU)"
    if "uhd graphics" in s or "hd graphics" in s or re.search(r'\buhd\b', s):
        return "Intel UHD (iGPU)"

    # =========================
    # 8) AMD iGPU (APU tarafı)
    # - 'radeon 780m', '680m', '760m' vb. (iGPU)
    # - 'vega 8/7/6/3' iGPU
    # =========================
    if "radeon graphics" in s:
        return "Radeon Graphics (iGPU)"
    m = re.search(r'radeon\s*(\d{3})m\b', s)  # 780m/680m/760m...
    if m:
        return f"Radeon {m.group(1)}M (iGPU)"
    m = re.search(r'\bvega\s*(8|7|6|3)\b', s)
    if m:
        return f"Radeon Vega {m.group(1)} (iGPU)"

    # =========================
    # 9) Entegre/Genel fallbacks
    # =========================
    if "integrated" in s or "igpu" in s or "apu graphics" in s:
        return "Integrated (generic)"

    # 'nvidia/geforce/radeon' geçiyor ama model bulunamadıysa
    if "geforce" in s or "nvidia" in s or "radeon" in s:
        return "Discrete GPU (Unknown)"

    return "GPU (Unlabeled)"

def _normalize_title_text(text: str) -> str:
    if text is None:
        return ""
    s = str(text).lower()
    s = s.replace("in\u00e7", "inch")
    s = s.replace(",", ".")
    s = re.sub(r"[^\x00-\x7F]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def normalize_cpu(title: str, brand: str) -> Optional[str]:
    """
    Normalize CPU from product title.
    Apple M-series is only detected for Apple/MacBook titles.
    """
    s = _normalize_title_text(title)
    brand_l = (brand or "").lower()

    if brand_l == "apple" or re.search(r"\bmacbook\b|\bapple\b", s):
        m = re.search(r"\bm([1-4])\b(?:\s*(pro|max))?", s)
        if m:
            suffix = m.group(2)
            extra = f" {suffix.title()}" if suffix else ""
            return f"M{m.group(1)}{extra}".strip()

    m = re.search(r"\b(?:core\s*)?ultra\s*([579])\s*-?\s*(\d{3,4}[a-z]{0,2})?\b", s)
    if m:
        tier = m.group(1)
        model = m.group(2)
        return f"Ultra {tier} {model.upper()}".strip() if model else f"Ultra {tier}"

    m = re.search(r"\b(i[3579])[-\s]?(\d{4,5})([a-z]{0,2})\b", s)
    if m:
        prefix = m.group(1).upper()
        num = m.group(2)
        suf = m.group(3).upper()
        return f"{prefix}-{num}{suf}".strip()

    m = re.search(r"\bryzen\s*([3579])\s*-?\s*(\d{4,5})([a-z]{0,2})\b", s)
    if m:
        return f"Ryzen {m.group(1)} {m.group(2)}{m.group(3).upper()}".strip()

    m = re.search(r"\br([3579])\s*-?\s*(\d{4,5})([a-z]{0,2})\b", s)
    if m and "radeon" not in s:
        return f"Ryzen {m.group(1)} {m.group(2)}{m.group(3).upper()}".strip()

    return None

def normalize_gpu(title: str, brand: str) -> Optional[str]:
    """Normalize GPU from product title (no unrelated fallbacks)."""
    s = _normalize_title_text(title)
    compact = re.sub(r"\s+", "", s)

    m = re.search(r"\brtx\s*([0-9]{4})\b", s) or re.search(r"rtx([0-9]{4})", compact)
    if m:
        return f"RTX {m.group(1)}"

    m = re.search(r"\bgtx\s*([0-9]{3,4})\b", s) or re.search(r"gtx([0-9]{3,4})", compact)
    if m:
        return f"GTX {m.group(1)}"

    m = re.search(r"\bmx\s*([0-9]{2,3})\b", s) or re.search(r"mx([0-9]{2,3})", compact)
    if m:
        return f"MX {m.group(1)}"

    m = re.search(r"rx\s*([0-9]{3,4})(m|s|xt|xtx)?\b", s.replace(" ", ""))
    if m:
        num = m.group(1)
        suf = (m.group(2) or "").upper()
        return f"RX {num}{suf}".strip()

    m = re.search(r"\barc\s*([a-z]?\d{3,4}m?)\b", s)
    if m:
        return f"Arc {m.group(1).upper()}"

    if "iris xe" in s:
        return "Iris Xe"
    if "iris plus" in s:
        return "Iris Plus"
    if "uhd" in s:
        return "Intel UHD"
    m = re.search(r"radeon\s*(\d{3})m\b", s)
    if m:
        return f"Radeon {m.group(1)}M"
    if "radeon" in s and "graphics" in s:
        return "Radeon Graphics"

    brand_l = (brand or "").lower()
    if brand_l == "apple" or re.search(r"\bmacbook\b|\bapple\b", s):
        m = re.search(r"\bm([1-4])\b(?:\s*(pro|max))?", s)
        if m:
            suffix = m.group(2)
            extra = f" {suffix.title()}" if suffix else ""
            return f"Apple M{m.group(1)}{extra} GPU"

    return None

SSD_COMMON_GB = {128, 256, 512, 1024, 2048, 3072, 4096}

SSD_TINY_GB = {8, 16, 32, 40, 48, 64}

SSD_FORM_FACTOR_GB = {2242, 2280}

SSD_MIN_GB = 64

SSD_MAX_GB = 8192

RAM_STORAGE_SWAP_GB = {256, 512, 1024}

SSD_ANCHORS = ("ssd", "nvme", "m.2", "m2", "pcie", "pci-e", "depolama", "storage")

RAM_HINTS = ("ram", "ddr", "lpddr")

GPU_HINTS = ("rtx", "gtx", "gddr", "vram", "radeon", "arc", "geforce")

HDD_HINTS = ("hdd", "harddisk", "hard disk")

def _normalize_capacity_gb(gb: int) -> int:
    gb_int = int(round(gb))
    if gb_int == 500:
        return 512
    if gb_int == 1000:
        return 1024
    if gb_int == 2000:
        return 2048
    return gb_int

def _extract_capacity_candidates(text: str) -> List[Tuple[int, int, int]]:
    candidates = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(tb|gb)", text):
        try:
            size_val = float(m.group(1))
        except ValueError:
            continue
        unit = m.group(2)
        gb = int(round(size_val * 1024)) if unit == "tb" else int(round(size_val))
        gb = _normalize_capacity_gb(gb)
        candidates.append((gb, m.start(), m.end()))
    return candidates

def _extract_no_unit_ssd_candidates(text: str) -> List[Tuple[int, int, int]]:
    candidates = []
    for m in re.finditer(
        r"(?<!\d)(\d{1,2})\s*tb\s*(ssd|nvme|m\.2|m2|pcie|pci-e)\b",
        text,
    ):
        gb = _normalize_capacity_gb(int(m.group(1)) * 1024)
        candidates.append((gb, m.start(), m.end()))

    for m in re.finditer(
        r"(?<!\d)(\d{3,4})\s*(?:gb)?\s*(ssd|nvme|m\.2|m2|pcie|pci-e)\b",
        text,
    ):
        gb = _normalize_capacity_gb(int(m.group(1)))
        candidates.append((gb, m.start(), m.end()))

    return candidates

def _window_has_any(window: str, keywords: Tuple[str, ...]) -> bool:
    return any(k in window for k in keywords)

def _score_ssd_candidate(text: str, start: int, end: int, gb: int) -> int:
    window = text[max(0, start - 40): min(len(text), end + 40)]
    score = 0
    if _window_has_any(window, SSD_ANCHORS):
        score += 4
    if "ssd" in window:
        score += 2
    if _window_has_any(window, RAM_HINTS):
        score -= 4
    if _window_has_any(window, GPU_HINTS):
        score -= 3
    if _window_has_any(window, HDD_HINTS):
        score -= 2
    if gb in SSD_COMMON_GB:
        score += 1
    return score

def _coerce_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, float) and np.isnan(value):
            return None
        return int(round(float(value)))
    except Exception:
        return None

def _is_valid_ssd_value(gb: Optional[int]) -> bool:
    gb_int = _coerce_int(gb)
    if gb_int is None:
        return False
    if gb_int in SSD_FORM_FACTOR_GB:
        return False
    if gb_int < SSD_MIN_GB or gb_int > SSD_MAX_GB:
        return False
    return True

def _find_larger_ssd_in_title(title: str) -> Optional[int]:
    s = _normalize_title_text(title)
    if not s:
        return None
    candidates = [
        gb for gb, _, _ in _extract_capacity_candidates(s)
        if gb in SSD_COMMON_GB
    ]
    candidates.extend(
        gb for gb, _, _ in _extract_no_unit_ssd_candidates(s)
        if gb in SSD_COMMON_GB
    )
    if not candidates:
        return None
    return max(candidates)

def parse_ram_gb(title: str) -> Optional[int]:
    s = _normalize_title_text(title).upper()
    if not s:
        return None

    matches = []
    for pattern in (
        r"(\d{1,3})\s*GB\s*(?:RAM|DDR\d|LPDDR\d)",
        r"RAM\s*(\d{1,3})\s*GB",
        r"(?:DDR\d|LPDDR\d)\s*(\d{1,3})\s*GB",
    ):
        for m in re.finditer(pattern, s):
            try:
                matches.append(int(m.group(1)))
            except ValueError:
                continue

    if not matches:
        return None
    val = max(matches)
    return None if val > 128 else val

def sanitize_ram(product) -> float:
    """Final safety filter for RAM values >64GB."""
    s = _normalize_title_text(product.get('name'))
    if not s:
        return 64.0
    valid_vals = {4, 8, 12, 16, 24, 32, 48, 64}
    vram_hints = ("gddr", "vram", "rtx", "radeon", "gpu")
    pattern = r"(\d{1,3})\s*(gb|g)\s*(ram|ddr\d?|lpddr\d?|memory)?"
    matches = []
    for m in re.finditer(pattern, s, flags=re.IGNORECASE):
        try:
            val = int(m.group(1))
        except ValueError:
            continue
        if val not in valid_vals:
            continue
        window = s[max(0, m.start() - 40): min(len(s), m.end() + 40)]
        if any(k in window for k in vram_hints):
            continue
        matches.append(val)
    if matches:
        return float(max(matches))
    return 64.0

def _pick_best_ssd(text: str) -> Optional[int]:
    """
    Ortak SSD aday-skorlama mantığı.
    Normalize edilmiş metinden en iyi SSD GB değerini döndürür.
    parse_ssd_gb() ve clean_ssd_value() tarafından paylaşılır.
    """
    candidates: List[Tuple[int, int]] = []

    for gb, start, end in _extract_capacity_candidates(text):
        if not _is_valid_ssd_value(gb):
            continue
        score = _score_ssd_candidate(text, start, end, gb)
        candidates.append((score, gb))

    for gb, start, end in _extract_no_unit_ssd_candidates(text):
        if gb not in SSD_COMMON_GB:
            continue
        if not _is_valid_ssd_value(gb):
            continue
        score = _score_ssd_candidate(text, start, end, gb) + 3
        candidates.append((score, gb))

    if not candidates:
        return None
    best_score, best_gb = max(candidates, key=lambda x: (x[0], x[1]))
    if best_score <= 0:
        return None
    return best_gb


def parse_ssd_gb(title: str) -> Optional[int]:
    s = _normalize_title_text(title)
    if not s:
        return None
    return _pick_best_ssd(s)

def parse_screen_size(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, (int, float)):
        size = float(value)
        return size if 10.0 <= size <= 20.0 else None

    s_raw = str(value).strip().lower()
    if not s_raw:
        return None
    s_raw = (
        s_raw.replace("in\u00e7", "inch")
        .replace("inc", "inch")
        .replace("in ", "inch ")
        .replace("in.", "inch ")
        .replace("inç", "inch")
        .replace(",", ".")
        .replace("”", "\"")
        .replace("″", "\"")
    )

    s_simple = s_raw.replace("\"", "").replace("inch", "").strip()
    if re.fullmatch(r"\d{1,2}(?:\.\d+)?", s_simple or ""):
        size = float(s_simple)
        return size if 10.0 <= size <= 20.0 else None

    for m in re.finditer(r"(\d{1,2}(?:\.\d+)?)\s*(?:\"|inch)", s_raw):
        try:
            size = float(m.group(1))
        except ValueError:
            continue
        if 10.0 <= size <= 20.0:
            return size

    # Standalone sizes like "13.3" or "15.6 FHD" without unit.
    for m in re.finditer(r"(?<!\d)(\d{1,2}(?:\.\d)?)\b(?!\.\s*[a-z])(?!=\s*[a-z])(?!\s*[x×]\s*\d)", s_raw):
        prefix = s_raw[:m.start()]
        if re.search(r"(windows|win)\s*$", prefix):
            continue
        try:
            size = float(m.group(1))
        except ValueError:
            continue
        if 10.0 <= size <= 20.0:
            return size
    return None

def _find_ram_candidates(title: str) -> List[int]:
    s = _normalize_title_text(title).upper()
    if not s:
        return []
    vals = []
    for pattern in (
        r"(\d{1,3})\s*GB\s*(?:RAM|DDR\d|LPDDR\d)",
        r"RAM\s*(\d{1,3})\s*GB",
        r"(?:DDR\d|LPDDR\d)\s*(\d{1,3})\s*GB",
    ):
        for m in re.finditer(pattern, s):
            try:
                vals.append(int(m.group(1)))
            except ValueError:
                continue
    return vals

def _find_screen_candidates(title: str) -> List[float]:
    s = _normalize_title_text(title)
    if not s:
        return []
    vals = []
    for m in re.finditer(r"(\d{1,2}(?:\.\d+)?)\s*(?:\"|inch|in\u00e7)", s):
        try:
            vals.append(float(m.group(1)))
        except ValueError:
            continue
    return vals
