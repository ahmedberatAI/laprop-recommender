import re

import numpy as np
import pandas as pd

from ..config.rules import (
    DEV_PRESETS,
    BRAND_SCORES,
    BRAND_PARAM_SCORES,
    BASE_WEIGHTS,
    CPU_SCORES,
    RTX_MODEL_SCORES,
    GTX_MODEL_SCORES,
    MX_MODEL_SCORES,
    RX_MODEL_SCORES,
)
from ..processing.normalize import sanitize_ram
from ..processing.read import _get_domain_counts
def get_cpu_score(cpu_text):
    """Geliştirilmiş CPU skorlama"""
    if pd.isna(cpu_text):
        return 5.0

    cpu_lower = str(cpu_text).lower()

    # Önce detaylı eşleşmeleri kontrol et
    for key, score in CPU_SCORES.items():
        if key in cpu_lower:
            # HX, H, U, P gibi suffixlere göre ayarlama
            if 'hx' in cpu_lower:
                return min(10, score + 0.5)  # Yüksek performans
            elif ' u' in cpu_lower or '-u' in cpu_lower:
                return max(1, score - 1.0)  # Düşük güç
            elif ' p' in cpu_lower or '-p' in cpu_lower:
                return score - 0.3  # Orta segment
            return score

    # Basit eşleşmeler
    if 'i9' in cpu_lower or 'ryzen 9' in cpu_lower:
        return 9.0
    elif 'i7' in cpu_lower or 'ryzen 7' in cpu_lower:
        return 7.5
    elif 'i5' in cpu_lower or 'ryzen 5' in cpu_lower:
        return 6.0
    elif 'i3' in cpu_lower or 'ryzen 3' in cpu_lower:
        return 4.0

    return 5.0  # Varsayılan

def get_gpu_score(gpu_text):
    """Model bazlı sağlam GPU skorlama (boşluksuz 'rtx4050' gibi yazımları da yakalar)."""
    if pd.isna(gpu_text):
        return 2.0

    s = str(gpu_text).lower()

    # iGPU kısa devreleri
    for kw in ['iris xe', 'iris plus', 'uhd graphics', 'hd graphics',
               'radeon graphics', 'radeon 780m', 'radeon 760m', 'radeon 680m',
               'vega 8', 'vega 7', 'vega 6', 'vega 3', 'integrated', 'igpu', 'apu graphics']:
        if kw in s:
            if '780m' in s or '680m' in s: return 3.5
            if '760m' in s or '660m' in s: return 3.0
            return 2.5

    # Intel Arc
    m = re.search(r'\barc\s*([a-z]?\d{3,4}m?)\b', s)
    if m:
        code = m.group(1).upper()
        if any(x in code for x in ['A770', 'A750']): return 7.5
        if any(x in code for x in ['A570', 'A550']): return 6.5
        if any(x in code for x in ['A370', 'A350']): return 5.5
        return 3.0

    # NVIDIA RTX (rtx 4050 / rtx4050)
    m = re.search(r'rtx\s*([345]\d{3,4})', s) or re.search(r'rtx(\d{4})', s)
    if m:
        code = m.group(1)
        if code in RTX_MODEL_SCORES: return RTX_MODEL_SCORES[code]
        if code.startswith('50'): return 8.3
        if code.startswith('40'): return 8.0
        if code.startswith('30'): return 7.0
        return 6.5

    # NVIDIA GTX
    m = re.search(r'gtx\s*(\d{3,4})', s) or re.search(r'gtx(\d{3,4})', s)
    if m:
        code = m.group(1)
        return GTX_MODEL_SCORES.get(code, 4.5)

    # NVIDIA MX
    m = re.search(r'\bmx\s*(\d{2,3})\b', s) or re.search(r'mx(\d{2,3})', s)
    if m:
        code = m.group(1)
        return MX_MODEL_SCORES.get(code, 3.5)

    # AMD RX
    m = re.search(r'\brx\s*(\d{3,4}m?)\b', s.replace(' ', ''))
    if m:
        code = m.group(1).upper()
        base = code.replace('M', '')
        if code in RX_MODEL_SCORES: return RX_MODEL_SCORES[code]
        if base in RX_MODEL_SCORES: return RX_MODEL_SCORES[base]
        if base.startswith('79'): return 8.6
        if base.startswith('78'): return 8.2
        if base.startswith('77'): return 7.7
        if base.startswith('76'): return 7.1
        if base.startswith('67'): return 6.9
        if base.startswith('66'): return 6.5
        return 5.5

    # Apple M
    if re.search(r'\bm4\b', s): return 8.5
    if re.search(r'\bm3\b', s): return 8.0
    if re.search(r'\bm2\b', s): return 7.5
    if re.search(r'\bm1\b', s): return 7.0

    # Discrete ama model yoksa
    if any(x in s for x in ['geforce', 'nvidia', 'radeon', 'discrete']):
        return 4.0

    return 2.0

