"""Unit tests for laprop.recommend.engine — target ≥70 % coverage."""

import numpy as np
import pandas as pd
import pytest

from laprop.recommend.engine import (
    get_cpu_score,
    get_gpu_score,
    _cpu_suffix,
    _has_dgpu,
    _is_nvidia_cuda,
    _rtx_tier,
    _is_heavy_dgpu_for_dev,
    compute_dev_fit,
    _safe_num,
    _series_with_default,
    calculate_score,
    get_dynamic_weights,
    filter_by_usage,
    get_recommendations,
)


# ============================================================================
# get_cpu_score
# ============================================================================
class TestGetCpuScore:
    def test_na_returns_default(self):
        assert get_cpu_score(None) == 5.0
        assert get_cpu_score(np.nan) == 5.0

    @pytest.mark.parametrize("cpu,min_expected", [
        ("i9-14900HX", 9.0),
        ("i7-13700H", 7.0),
        ("i5-12500U", 4.0),  # U suffix lowers score
        ("Ryzen 9 7945HX", 8.0),
        ("Ryzen 5 7530U", 5.0),
        ("M4", 9.0),
        ("Ultra 7", 7.0),
    ])
    def test_known_cpus(self, cpu, min_expected):
        score = get_cpu_score(cpu)
        assert score >= min_expected, f"CPU '{cpu}' scored {score}, expected >= {min_expected}"

    def test_i3_fallback(self):
        assert get_cpu_score("i3-1215U") >= 3.0

    def test_unknown_cpu(self):
        assert get_cpu_score("Unknown Chip X1") == 5.0

    def test_hx_suffix_bonus(self):
        score_hx = get_cpu_score("i7-13700HX")
        score_h = get_cpu_score("i7-13700H")
        # HX should score at least as high as H
        assert score_hx >= score_h


# ============================================================================
# get_gpu_score
# ============================================================================
class TestGetGpuScore:
    def test_na_returns_default(self):
        assert get_gpu_score(None) == 2.0
        assert get_gpu_score(np.nan) == 2.0

    @pytest.mark.parametrize("gpu,min_expected", [
        ("GeForce RTX 4090", 9.0),
        ("GeForce RTX 4060", 7.5),
        ("GeForce RTX 3050", 5.5),
        ("GeForce GTX 1650", 4.5),
        ("NVIDIA MX 550", 3.5),
        ("Radeon RX 7600M", 3.5),
        ("Intel Arc A370M", 4.0),
        ("Intel Iris Xe (iGPU)", 2.0),
        ("Radeon Graphics (iGPU)", 2.0),
    ])
    def test_known_gpus(self, gpu, min_expected):
        score = get_gpu_score(gpu)
        assert score >= min_expected, f"GPU '{gpu}' scored {score}, expected >= {min_expected}"

    def test_igpu_780m_bonus(self):
        score = get_gpu_score("Radeon 780M (iGPU)")
        assert score >= 3.0

    def test_apple_m4(self):
        score = get_gpu_score("Apple M4 GPU")
        assert score >= 8.0

    def test_discrete_unknown(self):
        score = get_gpu_score("Some NVIDIA discrete card")
        assert score >= 3.5

    def test_unknown_gpu_default(self):
        assert get_gpu_score("Bilinmeyen GPU") == 2.0


# ============================================================================
# Helper functions
# ============================================================================
class TestCpuSuffix:
    @pytest.mark.parametrize("text,expected", [
        ("I7-13700HX", "hx"),
        ("I7-13700H", "h"),
        ("I5-1335U", ""),   # "U" at end of model number, no space/dash before
        ("I5-1340P", ""),   # "P" at end of model number, no space/dash before
        ("M2", ""),
        ("Ultra 7 255V", "p"),  # Ultra V series -> 'p'
    ])
    def test_suffix_detection(self, text, expected):
        assert _cpu_suffix(text) == expected


class TestHasDgpu:
    def test_igpu(self):
        assert _has_dgpu("Intel Iris Xe (iGPU)") is False
        assert _has_dgpu("Integrated (generic)") is False

    def test_dgpu(self):
        assert _has_dgpu("GeForce RTX 4060") is True
        assert _has_dgpu("Radeon RX 7600M") is True


class TestIsNvidiaCuda:
    def test_nvidia(self):
        assert _is_nvidia_cuda("GeForce RTX 4060") is True

    def test_non_nvidia(self):
        assert _is_nvidia_cuda("Radeon RX 7600M") is False
        assert _is_nvidia_cuda("Intel Iris Xe (iGPU)") is False


