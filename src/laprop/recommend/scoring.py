"""Score calculation, dev-fit computation, and dynamic weight generation."""

import re

import numpy as np
import pandas as pd

from ..config.rules import (
    DEV_PRESETS,
    BRAND_SCORES,
    BRAND_PARAM_SCORES,
    BASE_WEIGHTS,
)
from ..config.scoring_constants import (
    PRICE_BASE_FACTOR, PRICE_MID_BONUS_MAX, PRICE_OUT_OF_RANGE_BASE,
    PERF_MIX,
    RAM_SCORE_TIERS, SSD_SCORE_TIERS,
    BATTERY_BASE_SCORE, BATTERY_ADJUSTMENTS,
    BATTERY_GPU_LOW_BONUS, BATTERY_GPU_HIGH_PENALTY, BATTERY_GPU_MID_PENALTY,
    PORTABILITY_BASE_SCORE, PORTABILITY_SCREEN_TIERS,
    PORTABILITY_LARGE_PENALTY, PORTABILITY_DEFAULT_PENALTY,
    PORTABILITY_GPU_LOW_BONUS, PORTABILITY_GPU_HIGH_PENALTY,
    OS_MULTIPLIERS,
    DEV_FIT_BLEND, DEV_GPU_NO_DGPU_BONUS, DEV_GPU_HEAVY_PENALTY, DEV_GPU_LIGHT_PENALTY,
    DEV_FIT_RAM_POINTS, DEV_FIT_SSD_POINTS, DEV_FIT_CPU_MULTIPLIER,
    DEV_FIT_GPU_BASE_POINTS, DEV_FIT_GPU_MAX_POINTS,
    DEV_FIT_SCREEN_POINTS, DEV_FIT_SCREEN_TOTAL_PARTS,
    DEV_FIT_SIZE_OK, DEV_FIT_SIZE_PENALTY, DEV_FIT_APPLE_BONUS,
    DEV_WEB_CPU_U_BONUS, DEV_WEB_CPU_P_BONUS, DEV_WEB_CPU_HX_PENALTY,
    DEV_WEB_DGPU_PENALTY, DEV_WEB_DGPU_RTX_EXTRA_PENALTY,
    DEV_WEB_SMALL_SCREEN_BONUS, DEV_WEB_LARGE_SCREEN_PENALTY,
    DEV_WEB_DGPU_LARGE_SCREEN_PENALTY, DEV_WEB_FREEDOS_PENALTY,
    DEV_ML_GPU_BONUS, DEV_GAMEDEV_GPU_BONUS,
    DEV_WEB_GENERAL_DGPU_PENALTY, DEV_MOBILE_DGPU_PENALTY,
)
from .hardware import (
    _cpu_suffix,
    _has_dgpu,
    _is_nvidia_cuda,
    _rtx_tier,
    _is_heavy_dgpu_for_dev,
)


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