def _cpu_suffix(cpu_text: str) -> str:
    s = (cpu_text or '').lower()
    if 'hx' in s: return 'hx'
    if re.search(r'(?<!h)h(?!x)', s): return 'h'
    if '-p' in s or ' p' in s: return 'p'
    if '-u' in s or ' u' in s: return 'u'
    # Intel Ultra 'V' serisine nazik davran: taşınabilir + performans karışımı
    if 'ultra' in s and re.search(r'\b2\d{2}v\b', s): return 'p'
    return ''

def _has_dgpu(gpu_norm: str) -> bool:
    s = (gpu_norm or '').lower()
    return not any(k in s for k in ['(igpu)', 'integrated', 'intel uhd', 'iris'])

def _is_nvidia_cuda(gpu_norm: str) -> bool:
    return 'rtx' in (gpu_norm or '').lower() or 'geforce' in (gpu_norm or '').lower()

def _rtx_tier(gpu_norm: str) -> int:
    """4060 -> 4060; 4070 -> 4070; yoksa 0"""
    m = re.search(r'rtx\s*(\d{4})', (gpu_norm or '').lower())
    return int(m.group(1)) if m else 0

def _is_heavy_dgpu_for_dev(gpu_norm: str) -> bool:
    s = (gpu_norm or '').lower()
    if not s:
        return False
    tier = _rtx_tier(s)
    if tier >= 4060:
        return True
    if 'rtx 50' in s or 'rtx50' in s:
        return True
    return False

