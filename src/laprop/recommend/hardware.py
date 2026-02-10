"""CPU and GPU scoring functions and hardware helper utilities."""

import re

import numpy as np
import pandas as pd

from ..config.rules import (
    CPU_SCORES,
    RTX_MODEL_SCORES,
    GTX_MODEL_SCORES,
    MX_MODEL_SCORES,
    RX_MODEL_SCORES,
)
from ..config.scoring_constants import (
    CPU_SUFFIX_HX_BONUS, CPU_SUFFIX_U_PENALTY, CPU_SUFFIX_P_PENALTY,
    CPU_FALLBACK_I9, CPU_FALLBACK_I7, CPU_FALLBACK_I5, CPU_FALLBACK_I3,
    CPU_DEFAULT_SCORE,
    GPU_DEFAULT_SCORE, GPU_IGPU_HIGH_SCORE, GPU_IGPU_MID_SCORE, GPU_IGPU_LOW_SCORE,
    GPU_ARC_HIGH_SCORE, GPU_ARC_MID_SCORE, GPU_ARC_LOW_SCORE, GPU_ARC_DEFAULT_SCORE,
    GPU_RTX_50_FALLBACK, GPU_RTX_40_FALLBACK, GPU_RTX_30_FALLBACK, GPU_RTX_DEFAULT_FALLBACK,
    GPU_GTX_DEFAULT_SCORE, GPU_MX_DEFAULT_SCORE, GPU_RX_DEFAULT_SCORE,
    GPU_DISCRETE_UNKNOWN_SCORE,
    GPU_APPLE_M4_SCORE, GPU_APPLE_M3_SCORE, GPU_APPLE_M2_SCORE, GPU_APPLE_M1_SCORE,
    GPU_RX_FALLBACK,
    HEAVY_DGPU_MIN_RTX_TIER,
)


def gpu_normalize_and_score(gpu_text: str) -> tuple:
    """
    Tek pass'ta GPU normalize + skor hesapla.
    normalize_gpu_model() ve get_gpu_score() çağrılarını birleştirir.
    Dönüş: (gpu_norm: str, gpu_score: float)
    """
    from ..processing.normalize import normalize_gpu_model as _norm_gpu
    gpu_norm = _norm_gpu(gpu_text)
    gpu_score = get_gpu_score(gpu_norm)
    return gpu_norm, gpu_score


def get_cpu_score(cpu_text):
    """Geliştirilmiş CPU skorlama"""
    if pd.isna(cpu_text):
        return CPU_DEFAULT_SCORE

    cpu_lower = str(cpu_text).lower()

    for key, score in CPU_SCORES.items():
        if key in cpu_lower:
            if 'hx' in cpu_lower:
                return min(10, score + CPU_SUFFIX_HX_BONUS)
            elif ' u' in cpu_lower or '-u' in cpu_lower:
                return max(1, score - CPU_SUFFIX_U_PENALTY)
            elif ' p' in cpu_lower or '-p' in cpu_lower:
                return score - CPU_SUFFIX_P_PENALTY
            return score

    if 'i9' in cpu_lower or 'ryzen 9' in cpu_lower:
        return CPU_FALLBACK_I9
    elif 'i7' in cpu_lower or 'ryzen 7' in cpu_lower:
        return CPU_FALLBACK_I7
    elif 'i5' in cpu_lower or 'ryzen 5' in cpu_lower:
        return CPU_FALLBACK_I5
    elif 'i3' in cpu_lower or 'ryzen 3' in cpu_lower:
        return CPU_FALLBACK_I3

    return CPU_DEFAULT_SCORE


