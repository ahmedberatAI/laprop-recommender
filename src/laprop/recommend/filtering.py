"""Usage-based filtering for laptop recommendations."""

import pandas as pd

from ..config.rules import DEV_PRESETS
from ..config.scoring_constants import (
    FILTER_MIN_RESULTS, FILTER_GAMING_RELAXED_GPU,
    FILTER_PORTABILITY_MAX_SCREEN, FILTER_PORTABILITY_RELAXED_SCREEN,
    FILTER_PORTABILITY_GPU_THRESHOLDS,
    FILTER_DESIGN_MIN_RAM, FILTER_DESIGN_MIN_GPU, FILTER_DESIGN_MIN_SCREEN,
    FILTER_DESIGN_GPU_HINT_MAP,
    FILTER_DEV_MIN_RAM, FILTER_DEV_MIN_CPU, FILTER_DEV_MIN_SSD,
    FILTER_RELAXED_MIN_RAM,
)
from ..utils.logging import get_logger
from .hardware import _cpu_suffix, _has_dgpu, _is_nvidia_cuda
from .scoring import _series_with_default

logger = get_logger(__name__)


def _apply_design_hints(filtered, preferences, gpu_vals, ram_vals):
    """Design profili GPU/RAM hint'lerini uygula."""
    gpu_hint = preferences.get('design_gpu_hint')
    if gpu_hint:
        min_gpu = FILTER_DESIGN_GPU_HINT_MAP.get(str(gpu_hint).lower())
        if min_gpu is not None:
            filtered = filtered[gpu_vals >= min_gpu]

    ram_hint = preferences.get('design_min_ram_hint')
    if ram_hint:
        try:
            filtered = filtered[ram_vals >= float(ram_hint)]
        except (ValueError, TypeError):
            pass

    return filtered


def filter_by_usage(df, usage_key, preferences):
    """
    Kullanım amacına göre ön filtreleme.
    - Sabit, anlaşılır eşikler kullanılır.
    - Çok az sonuç durumunda hafif adaptif gevşetme yapılır.
    """
    filtered = df.copy()
    ram_vals = _series_with_default(filtered, 'ram_gb', 8)
    ssd_vals = _series_with_default(filtered, 'ssd_gb', 256)
    cpu_vals = _series_with_default(filtered, 'cpu_score', 5.0)
    gpu_vals = _series_with_default(filtered, 'gpu_score', 3.0)
    screen_vals = _series_with_default(filtered, 'screen_size', 15.6)

    if usage_key == 'gaming':
        min_needed = float(preferences.get('min_gpu_score_required', 6.0))
        filtered = filtered[gpu_vals >= min_needed]
        filtered = filtered[ram_vals >= 8]
        if 'name' in filtered.columns:
            name_lower = filtered['name'].fillna('').astype(str).str.lower()
            filtered = filtered[~(name_lower.str.contains('apple') | name_lower.str.contains('macbook'))]

    elif usage_key == 'portability':
        filtered = filtered[screen_vals <= FILTER_PORTABILITY_MAX_SCREEN]

        c1, g1, c2, g2 = FILTER_PORTABILITY_GPU_THRESHOLDS
        if len(filtered) > c1:
            filtered = filtered[gpu_vals <= g1]
        elif len(filtered) > c2:
            filtered = filtered[gpu_vals <= g2]

    elif usage_key == 'productivity':
        filtered = filtered[ram_vals >= 8]
        filtered = filtered[cpu_vals >= 5.0]

    elif usage_key == 'design':
        filtered = filtered[ram_vals >= FILTER_DESIGN_MIN_RAM]
        filtered = filtered[gpu_vals >= FILTER_DESIGN_MIN_GPU]
        filtered = filtered[screen_vals >= FILTER_DESIGN_MIN_SCREEN]
        filtered = _apply_design_hints(filtered, preferences, gpu_vals, ram_vals)

    elif usage_key == 'dev':
        dev_mode = preferences.get('dev_mode', 'general')
        if dev_mode == "web":
            gpu_norm = filtered["gpu_norm"]
            cpu_suffix = filtered["cpu"].apply(_cpu_suffix)
            screen = filtered["screen_size"].fillna(15.6)
            os_val = filtered["os"].fillna("freedos").str.lower()

            filtered = filtered[~gpu_norm.str.contains(r"rtx\s*(4050|4060|4070|4080|4090|50)", case=False, na=False)]
            filtered = filtered[cpu_suffix != "hx"]
            filtered = filtered[~((screen >= 16.0) & (gpu_norm.apply(_has_dgpu)))]
            filtered = filtered[~((os_val == "freedos") & (gpu_norm.apply(_has_dgpu)))]

            if filtered.empty:
                return filtered

        filtered = filtered[ram_vals >= FILTER_DEV_MIN_RAM]
        filtered = filtered[cpu_vals >= FILTER_DEV_MIN_CPU]
        filtered = filtered[ssd_vals >= FILTER_DEV_MIN_SSD]

        p = DEV_PRESETS.get(dev_mode, DEV_PRESETS['general'])
        filtered = filtered[ram_vals >= p['min_ram']]
        filtered = filtered[ssd_vals >= p['min_ssd']]

        if 'screen_size' in filtered.columns:
            filtered = filtered[screen_vals <= p['screen_max']]

        if p.get('need_dgpu') or p.get('need_cuda'):
            if 'gpu_norm' in filtered.columns:
                filtered = filtered[filtered['gpu_norm'].apply(_has_dgpu)]
                if p.get('need_cuda'):
                    filtered = filtered[filtered['gpu_norm'].apply(_is_nvidia_cuda)]

    # Sonuç çok az kaldıysa gevşetme
    if len(filtered) < FILTER_MIN_RESULTS and len(df) > FILTER_MIN_RESULTS:
        logger.warning("Filtreleme çok katı (%d ürün kaldı), kriterler gevşetiliyor...", len(filtered))
        if usage_key == 'gaming':
            return df[df['gpu_score'] >= FILTER_GAMING_RELAXED_GPU]
        elif usage_key == 'portability':
            screen_vals_all = _series_with_default(df, 'screen_size', 15.6)
            return df[screen_vals_all <= FILTER_PORTABILITY_RELAXED_SCREEN]
        elif usage_key in ['design', 'dev']:
            ram_vals_all = _series_with_default(df, 'ram_gb', 8)
            return df[ram_vals_all >= FILTER_RELAXED_MIN_RAM]
        else:
            return df

    return filtered