def compute_dev_fit(row, dev_mode: str) -> float:
    p = DEV_PRESETS.get(dev_mode, DEV_PRESETS['general'])
    score = 0.0
    parts = 0

    # 1) RAM
    ram = _safe_num(row.get('ram_gb'), 8)
    score += min(1.0, ram / p['min_ram']) * 20   # 20 puan
    parts += 20

    # 2) SSD
    ssd = _safe_num(row.get('ssd_gb'), 256)
    score += min(1.0, ssd / p['min_ssd']) * 15   # 15 puan
    parts += 15

    # 3) CPU yapısı (suffix)
    cpu_suf = _cpu_suffix(str(row.get('cpu', '')))
    score += max(0.0, p['cpu_bias'].get(cpu_suf, 0.0)) * 4  # ±4’e kadar
    parts += 4
    web_adjust = 0.0
    if dev_mode == 'web':
        if cpu_suf == 'u':
            web_adjust += 3.0  # WEB DEV leakage fix
        elif cpu_suf == 'p':
            web_adjust += 2.0  # WEB DEV leakage fix
        elif cpu_suf == 'hx':
            web_adjust -= 2.0  # WEB DEV leakage fix

    # 4) GPU gerekliliği / seviyesi
    gnorm = str(row.get('gpu_norm', ''))
    has_d = _has_dgpu(gnorm)
    if p['need_dgpu'] and not has_d:
        return 0.0  # dGPU şartını sağlamıyorsa direkt 0 (ML/gamedev için kritik)
    if p['need_cuda'] and not _is_nvidia_cuda(gnorm):
        return 0.0  # NVIDIA şart

    base_gpu = _safe_num(row.get('gpu_score'), 3.0)  # 0–10
    gpu_pts = min(1.0, base_gpu / 8.0) * 20            # 20 puan tavan
    # Ek biaslar
    tier = _rtx_tier(gnorm)
    if dev_mode == 'ml':
        if tier >= 4060: gpu_pts += 5
        elif tier >= 4050: gpu_pts += 3
        elif has_d: gpu_pts += 1
    if dev_mode == 'gamedev':
        if tier >= 4070: gpu_pts += 6
        elif tier >= 4060: gpu_pts += 4
        elif tier >= 4050: gpu_pts += 2
    if dev_mode in ['web','general'] and has_d:
        gpu_pts -= 1.5  # gereksiz güç/ısınma/taşınabilirlik eksi
    if dev_mode == 'mobile' and has_d:
        gpu_pts -= 2.5

    gpu_pts = max(0.0, min(25.0, gpu_pts))  # 25 tavan
    if dev_mode == 'web':
        # DEV WEB: GPU is irrelevant override
        gpu_pts = 0.0
        if has_d:
            web_adjust -= 6.0  # DEV WEB: GPU is irrelevant override
            if tier >= 4050:
                web_adjust -= 4.0  # DEV WEB: GPU is irrelevant override
    score += gpu_pts
    parts += 25

    # 5) Ekran/taşınabilirlik
    scr = _safe_num(row.get('screen_size'), 15.6)
    if scr <= 13.6: port_bonus = p['port_bias'].get('<=13.6', 0.0)
    elif scr <= 14.5: port_bonus = p['port_bias'].get('<=14.5', p['port_bias'].get('<=14', 0.0))
    elif scr <= 15.6: port_bonus = p['port_bias'].get('<=15.6', 0.0)
    elif scr > 16: port_bonus = p['port_bias'].get('>16', -0.2)
    else: port_bonus = p['port_bias'].get('15-16', 0.0)

    size_ok = 1.0 if scr <= p['screen_max'] else 0.7
    score += size_ok * 10 + (port_bonus * 10)       # 10 + bias*10
    parts += 20
    if dev_mode == 'web':
        if scr <= 14.5:
            web_adjust += 2.0  # WEB DEV leakage fix
        elif scr > 16.0:
            web_adjust -= 3.0  # WEB DEV leakage fix
        if has_d and scr >= 15.6:
            web_adjust -= 2.0  # DEV WEB: GPU is irrelevant override

    # 6) OS uyumu (küçük çarpan)
    osv = str(row.get('os', 'freedos')).lower()
    os_mult = p['prefer_os'].get(osv, 0.98)
    # OS mult’u dev_fit’e minik etkilesin:
    score *= os_mult
    if dev_mode == 'web':
        os_norm = str(row.get('os') or '').strip().lower()
        if os_norm in ['', 'freedos']:
            web_adjust -= 6.0  # WEB DEV leakage fix

    # 7) Apple iGPU özel durumu (mobile/general’da avantaj, ml/gamedev’de zaten elendi)
    if any(k in gnorm.lower() for k in ['apple m1', 'apple m2', 'apple m3', 'apple m4']):
        # DEV WEB: GPU is irrelevant override
        if dev_mode in ['mobile', 'general']:
            score += 3.0  # pil/serinlik/ekosistem akıcılığı

    # Normalizasyon (0–100)
    base_fit = (score / parts) * 100 if parts > 0 else 0.0
    if dev_mode == 'web':
        base_fit += web_adjust  # WEB DEV leakage fix
    return max(0.0, min(100.0, base_fit))

def _safe_num(value, default):
    """Return numeric value or a default when missing/invalid."""
    try:
        if value is None:
            return default
        if isinstance(value, float) and np.isnan(value):
            return default
        return float(value)
    except Exception:
        return default

def _series_with_default(df, column: str, default: float) -> pd.Series:
    if column not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(default)