class TestRtxTier:
    def test_rtx_4060(self):
        assert _rtx_tier("GeForce RTX 4060") == 4060

    def test_no_rtx(self):
        assert _rtx_tier("GTX 1650") == 0

    def test_rtx_5090(self):
        assert _rtx_tier("rtx 5090") == 5090


class TestIsHeavyDgpuForDev:
    def test_heavy(self):
        assert _is_heavy_dgpu_for_dev("GeForce RTX 4060") is True
        assert _is_heavy_dgpu_for_dev("GeForce RTX 4070") is True

    def test_not_heavy(self):
        assert _is_heavy_dgpu_for_dev("GeForce GTX 1650") is False
        assert _is_heavy_dgpu_for_dev("Intel Iris Xe (iGPU)") is False

    def test_empty(self):
        assert _is_heavy_dgpu_for_dev("") is False
        assert _is_heavy_dgpu_for_dev(None) is False


# ============================================================================
# _safe_num
# ============================================================================
class TestSafeNum:
    def test_normal(self):
        assert _safe_num(42.0, 0) == 42.0

    def test_none(self):
        assert _safe_num(None, 8) == 8

    def test_nan(self):
        assert _safe_num(float("nan"), 8) == 8

    def test_invalid_string(self):
        assert _safe_num("abc", 5) == 5

    def test_string_number(self):
        assert _safe_num("16", 8) == 16.0


# ============================================================================
# _series_with_default
# ============================================================================
class TestSeriesWithDefault:
    def test_existing_column(self):
        df = pd.DataFrame({"ram_gb": [16, np.nan, 8]})
        result = _series_with_default(df, "ram_gb", 4.0)
        assert result.tolist() == [16.0, 4.0, 8.0]

    def test_missing_column(self):
        df = pd.DataFrame({"other": [1, 2, 3]})
        result = _series_with_default(df, "ram_gb", 8.0)
        assert result.tolist() == [8.0, 8.0, 8.0]


# ============================================================================
# get_dynamic_weights
# ============================================================================
class TestGetDynamicWeights:
    @pytest.mark.parametrize("usage", ["gaming", "portability", "productivity", "design", "dev"])
    def test_weights_sum_to_100(self, usage):
        weights = get_dynamic_weights(usage)
        total = sum(weights.values())
        assert abs(total - 100.0) < 0.1, f"Usage '{usage}' weights sum = {total}"

    def test_unknown_usage_uses_base(self):
        weights = get_dynamic_weights("unknown_usage")
        assert "price" in weights
        total = sum(weights.values())
        assert abs(total - 100.0) < 0.1

    def test_gaming_emphasizes_performance(self):
        weights = get_dynamic_weights("gaming")
        assert weights["performance"] > weights["battery"]

    def test_portability_emphasizes_portability(self):
        weights = get_dynamic_weights("portability")
        assert weights["portability"] > weights["performance"]


# ============================================================================
# calculate_score
# ============================================================================
class TestCalculateScore:
    def test_returns_tuple(self, sample_laptop_row, base_preferences):
        score, breakdown = calculate_score(sample_laptop_row, base_preferences)
        assert isinstance(score, (int, float))
        assert isinstance(breakdown, str)
        assert 0 <= score <= 100

    def test_gaming_score(self, sample_laptop_row, gaming_preferences):
        score, _ = calculate_score(sample_laptop_row, gaming_preferences)
        assert 0 <= score <= 100

    def test_dev_web_score(self, sample_laptop_row, dev_web_preferences):
        score, _ = calculate_score(sample_laptop_row, dev_web_preferences)
        assert 0 <= score <= 100

    def test_out_of_budget_lower_score(self, sample_laptop_row, base_preferences):
        # Way over budget
        expensive = {**sample_laptop_row, "price": 200000}
        prefs = {**base_preferences, "min_budget": 10000, "max_budget": 20000}
        score, _ = calculate_score(expensive, prefs)
        # In-budget laptop
        cheap = {**sample_laptop_row, "price": 15000}
        score_in, _ = calculate_score(cheap, prefs)
        assert score < score_in

    def test_breakdown_contains_parts(self, sample_laptop_row, base_preferences):
        _, breakdown = calculate_score(sample_laptop_row, base_preferences)
        for part in ["price", "performance", "ram", "storage", "brand", "battery", "portability"]:
            assert part in breakdown