def compute_dev_fit(row, dev_mode: str) -> float:
    p = DEV_PRESETS.get(dev_mode, DEV_PRESETS['general'])
    score = 0.0
    parts = 0

    # 1) RAM
    ram = _safe_num(row.get('ram_gb'), 8)
    score += min(1.0, ram / p['min_ram']) * DEV_FIT_RAM_POINTS
    parts += DEV_FIT_RAM_POINTS

    # 2) SSD
    ssd = _safe_num(row.get('ssd_gb'), 256)
    score += min(1.0, ssd / p['min_ssd']) * DEV_FIT_SSD_POINTS
    parts += DEV_FIT_SSD_POINTS

    # 3) CPU yapısı (suffix)
    cpu_suf = _cpu_suffix(str(row.get('cpu', '')))
    score += max(0.0, p['cpu_bias'].get(cpu_suf, 0.0)) * DEV_FIT_CPU_MULTIPLIER
    parts += DEV_FIT_CPU_MULTIPLIER
    web_adjust = 0.0
    if dev_mode == 'web':
        if cpu_suf == 'u':
            web_adjust += DEV_WEB_CPU_U_BONUS
        elif cpu_suf == 'p':
            web_adjust += DEV_WEB_CPU_P_BONUS
        elif cpu_suf == 'hx':
            web_adjust -= DEV_WEB_CPU_HX_PENALTY

    # 4) GPU gerekliliği / seviyesi
    gnorm = str(row.get('gpu_norm', ''))
    has_d = _has_dgpu(gnorm)
    if p['need_dgpu'] and not has_d:
        return 0.0
    if p['need_cuda'] and not _is_nvidia_cuda(gnorm):
        return 0.0

    base_gpu = _safe_num(row.get('gpu_score'), 3.0)
    gpu_pts = min(1.0, base_gpu / 8.0) * DEV_FIT_GPU_BASE_POINTS
    tier = _rtx_tier(gnorm)
    if dev_mode == 'ml':
        if tier >= 4060: gpu_pts += DEV_ML_GPU_BONUS[4060]
        elif tier >= 4050: gpu_pts += DEV_ML_GPU_BONUS[4050]
        elif has_d: gpu_pts += DEV_ML_GPU_BONUS['dgpu']
    if dev_mode == 'gamedev':
        if tier >= 4070: gpu_pts += DEV_GAMEDEV_GPU_BONUS[4070]
        elif tier >= 4060: gpu_pts += DEV_GAMEDEV_GPU_BONUS[4060]
        elif tier >= 4050: gpu_pts += DEV_GAMEDEV_GPU_BONUS[4050]
    if dev_mode in ['web', 'general'] and has_d:
        gpu_pts -= DEV_WEB_GENERAL_DGPU_PENALTY
    if dev_mode == 'mobile' and has_d:
        gpu_pts -= DEV_MOBILE_DGPU_PENALTY

    gpu_pts = max(0.0, min(float(DEV_FIT_GPU_MAX_POINTS), gpu_pts))
    if dev_mode == 'web':
        gpu_pts = 0.0
        if has_d:
            web_adjust -= DEV_WEB_DGPU_PENALTY
            if tier >= 4050:
                web_adjust -= DEV_WEB_DGPU_RTX_EXTRA_PENALTY
    score += gpu_pts
    parts += DEV_FIT_GPU_MAX_POINTS

    # 5) Ekran/taşınabilirlik
    scr = _safe_num(row.get('screen_size'), 15.6)
    if scr <= 13.6: port_bonus = p['port_bias'].get('<=13.6', 0.0)
    elif scr <= 14.5: port_bonus = p['port_bias'].get('<=14.5', p['port_bias'].get('<=14', 0.0))
    elif scr <= 15.6: port_bonus = p['port_bias'].get('<=15.6', 0.0)
    elif scr > 16: port_bonus = p['port_bias'].get('>16', -0.2)
    else: port_bonus = p['port_bias'].get('15-16', 0.0)

    size_ok = DEV_FIT_SIZE_OK if scr <= p['screen_max'] else DEV_FIT_SIZE_PENALTY
    score += size_ok * DEV_FIT_SCREEN_POINTS + (port_bonus * DEV_FIT_SCREEN_POINTS)
    parts += DEV_FIT_SCREEN_TOTAL_PARTS
    if dev_mode == 'web':
        if scr <= 14.5:
            web_adjust += DEV_WEB_SMALL_SCREEN_BONUS
        elif scr > 16.0:
            web_adjust -= DEV_WEB_LARGE_SCREEN_PENALTY
        if has_d and scr >= 15.6:
            web_adjust -= DEV_WEB_DGPU_LARGE_SCREEN_PENALTY

    # 6) OS uyumu
    osv = str(row.get('os', 'freedos')).lower()
    os_mult = p['prefer_os'].get(osv, 0.98)
    score *= os_mult
    if dev_mode == 'web':
        os_norm = str(row.get('os') or '').strip().lower()
        if os_norm in ['', 'freedos']:
            web_adjust -= DEV_WEB_FREEDOS_PENALTY

    # 7) Apple iGPU özel durumu
    if any(k in gnorm.lower() for k in ['apple m1', 'apple m2', 'apple m3', 'apple m4']):
        if dev_mode in ['mobile', 'general']:
            score += DEV_FIT_APPLE_BONUS

    # Normalizasyon (0–100)
    base_fit = (score / parts) * 100 if parts > 0 else 0.0
    if dev_mode == 'web':
        base_fit += web_adjust
    return max(0.0, min(100.0, base_fit))