def calculate_score(row, preferences):
    """Geliştirilmiş puanlama sistemi - CPU verimlilik tespiti düzeltildi"""
    score_parts = {}
    usage_key = preferences.get('usage_key', 'productivity')

    # Önem çarpanları
    weights = get_dynamic_weights(usage_key)

    # 1) Fiyat skoru
    price = row['price']
    min_b = preferences['min_budget']
    max_b = preferences['max_budget']
    if min_b <= price <= max_b:
        price_range = max_b - min_b
        if price_range > 0:
            price_score = 100 * (1 - (price - min_b) / price_range)
        else:
            price_score = 100
        mid = (min_b + max_b) / 2
        distance_from_mid = abs(price - mid) / (price_range / 2) if price_range > 0 else 0
        mid_bonus = max(0, (1 - distance_from_mid) * 4)   # 10 → 4
        price_score = min(100, price_score * 0.95 + mid_bonus)  # 0.9 → 0.95

    else:
        penalty = (min_b - price) / min_b if price < min_b else (price - max_b) / max_b
        price_score = max(0, 50 * (1 - penalty))
    score_parts['price'] = price_score * weights['price'] / 100

    # 2) Performans skoru
    cpu_score = _safe_num(row.get('cpu_score'), 5.0)
    gpu_score = _safe_num(row.get('gpu_score'), 3.0)
    gpu_norm = str(row.get('gpu_norm', ''))
    dev_mode = preferences.get('dev_mode', 'general')
    is_dev_web = (usage_key == 'dev' and dev_mode == 'web')

    # Varsayılan karışımlar
    cpu_w, gpu_w = 0.7, 0.3  # dev/productivity için eski davranış

    if usage_key == 'gaming':
        cpu_w, gpu_w = 0.3, 0.7
    elif usage_key == 'design':
        cpu_w, gpu_w = 0.5, 0.5
    elif usage_key == 'portability':
        cpu_w, gpu_w = 0.8, 0.2
    elif usage_key in ['dev', 'productivity']:
        # Özel durum: Üretkenlik -> Multitask (çok pencere/çok monitör)
        if usage_key == 'productivity' and preferences.get('productivity_profile') == 'multitask':
            # GPU etkisini azalt, CPU'yu belirgin artır
            cpu_w, gpu_w = 0.85, 0.15

    if is_dev_web:
        # DEV WEB: GPU is irrelevant override
        cpu_w = 1.0
        gpu_w = 0.0

    perf_score = (cpu_score * cpu_w + gpu_score * gpu_w) * 10
    score_parts['performance'] = perf_score * weights['performance'] / 100


    # 3) RAM
    ram_gb = _safe_num(row.get('ram_gb'), 8)
    if ram_gb >= 64:
        ram_score = 100
    elif ram_gb >= 32:
        ram_score = 90
    elif ram_gb >= 24:
        ram_score = 80
    elif ram_gb >= 16:
        ram_score = 70
    elif ram_gb >= 12:
        ram_score = 55
    elif ram_gb >= 8:
        ram_score = 40
    else:
        ram_score = 20
    score_parts['ram'] = ram_score * weights['ram'] / 100

    # 4) Depolama
    ssd_gb = _safe_num(row.get('ssd_gb'), 256)
    if ssd_gb >= 2048:
        storage_score = 100
    elif ssd_gb >= 1024:
        storage_score = 85
    elif ssd_gb >= 512:
        storage_score = 70
    elif ssd_gb >= 256:
        storage_score = 50
    else:
        storage_score = 30
    score_parts['storage'] = storage_score * weights['storage'] / 100

    # 5) Marka güven
    brand = row.get('brand', 'other')
    brand_score = BRAND_SCORES.get(brand, 5.0) * 10
    score_parts['brand'] = brand_score * weights['brand'] / 100

    # 6) Marka-amaç uyumu
    brand_purpose = BRAND_PARAM_SCORES.get(brand, {}).get(usage_key, 70)
    score_parts['brand_purpose'] = brand_purpose * weights['brand_purpose'] / 100

    # 7) Pil ve taşınabilirlik
    screen_size = _safe_num(row.get('screen_size'), 15.6)
    battery_score = 50
    cpu_text = str(row.get('cpu', '')).lower()
    if any(x in cpu_text for x in ['m1', 'm2', 'm3', 'm4']):
        battery_score += 30
    elif re.search(r'i[3579]-\d+u', cpu_text) or cpu_text.endswith('-u'):
        battery_score += 20
    elif re.search(r'i[3579]-\d+p', cpu_text) or '-p' in cpu_text:
        battery_score += 10
    elif 'hx' in cpu_text or cpu_text.endswith('-hx'):
        battery_score -= 20
    elif re.search(r'i[3579]-\d+h(?!x)', cpu_text) or cpu_text.endswith('-h') or ' h ' in cpu_text:
        battery_score -= 10
    elif 'ryzen' in cpu_text and (' u' in cpu_text or cpu_text.endswith('u')):
        battery_score += 20
    elif 'ryzen' in cpu_text and 'hs' in cpu_text:
        battery_score += 5
    elif 'ryzen' in cpu_text and (
            'hx' in cpu_text or ((' h' in cpu_text or cpu_text.endswith('h')) and 'hs' not in cpu_text)):
        battery_score -= 15
    elif 'ultra' in cpu_text:
        battery_score += 15

    # DEV WEB: GPU is irrelevant override
    if not is_dev_web:
        if gpu_score < 3:
            battery_score += 15
        elif gpu_score > 7:
            battery_score -= 20
        elif gpu_score > 5:
            battery_score -= 10
    battery_score = max(0, min(100, battery_score))
    score_parts['battery'] = battery_score * weights['battery'] / 100

    portability_score = 50
    if screen_size <= 13:
        portability_score += 40
    elif screen_size <= 14:
        portability_score += 30
    elif screen_size <= 15:
        portability_score += 10
    elif screen_size >= 17:
        portability_score -= 30
    else:
        portability_score -= 10
    # DEV WEB: GPU is irrelevant override
    if not is_dev_web:
        if gpu_score < 3:
            portability_score += 10
        elif gpu_score > 7:
            portability_score -= 15
    portability_score = max(0, min(100, portability_score))
    score_parts['portability'] = portability_score * weights['portability'] / 100

    # 8) OS çarpanı
    os_val = row.get('os', 'freedos')
    os_multiplier = 1.0
    if usage_key == 'gaming':
        os_multiplier = 1.0  # FreeDOS/Windows farkını oyun performansına yansıtma
    elif usage_key in ['design', 'dev']:
        if os_val == 'macos':
            os_multiplier = 1.05
        elif os_val == 'windows':
            os_multiplier = 1.03
        elif os_val == 'linux':
            os_multiplier = 1.02
        elif os_val == 'freedos':
            os_multiplier = 0.95
    elif usage_key == 'productivity':
        if os_val in ['windows', 'macos']:
            os_multiplier = 1.02
        elif os_val == 'freedos':
            os_multiplier = 0.97



    base_score = sum(score_parts.values())
    dev_gpu_bonus = 0.0
    if usage_key == 'dev':
        # DEV WEB: GPU is irrelevant override
        if is_dev_web:
            dev_gpu_bonus = 0.0
        elif dev_mode in ['mobile', 'general']:
            has_dgpu = _has_dgpu(gpu_norm)
            if not has_dgpu:
                dev_gpu_bonus += 1.0
            elif _is_heavy_dgpu_for_dev(gpu_norm):
                dev_gpu_bonus -= 4.0
            else:
                dev_gpu_bonus -= 1.5

    total_score = (base_score + dev_gpu_bonus) * os_multiplier
    total_score = min(100, max(0, total_score))
    # DEV profili: base skor + dev uyumunun harmanı
    if usage_key == 'dev':
        dev_fit = compute_dev_fit(row, dev_mode)  # 0–100
        if dev_mode == 'web':
            # DEV WEB: GPU is irrelevant override
            total_score = 0.5 * total_score + 0.5 * dev_fit
        elif dev_mode == 'mobile':
            total_score = 0.55 * total_score + 0.45 * dev_fit
        elif dev_mode == 'general':
            total_score = 0.65 * total_score + 0.35 * dev_fit
        else:
            total_score = 0.7 * total_score + 0.3 * dev_fit
        total_score = min(100.0, max(0.0, total_score))

    breakdown = " | ".join(f"{k}:{v:.1f}" for k, v in score_parts.items())
    return total_score, breakdown