def get_gpu_score(gpu_text):
    """Model bazlı sağlam GPU skorlama (boşluksuz 'rtx4050' gibi yazımları da yakalar)."""
    if pd.isna(gpu_text):
        return GPU_DEFAULT_SCORE

    s = str(gpu_text).lower()

    # iGPU kısa devreleri
    for kw in ['iris xe', 'iris plus', 'uhd graphics', 'hd graphics',
               'radeon graphics', 'radeon 780m', 'radeon 760m', 'radeon 680m',
               'vega 8', 'vega 7', 'vega 6', 'vega 3', 'integrated', 'igpu', 'apu graphics']:
        if kw in s:
            if '780m' in s or '680m' in s: return GPU_IGPU_HIGH_SCORE
            if '760m' in s or '660m' in s: return GPU_IGPU_MID_SCORE
            return GPU_IGPU_LOW_SCORE

    # Intel Arc
    m = re.search(r'\barc\s*([a-z]?\d{3,4}m?)\b', s)
    if m:
        code = m.group(1).upper()
        if any(x in code for x in ['A770', 'A750']): return GPU_ARC_HIGH_SCORE
        if any(x in code for x in ['A570', 'A550']): return GPU_ARC_MID_SCORE
        if any(x in code for x in ['A370', 'A350']): return GPU_ARC_LOW_SCORE
        return GPU_ARC_DEFAULT_SCORE

    # NVIDIA RTX (rtx 4050 / rtx4050)
    m = re.search(r'rtx\s*([345]\d{3,4})', s) or re.search(r'rtx(\d{4})', s)
    if m:
        code = m.group(1)
        if code in RTX_MODEL_SCORES: return RTX_MODEL_SCORES[code]
        if code.startswith('50'): return GPU_RTX_50_FALLBACK
        if code.startswith('40'): return GPU_RTX_40_FALLBACK
        if code.startswith('30'): return GPU_RTX_30_FALLBACK
        return GPU_RTX_DEFAULT_FALLBACK

    # NVIDIA GTX
    m = re.search(r'gtx\s*(\d{3,4})', s) or re.search(r'gtx(\d{3,4})', s)
    if m:
        code = m.group(1)
        return GTX_MODEL_SCORES.get(code, GPU_GTX_DEFAULT_SCORE)

    # NVIDIA MX
    m = re.search(r'\bmx\s*(\d{2,3})\b', s) or re.search(r'mx(\d{2,3})', s)
    if m:
        code = m.group(1)
        return MX_MODEL_SCORES.get(code, GPU_MX_DEFAULT_SCORE)

    # AMD RX
    m = re.search(r'\brx\s*(\d{3,4}m?)\b', s.replace(' ', ''))
    if m:
        code = m.group(1).upper()
        base = code.replace('M', '')
        if code in RX_MODEL_SCORES: return RX_MODEL_SCORES[code]
        if base in RX_MODEL_SCORES: return RX_MODEL_SCORES[base]
        for prefix, fallback_score in GPU_RX_FALLBACK.items():
            if base.startswith(prefix):
                return fallback_score
        return GPU_RX_DEFAULT_SCORE

    # Apple M
    if re.search(r'\bm4\b', s): return GPU_APPLE_M4_SCORE
    if re.search(r'\bm3\b', s): return GPU_APPLE_M3_SCORE
    if re.search(r'\bm2\b', s): return GPU_APPLE_M2_SCORE
    if re.search(r'\bm1\b', s): return GPU_APPLE_M1_SCORE

    # Discrete ama model yoksa
    if any(x in s for x in ['geforce', 'nvidia', 'radeon', 'discrete']):
        return GPU_DISCRETE_UNKNOWN_SCORE

    return GPU_DEFAULT_SCORE


def _cpu_suffix(cpu_text: str) -> str:
    s = (cpu_text or '').lower()
    if 'hx' in s: return 'hx'
    if re.search(r'(?<!h)h(?!x)', s): return 'h'
    if '-p' in s or ' p' in s: return 'p'
    if '-u' in s or ' u' in s: return 'u'
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
    if tier >= HEAVY_DGPU_MIN_RTX_TIER:
        return True
    if 'rtx 50' in s or 'rtx50' in s:
        return True
    return False
