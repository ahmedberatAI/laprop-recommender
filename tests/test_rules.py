"""Unit tests for laprop.config.rules — data integrity checks."""

import pytest

from laprop.config.rules import (
    DEV_PRESETS,
    GAMING_TITLE_SCORES,
    CPU_SCORES,
    GPU_SCORES,
    BRAND_PARAM_SCORES,
    BRAND_SCORES,
    USAGE_OPTIONS,
    BASE_WEIGHTS,
    RTX_MODEL_SCORES,
    GTX_MODEL_SCORES,
    MX_MODEL_SCORES,
    RX_MODEL_SCORES,
    IMPORTANCE_MULT,
    MIN_REQUIREMENTS,
)


class TestBaseWeights:
    def test_sum_is_100(self):
        total = sum(BASE_WEIGHTS.values())
        assert total == 100, f"BASE_WEIGHTS sum = {total}, expected 100"

    def test_all_positive(self):
        for k, v in BASE_WEIGHTS.items():
            assert v > 0, f"Weight '{k}' must be positive, got {v}"


class TestDevPresets:
    @pytest.mark.parametrize("mode", ["web", "ml", "mobile", "gamedev", "general"])
    def test_preset_has_required_keys(self, mode):
        p = DEV_PRESETS[mode]
        required = {"min_ram", "min_ssd", "screen_max", "prefer_os",
                     "need_dgpu", "need_cuda", "cpu_bias", "port_bias"}
        assert required.issubset(set(p.keys())), f"Missing keys in {mode}: {required - set(p.keys())}"

    def test_ml_requires_cuda(self):
        assert DEV_PRESETS["ml"]["need_cuda"] is True

    def test_web_no_dgpu(self):
        assert DEV_PRESETS["web"]["need_dgpu"] is False


class TestScoringDicts:
    def test_cpu_scores_range(self):
        for key, score in CPU_SCORES.items():
            assert 0 <= score <= 10, f"CPU score for '{key}' = {score}"

    def test_gpu_scores_range(self):
        for key, score in GPU_SCORES.items():
            assert 0 <= score <= 10, f"GPU score for '{key}' = {score}"

    def test_brand_scores_range(self):
        for brand, score in BRAND_SCORES.items():
            assert 0 <= score <= 10, f"Brand score for '{brand}' = {score}"

    def test_brand_param_scores_range(self):
        for brand, usages in BRAND_PARAM_SCORES.items():
            for usage, score in usages.items():
                assert 0 <= score <= 100, f"BrandParam {brand}/{usage} = {score}"


class TestUsageOptions:
    def test_five_options(self):
        assert len(USAGE_OPTIONS) == 5

    def test_all_keys_are_tuples(self):
        for key, val in USAGE_OPTIONS.items():
            assert isinstance(val, tuple)
            assert len(val) == 2

    def test_usage_keys_known(self):
        known = {"gaming", "portability", "productivity", "design", "dev"}
        actual = {v[0] for v in USAGE_OPTIONS.values()}
        assert actual == known


class TestModelScores:
    def test_rtx_scores_positive(self):
        for code, score in RTX_MODEL_SCORES.items():
            assert score > 0, f"RTX {code} score should be positive"

    def test_gtx_scores_positive(self):
        for code, score in GTX_MODEL_SCORES.items():
            assert score > 0

    def test_mx_scores_positive(self):
        for code, score in MX_MODEL_SCORES.items():
            assert score > 0

    def test_rx_scores_positive(self):
        for code, score in RX_MODEL_SCORES.items():
            assert score > 0


class TestGamingTitleScores:
    def test_all_scores_in_range(self):
        for title, score in GAMING_TITLE_SCORES.items():
            assert 0 <= score <= 10, f"Game '{title}' score {score} out of range"

    def test_has_entries(self):
        assert len(GAMING_TITLE_SCORES) > 0