def get_dynamic_weights(usage_key: str) -> dict:
    """
    Kullanım amacına göre sabit ağırlıkları döndürür.
    (Kullanıcıdan 1–5 önem derecesi alınmadığı için ekstra çarpan yok.)
    Toplam ağırlık 100'e normalize edilir.
    """
    # Temel ağırlıkları kopyala
    weights = BASE_WEIGHTS.copy()

    # Kullanım amacına göre temel ayarlamalar
    if usage_key == 'gaming':
        weights.update({
            'performance': 40, 'ram': 15, 'storage': 10,
            'battery': 3, 'portability': 2, 'price': 15,
            'brand': 7, 'brand_purpose': 8
        })

    elif usage_key == 'portability':
        weights.update({
            'performance': 10, 'ram': 10, 'storage': 8,
            'battery': 20, 'portability': 25, 'price': 15,
            'brand': 6, 'brand_purpose': 6
        })

    elif usage_key == 'productivity':
        weights.update({
            'performance': 25, 'ram': 20, 'storage': 12,
            'battery': 8, 'portability': 8, 'price': 15,
            'brand': 6, 'brand_purpose': 6
        })

    elif usage_key == 'design':
        weights.update({
            'performance': 22, 'ram': 18, 'storage': 15,
            'battery': 10, 'portability': 10, 'price': 12,
            'brand': 7, 'brand_purpose': 6
        })

    elif usage_key == 'dev':
        weights.update({
            'performance': 28, 'ram': 22, 'storage': 15,
            'battery': 8, 'portability': 7, 'price': 12,
            'brand': 4, 'brand_purpose': 4
        })
    # else: bilinmeyen durumda BASE_WEIGHTS olduğu gibi kalır

    # Toplamı 100'e normalize et
    total = sum(weights.values())
    if total > 0:
        factor = 100.0 / total
        for k in list(weights.keys()):
            weights[k] = weights[k] * factor

    return weights