def calculate_score(row, preferences):
    """Geliştirilmiş puanlama sistemi - CPU verimlilik tespiti düzeltildi"""
    score_parts = {}
    usage_key = preferences.get('usage_key', 'productivity')

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
        mid_bonus = max(0, (1 - distance_from_mid) * PRICE_MID_BONUS_MAX)
        price_score = min(100, price_score * PRICE_BASE_FACTOR + mid_bonus)
    else:
        penalty = (min_b - price) / min_b if price < min_b else (price - max_b) / max_b
        price_score = max(0, PRICE_OUT_OF_RANGE_BASE * (1 - penalty))
    score_parts['price'] = price_score * weights['price'] / 100

    # 2) Performans skoru
    cpu_score = _safe_num(row.get('cpu_score'), 5.0)
    gpu_score = _safe_num(row.get('gpu_score'), 3.0)
    gpu_norm = str(row.get('gpu_norm', ''))
    dev_mode = preferences.get('dev_mode', 'general')
    is_dev_web = (usage_key == 'dev' and dev_mode == 'web')

    cpu_w, gpu_w = PERF_MIX['default']

    if usage_key == 'gaming':
        cpu_w, gpu_w = PERF_MIX['gaming']
    elif usage_key == 'design':
        cpu_w, gpu_w = PERF_MIX['design']
    elif usage_key == 'portability':
        cpu_w, gpu_w = PERF_MIX['portability']
    elif usage_key in ['dev', 'productivity']:
        if usage_key == 'productivity' and preferences.get('productivity_profile') == 'multitask':
            cpu_w, gpu_w = PERF_MIX['multitask']

    if is_dev_web:
        cpu_w, gpu_w = PERF_MIX['dev_web']

    perf_score = (cpu_score * cpu_w + gpu_score * gpu_w) * 10
    score_parts['performance'] = perf_score * weights['performance'] / 100

    # 3) RAM
    ram_gb = _safe_num(row.get('ram_gb'), 8)
    ram_score = RAM_SCORE_TIERS[-1][1]
    for tier_min, tier_score in RAM_SCORE_TIERS:
        if ram_gb >= tier_min:
            ram_score = tier_score
            break
    score_parts['ram'] = ram_score * weights['ram'] / 100

    # 4) Depolama
    ssd_gb = _safe_num(row.get('ssd_gb'), 256)
    storage_score = SSD_SCORE_TIERS[-1][1]
    for tier_min, tier_score in SSD_SCORE_TIERS:
        if ssd_gb >= tier_min:
            storage_score = tier_score
            break
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
    battery_score = BATTERY_BASE_SCORE
    cpu_text = str(row.get('cpu', '')).lower()
    if any(x in cpu_text for x in ['m1', 'm2', 'm3', 'm4']):
        battery_score += BATTERY_ADJUSTMENTS['apple_m']
    elif re.search(r'i[3579]-\d+u', cpu_text) or cpu_text.endswith('-u'):
        battery_score += BATTERY_ADJUSTMENTS['intel_u']
    elif re.search(r'i[3579]-\d+p', cpu_text) or '-p' in cpu_text:
        battery_score += BATTERY_ADJUSTMENTS['intel_p']
    elif 'hx' in cpu_text or cpu_text.endswith('-hx'):
        battery_score += BATTERY_ADJUSTMENTS['intel_hx']
    elif re.search(r'i[3579]-\d+h(?!x)', cpu_text) or cpu_text.endswith('-h') or ' h ' in cpu_text:
        battery_score += BATTERY_ADJUSTMENTS['intel_h']
    elif 'ryzen' in cpu_text and (' u' in cpu_text or cpu_text.endswith('u')):
        battery_score += BATTERY_ADJUSTMENTS['ryzen_u']
    elif 'ryzen' in cpu_text and 'hs' in cpu_text:
        battery_score += BATTERY_ADJUSTMENTS['ryzen_hs']
    elif 'ryzen' in cpu_text and (
            'hx' in cpu_text or ((' h' in cpu_text or cpu_text.endswith('h')) and 'hs' not in cpu_text)):
        battery_score += BATTERY_ADJUSTMENTS['ryzen_h']
    elif 'ultra' in cpu_text:
        battery_score += BATTERY_ADJUSTMENTS['ultra']

    if not is_dev_web:
        if gpu_score < 3:
            battery_score += BATTERY_GPU_LOW_BONUS
        elif gpu_score > 7:
            battery_score -= BATTERY_GPU_HIGH_PENALTY
        elif gpu_score > 5:
            battery_score -= BATTERY_GPU_MID_PENALTY
    battery_score = max(0, min(100, battery_score))
    score_parts['battery'] = battery_score * weights['battery'] / 100

    portability_score = PORTABILITY_BASE_SCORE
    if screen_size <= 13:
        portability_score += PORTABILITY_SCREEN_TIERS[0][1]
    elif screen_size <= 14:
        portability_score += PORTABILITY_SCREEN_TIERS[1][1]
    elif screen_size <= 15:
        portability_score += PORTABILITY_SCREEN_TIERS[2][1]
    elif screen_size >= 17:
        portability_score -= PORTABILITY_LARGE_PENALTY
    else:
        portability_score -= PORTABILITY_DEFAULT_PENALTY
    if not is_dev_web:
        if gpu_score < 3:
            portability_score += PORTABILITY_GPU_LOW_BONUS
        elif gpu_score > 7:
            portability_score -= PORTABILITY_GPU_HIGH_PENALTY
    portability_score = max(0, min(100, portability_score))
    score_parts['portability'] = portability_score * weights['portability'] / 100

    # 8) OS çarpanı
    os_val = row.get('os', 'freedos')
    os_multiplier = 1.0
    if usage_key == 'gaming':
        os_multiplier = 1.0
    elif usage_key in ['design', 'dev']:
        os_multiplier = OS_MULTIPLIERS['design_dev'].get(os_val, 1.0)
    elif usage_key == 'productivity':
        os_multiplier = OS_MULTIPLIERS['productivity'].get(os_val, 1.0)

    base_score = sum(score_parts.values())
    dev_gpu_bonus = 0.0
    if usage_key == 'dev':
        if is_dev_web:
            dev_gpu_bonus = 0.0
        elif dev_mode in ['mobile', 'general']:
            has_dgpu = _has_dgpu(gpu_norm)
            if not has_dgpu:
                dev_gpu_bonus += DEV_GPU_NO_DGPU_BONUS
            elif _is_heavy_dgpu_for_dev(gpu_norm):
                dev_gpu_bonus -= DEV_GPU_HEAVY_PENALTY
            else:
                dev_gpu_bonus -= DEV_GPU_LIGHT_PENALTY

    total_score = (base_score + dev_gpu_bonus) * os_multiplier
    total_score = min(100, max(0, total_score))
    if usage_key == 'dev':
        dev_fit = compute_dev_fit(row, dev_mode)
        blend = DEV_FIT_BLEND.get(dev_mode, DEV_FIT_BLEND['default'])
        total_score = blend[0] * total_score + blend[1] * dev_fit
        total_score = min(100.0, max(0.0, total_score))

    breakdown = " | ".join(f"{k}:{v:.1f}" for k, v in score_parts.items())
    return total_score, breakdown


def get_dynamic_weights(usage_key: str) -> dict:
    """
    Kullanım amacına göre sabit ağırlıkları döndürür.
    Toplam ağırlık 100'e normalize edilir.
    """
    weights = BASE_WEIGHTS.copy()

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

    total = sum(weights.values())
    if total > 0:
        factor = 100.0 / total
        for k in list(weights.keys()):
            weights[k] = weights[k] * factor

    return weights