# ============================================================================
# compute_dev_fit
# ============================================================================
class TestComputeDevFit:
    def test_web_mode(self, sample_laptop_row):
        fit = compute_dev_fit(sample_laptop_row, "web")
        assert 0 <= fit <= 100

    def test_ml_needs_dgpu(self):
        row = {
            "ram_gb": 32, "ssd_gb": 1024, "cpu": "I7-13700H",
            "gpu_norm": "Intel Iris Xe (iGPU)", "gpu_score": 2.5,
            "screen_size": 15.6, "os": "windows",
        }
        fit = compute_dev_fit(row, "ml")
        assert fit == 0.0  # ML mode requires dGPU

    def test_ml_with_dgpu(self):
        row = {
            "ram_gb": 32, "ssd_gb": 1024, "cpu": "I7-13700H",
            "gpu_norm": "GeForce RTX 4060", "gpu_score": 8.0,
            "screen_size": 15.6, "os": "windows",
        }
        fit = compute_dev_fit(row, "ml")
        assert fit > 0

    def test_mobile_mode(self, sample_laptop_row):
        fit = compute_dev_fit(sample_laptop_row, "mobile")
        assert 0 <= fit <= 100

    def test_general_mode(self, sample_laptop_row):
        fit = compute_dev_fit(sample_laptop_row, "general")
        assert 0 <= fit <= 100


# ============================================================================
# filter_by_usage
# ============================================================================
class TestFilterByUsage:
    def test_gaming_filter(self, sample_laptop_df, gaming_preferences):
        result = filter_by_usage(sample_laptop_df, "gaming", gaming_preferences)
        # Should exclude low-GPU laptops and Apple
        if not result.empty:
            assert (result["gpu_score"] >= 5.0).all()
            assert not result["brand"].str.contains("apple").any()

    def test_portability_filter(self, sample_laptop_df, base_preferences):
        result = filter_by_usage(sample_laptop_df, "portability", base_preferences)
        if not result.empty:
            assert (result["screen_size"] <= 15.6).all()

    def test_productivity_filter(self, sample_laptop_df, base_preferences):
        result = filter_by_usage(sample_laptop_df, "productivity", base_preferences)
        # Should keep laptops with decent RAM/CPU
        assert len(result) >= 1

    def test_design_filter(self, sample_laptop_df, base_preferences):
        prefs = {**base_preferences, "usage_key": "design"}
        result = filter_by_usage(sample_laptop_df, "design", prefs)
        # Design needs ram >= 16 and gpu >= 4
        if not result.empty:
            assert (result["ram_gb"] >= 16).all() or len(result) < 5

    def test_relaxation_on_empty(self):
        """When filter is too strict and <5 results, relaxation should kick in."""
        df = pd.DataFrame({
            "name": [f"Laptop {i}" for i in range(10)],
            "price": [20000] * 10,
            "brand": ["asus"] * 10,
            "cpu": ["I5-1335U"] * 10,
            "gpu": ["integrated"] * 10,
            "gpu_norm": ["Intel Iris Xe (iGPU)"] * 10,
            "ram_gb": [12.0] * 10,   # 12 GB to pass relaxed RAM >= 12
            "ssd_gb": [256.0] * 10,
            "screen_size": [15.6] * 10,
            "cpu_score": [6.0] * 10,
            "gpu_score": [2.5] * 10,
            "os": ["windows"] * 10,
        })
        prefs = {"usage_key": "design"}
        result = filter_by_usage(df, "design", prefs)
        # Relaxation should return something since len(df) > 5
        assert len(result) > 0


# ============================================================================
# get_recommendations
# ============================================================================
class TestGetRecommendations:
    def test_returns_dataframe(self, sample_laptop_df, base_preferences):
        result = get_recommendations(sample_laptop_df, base_preferences, top_n=3)
        assert isinstance(result, pd.DataFrame)

    def test_respects_top_n(self, sample_laptop_df, base_preferences):
        result = get_recommendations(sample_laptop_df, base_preferences, top_n=2)
        assert len(result) <= 2

    def test_empty_on_no_budget_match(self, sample_laptop_df):
        prefs = {
            "min_budget": 1000000,
            "max_budget": 2000000,
            "usage_key": "productivity",
            "usage_label": "Test",
        }
        result = get_recommendations(sample_laptop_df, prefs)
        assert result.empty

    def test_gaming_recommendations(self, sample_laptop_df, gaming_preferences):
        result = get_recommendations(sample_laptop_df, gaming_preferences, top_n=3)
        assert isinstance(result, pd.DataFrame)
        # If results exist, they should have scores
        if not result.empty:
            assert "score" in result.columns

    def test_score_column_present(self, sample_laptop_df, base_preferences):
        result = get_recommendations(sample_laptop_df, base_preferences, top_n=5)
        if not result.empty:
            assert "score" in result.columns
            assert "score_breakdown" in result.columns
            assert result["score"].between(0, 100).all()

    def test_metadata_attrs(self, sample_laptop_df, base_preferences):
        result = get_recommendations(sample_laptop_df, base_preferences, top_n=3)
        if not result.empty:
            assert "usage_label" in result.attrs
            assert "avg_score" in result.attrs