def filter_by_usage(df, usage_key, preferences):
    """
    Kullanım amacına göre ön filtreleme.
    - Önem puanları kaldırıldı; sabit, anlaşılır eşikler kullanılır.
    - Çok kalabalık/çok az sonuç durumunda hafif adaptif gevşetme/sıkılaştırma yapılır.
    """
    filtered = df.copy()
    ram_vals = _series_with_default(filtered, 'ram_gb', 8)
    ssd_vals = _series_with_default(filtered, 'ssd_gb', 256)
    cpu_vals = _series_with_default(filtered, 'cpu_score', 5.0)
    gpu_vals = _series_with_default(filtered, 'gpu_score', 3.0)
    screen_vals = _series_with_default(filtered, 'screen_size', 15.6)

    if usage_key == 'gaming':
        # Oyun seçimlerinden gelen dinamik GPU eşiği (0–10). Yoksa 6.0.
        min_needed = float(preferences.get('min_gpu_score_required', 6.0))
        # Sert kapı: eşik altını tamamen ele
        filtered = filtered[gpu_vals >= min_needed]
        # Makul RAM alt sınırı
        filtered = filtered[ram_vals >= 8]
        if 'name' in filtered.columns:
            name_lower = filtered['name'].fillna('').astype(str).str.lower()
            filtered = filtered[~(name_lower.str.contains('apple') | name_lower.str.contains('macbook'))]

    elif usage_key == 'portability':
        # Taşınabilirlik: ekran küçük olsun, ağır GPU'lar elensin (tercihen)
        filtered = filtered[screen_vals <= 14.5]

        # Çok fazla sonuçta ağır GPU’ları kıs (sırayla daha sıkı)
        if len(filtered) > 50:
            filtered = filtered[gpu_vals <= 5.0]
        elif len(filtered) > 30:
            filtered = filtered[gpu_vals <= 6.0]

    elif usage_key == 'productivity':
        filtered = filtered[ram_vals >= 8]
        filtered = filtered[cpu_vals >= 5.0]

    elif usage_key == 'design':
        filtered = filtered[ram_vals >= 16]
        filtered = filtered[gpu_vals >= 4.0]
        filtered = filtered[screen_vals >= 14.0]
        design_gpu_hint = preferences.get('design_gpu_hint')
        if design_gpu_hint:
            hint_map = {'high': 6.5, 'mid': 4.5, 'low': 2.5}
            min_gpu = hint_map.get(str(design_gpu_hint).lower())
            if min_gpu is not None:
                filtered = filtered[gpu_vals >= min_gpu]
        design_min_ram = preferences.get('design_min_ram_hint')
        if design_min_ram:
            try:
                min_ram = float(design_min_ram)
                filtered = filtered[ram_vals >= min_ram]
            except ValueError:
                pass

    elif usage_key == 'dev':
        dev_mode = preferences.get('dev_mode', 'general')
        # DEV WEB HARD FILTER — prevent gaming laptops
        if dev_mode == "web":
            # Normalize helpers already exist
            gpu_norm = filtered["gpu_norm"]
            cpu_suffix = filtered["cpu"].apply(_cpu_suffix)
            screen = filtered["screen_size"].fillna(15.6)
            os_val = filtered["os"].fillna("freedos").str.lower()

            # Rule 1: Remove RTX 4050+ (gaming GPUs)
            filtered = filtered[~gpu_norm.str.contains(r"rtx\s*(4050|4060|4070|4080|4090|50)", case=False, na=False)]

            # Rule 2: Remove HX CPUs (desktop-class, gaming-oriented)
            filtered = filtered[cpu_suffix != "hx"]

            # Rule 3: Remove large gaming chassis (>=16" + dGPU)
            filtered = filtered[~((screen >= 16.0) & (gpu_norm.apply(_has_dgpu)))]

            # Rule 4: Remove FreeDOS + dGPU combo
            filtered = filtered[~((os_val == "freedos") & (gpu_norm.apply(_has_dgpu)))]

            # Optional safety: if df becomes empty, skip filtering
            if filtered.empty:
                return filtered
        # Genel dev temel eşikler
        filtered = filtered[ram_vals >= 16]
        filtered = filtered[cpu_vals >= 6.0]
        filtered = filtered[ssd_vals >= 256]

        # Alt mod (web/ml/mobile/gamedev/general)
        p = DEV_PRESETS.get(dev_mode, DEV_PRESETS['general'])

        # Preset minimumları uygula
        filtered = filtered[ram_vals >= p['min_ram']]
        filtered = filtered[ssd_vals >= p['min_ssd']]

        # Ekran üst sınırı
        if 'screen_size' in filtered.columns:
            filtered = filtered[screen_vals <= p['screen_max']]

        # ML/Gamedev için dGPU/CUDA şartları
        if p.get('need_dgpu') or p.get('need_cuda'):
            if 'gpu_norm' in filtered.columns:
                filtered = filtered[filtered['gpu_norm'].apply(_has_dgpu)]
                if p.get('need_cuda'):
                    filtered = filtered[filtered['gpu_norm'].apply(_is_nvidia_cuda)]

    # Sonuç çok az kaldıysa, mantıklı bir gevşetme uygula
    if len(filtered) < 5 and len(df) > 5:
        print(f"⚠️ Filtreleme çok katı ({len(filtered)} ürün kaldı), kriterler gevşetiliyor...")
        if usage_key == 'gaming':
            return df[df['gpu_score'] >= 5.0]         # GPU eşiğini 6.0 → 5.0
        elif usage_key == 'portability':
            screen_vals_all = _series_with_default(df, 'screen_size', 15.6)
            return df[screen_vals_all <= 15.6]      # 14.5 → 15.6
        elif usage_key in ['design', 'dev']:
            ram_vals_all = _series_with_default(df, 'ram_gb', 8)
            return df[ram_vals_all >= 12]             # RAM 16 → 12
        else:
            return df

    return filtered

