"""Recommendation engine — orchestrates scoring, filtering, and ranking.

Submodules:
  - hardware: CPU/GPU scoring, hardware helpers
  - scoring: calculate_score, compute_dev_fit, get_dynamic_weights
  - filtering: filter_by_usage, _apply_design_hints
"""

import pandas as pd

from ..config.scoring_constants import BUDGET_CLOSE_FACTOR
from ..processing.normalize import sanitize_ram
from ..processing.read import _get_domain_counts
from ..utils.logging import get_logger

# --- Re-exports for backward compatibility ---
from .hardware import (  # noqa: F401
    gpu_normalize_and_score,
    get_cpu_score,
    get_gpu_score,
    _cpu_suffix,
    _has_dgpu,
    _is_nvidia_cuda,
    _rtx_tier,
    _is_heavy_dgpu_for_dev,
)
from .scoring import (  # noqa: F401
    _safe_num,
    _series_with_default,
    compute_dev_fit,
    calculate_score,
    get_dynamic_weights,
)
from .filtering import (  # noqa: F401
    _apply_design_hints,
    filter_by_usage,
)

logger = get_logger(__name__)


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
        logger.info("Bütçenize uygun laptop bulunamadı!")
        close_options = df[
            (df['price'] >= preferences['min_budget'] * (1 - BUDGET_CLOSE_FACTOR)) &
            (df['price'] <= preferences['max_budget'] * (1 + BUDGET_CLOSE_FACTOR))
        ]
        if not close_options.empty:
            logger.info("İpucu: Bütçenizi %%10 artırıp/azaltırsanız %d seçenek var.", len(close_options))
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

    # --- Fail-safe: gaming için GPU eşiğini tekrar uygula
    if usage_key == 'gaming':
        min_gpu = float(
            preferences.get('gaming_min_gpu',
                preferences.get('min_gpu_score_required', 6.0))
        )
        before_cnt = len(filtered)
        filtered = filtered[filtered['gpu_score'] >= min_gpu]
        after_cnt = len(filtered)
        logger.info("Oyun eşiği uygulanıyor -> min gpu_score: %.1f (kalan: %d/%d)", min_gpu, after_cnt, before_cnt)
        if filtered.empty:
            logger.info("Seçtiğiniz oyun(lar) için GPU eşiğini karşılayan cihaz bulunamadı.")
            logger.info("İpucu: Bütçeyi artırmayı veya oyun listesindeki hedefleri yeniden seçmeyi deneyin.")
            return pd.DataFrame()

    # 3) Duplikasyonları temizle
    if 'url' in filtered.columns:
        filtered = filtered.drop_duplicates(subset=['url'], keep='first')
    filtered = filtered.drop_duplicates(subset=['name', 'price'], keep='first')

    if filtered.empty:
        logger.info("Filtrelerden sonra uygun cihaz kalmadı.")
        return pd.DataFrame()

    # Final RAM sanity filter
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
            logger.info(
                "URL domains: amazon=%d, vatan=%d, incehesap=%d (total=%d)",
                counts['amazon'], counts['vatan'], counts['incehesap'], len(result_df),
            )
        result_df.attrs['usage_label'] = usage_label
        result_df.attrs['avg_score'] = result_df['score'].mean()
        result_df.attrs['price_range'] = (result_df['price'].min(), result_df['price'].max())

    return result_df