def get_recommendations(df, preferences, top_n=5):
    """Geliştirilmiş öneri sistemi (gaming için GPU eşiği fail-safe dahil)"""
    usage_key = preferences.get('usage_key', 'productivity')
    usage_label = preferences.get('usage_label', '')

    # 1) Bütçe filtresi
    budget_filtered = df[
        (df['price'] >= preferences['min_budget']) &
        (df['price'] <= preferences['max_budget'])
    ].copy()

    if budget_filtered.empty:
        print("\n❌ Bütçenize uygun laptop bulunamadı!")
        close_options = df[
            (df['price'] >= preferences['min_budget'] * 0.9) &
            (df['price'] <= preferences['max_budget'] * 1.1)
        ]
        if not close_options.empty:
            print(f"💡 İpucu: Bütçenizi %10 artırıp/azaltırsanız {len(close_options)} seçenek var.")
        return pd.DataFrame()

    # 1.1) Opsiyonel ekran üst sınırı
    screen_max = preferences.get('screen_max')
    if screen_max is not None and 'screen_size' in budget_filtered.columns:
        try:
            screen_max = float(screen_max)
        except (TypeError, ValueError):
            screen_max = None
        if screen_max is not None:
            screen_vals = pd.to_numeric(budget_filtered['screen_size'], errors='coerce')
            budget_filtered = budget_filtered[screen_vals <= screen_max]

    # 2) Kullanım amacına göre filtreleme
    filtered = filter_by_usage(budget_filtered, usage_key, preferences)

    # --- Fail-safe: gaming için GPU eşiğini tekrar ve kesin uygula
    if usage_key == 'gaming':
        # Oyun listesi seçiminden gelen eşik (örn. _prompt_gaming_titles → preferences['gaming_min_gpu'])
        min_gpu = float(
            preferences.get('gaming_min_gpu',  # oyun seçiminden geliyorsa bunu kullan
                preferences.get('min_gpu_score_required', 6.0))  # ya da genel ayar
        )
        before_cnt = len(filtered)
        filtered = filtered[filtered['gpu_score'] >= min_gpu]
        after_cnt = len(filtered)
        print(f"🧮 Oyun eşiği uygulanıyor → min gpu_score: {min_gpu:.1f} "
              f"(kalan: {after_cnt}/{before_cnt})")
        if filtered.empty:
            print("❌ Seçtiğiniz oyun(lar) için GPU eşiğini karşılayan cihaz bulunamadı.")
            print("💡 İpucu: Bütçeyi artırmayı veya oyun listesindeki hedefleri yeniden seçmeyi deneyin.")
            return pd.DataFrame()

    # 3) Duplikasyonları temizle
    if 'url' in filtered.columns:
        filtered = filtered.drop_duplicates(subset=['url'], keep='first')
    filtered = filtered.drop_duplicates(subset=['name', 'price'], keep='first')

    if filtered.empty:
        print("\n❌ Filtrelerden sonra uygun cihaz kalmadı.")
        return pd.DataFrame()

    # Final RAM sanity filter for impossible values (>64GB).
    if 'ram_gb' in filtered.columns and 'name' in filtered.columns:
        high_ram_mask = pd.to_numeric(filtered['ram_gb'], errors='coerce') > 64
        if high_ram_mask.any():
            filtered.loc[high_ram_mask, 'ram_gb'] = (
                filtered.loc[high_ram_mask].apply(sanitize_ram, axis=1)
            )

    # 4) Skorlama
    scores, breakdowns = [], []
    for _, row in filtered.iterrows():
        score, breakdown = calculate_score(row, preferences)
        scores.append(score)
        breakdowns.append(breakdown)
    filtered['score'] = scores
    filtered['score_breakdown'] = breakdowns

    # 5) Sıralama
    filtered = filtered.sort_values(by=['score', 'price'], ascending=[False, True])

    # 6) Top-N (marka çeşitliliği korunsun)
    recommendations, seen_brands, seen_price_ranges = [], set(), set()
    for _, row in filtered.iterrows():
        brand = row['brand']
        price_range = int(row['price'] / 10000) * 10000
        if len(recommendations) < 3:
            if brand not in seen_brands or len(recommendations) < 2:
                recommendations.append(row); seen_brands.add(brand); seen_price_ranges.add(price_range)
        else:
            recommendations.append(row)
        if len(recommendations) >= top_n:
            break

    result_df = pd.DataFrame(recommendations)

    # 7) Metadata
    if not result_df.empty:
        if 'url' in result_df.columns:
            counts = _get_domain_counts(result_df['url'])
            print(
                "URL domains: "
                f"amazon={counts['amazon']}, vatan={counts['vatan']}, incehesap={counts['incehesap']} "
                f"(total={len(result_df)})"
            )
        result_df.attrs['usage_label'] = usage_label
        result_df.attrs['avg_score'] = result_df['score'].mean()
        result_df.attrs['price_range'] = (result_df['price'].min(), result_df['price'].max())

    return result_df
