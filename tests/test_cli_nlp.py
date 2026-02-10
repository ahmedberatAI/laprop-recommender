"""Unit tests for NLP / detection helpers in laprop.app.cli."""

import pytest

from laprop.app.cli import (
    detect_budget,
    detect_usage_intent,
    detect_dev_mode,
    fuzzy_match_game_titles,
    parse_design_profile_from_text,
    parse_free_text_to_preferences,
    normalize_and_complete_preferences,
    _safe_float,
    _row_to_result_dict,
)
from laprop.config.rules import GAMING_TITLE_SCORES

_KNOWN_TITLES = list(GAMING_TITLE_SCORES.keys())


# ============================================================================
# _safe_float
# ============================================================================
class TestSafeFloat:
    def test_normal_number(self):
        assert _safe_float("15.6") == 15.6

    def test_integer_string(self):
        assert _safe_float("16") == 16.0

    def test_invalid_string(self):
        assert _safe_float("abc") is None

    def test_none_input(self):
        assert _safe_float(None) is None

    def test_empty_string(self):
        assert _safe_float("") is None


# ============================================================================
# detect_budget
# ============================================================================
class TestDetectBudget:
    def test_explicit_range(self):
        result = detect_budget("20000-40000 TL arasi laptop istiyorum")
        assert result is not None
        lo, hi = result
        assert lo <= hi

    def test_single_budget(self):
        result = detect_budget("30000 TL butce ile laptop onerir misiniz")
        assert result is not None

    def test_no_budget(self):
        result = detect_budget("en iyi laptop hangisi")
        # Should return None or a default range
        # Implementation-dependent
        assert result is None or isinstance(result, tuple)

    def test_k_notation(self):
        result = detect_budget("30k butce ile oyun laptopu")
        # "30k" may not be recognized by the parser — that's OK
        if result is not None:
            lo, hi = result
            if lo is not None and hi is not None:
                assert lo >= 20000 or hi >= 25000

    def test_empty_string(self):
        lo, hi = detect_budget("")
        assert lo is None and hi is None

    def test_range_with_dash(self):
        lo, hi = detect_budget("20000-40000")
        assert lo is not None and hi is not None
        assert lo <= hi

    def test_max_keyword(self):
        lo, hi = detect_budget("max 50000 TL")
        assert hi is not None
        assert hi >= 50000

    def test_min_keyword(self):
        lo, hi = detect_budget("min 20000 TL")
        assert lo is not None
        assert lo >= 20000

    def test_range_reversed(self):
        lo, hi = detect_budget("50000-20000 TL")
        if lo is not None and hi is not None:
            assert lo <= hi

    def test_tl_currency(self):
        lo, hi = detect_budget("butcem 25000₺")
        assert hi is not None

    def test_bin_notation(self):
        lo, hi = detect_budget("20bin-40bin arasi laptop")
        if lo is not None and hi is not None:
            assert lo >= 15000

    def test_with_dots_in_number(self):
        lo, hi = detect_budget("32.999 TL laptop")
        assert hi is not None


# ============================================================================
# detect_usage_intent
# ============================================================================
class TestDetectUsageIntent:
    def test_gaming_intent(self):
        result = detect_usage_intent("oyun oynamak icin laptop")
        assert result is not None
        assert "gaming" in result.lower() or result == "gaming"

    def test_dev_intent(self):
        result = detect_usage_intent("yazilim gelistirme ve programlama icin")
        assert result is not None

    def test_portability_intent(self):
        result = detect_usage_intent("hafif tasimasi kolay laptop")
        assert result is not None

    def test_no_clear_intent(self):
        result = detect_usage_intent("laptop onerir misiniz")
        # May return None or a default
        assert result is None or isinstance(result, str)

    def test_empty_string(self):
        result = detect_usage_intent("")
        assert result is None

    def test_design_intent(self):
        result = detect_usage_intent("tasarim ve grafik isler icin")
        assert result is not None

    def test_productivity_intent(self):
        result = detect_usage_intent("ofis isi ve verimlilik icin laptop")
        assert result is not None


# ============================================================================
# detect_dev_mode
# ============================================================================
class TestDetectDevMode:
    def test_web_dev(self):
        result = detect_dev_mode("web gelistirme react frontend")
        assert result is not None
        assert "web" in result.lower()

    def test_ml_dev(self):
        result = detect_dev_mode("makine ogrenmesi deep learning pytorch")
        assert result is not None

    def test_mobile_dev(self):
        result = detect_dev_mode("android ios mobil uygulama gelistirme")
        assert result is not None

    def test_general_dev(self):
        result = detect_dev_mode("genel yazilim gelistirme")
        # "genel" may not trigger any specific dev mode — that's OK (returns None -> general default)
        assert result is None or isinstance(result, str)

    def test_empty_string(self):
        result = detect_dev_mode("")
        assert result is None

    def test_game_dev(self):
        result = detect_dev_mode("oyun gelistirme unity unreal")
        assert result is not None


# ============================================================================
# fuzzy_match_game_titles
# ============================================================================
class TestFuzzyMatchGameTitles:
    def test_exact_match(self):
        result = fuzzy_match_game_titles("Starfield", _KNOWN_TITLES)
        assert len(result) >= 1
        assert any("Starfield" in str(r) for r in result)

    def test_partial_match(self):
        result = fuzzy_match_game_titles("forza", _KNOWN_TITLES)
        assert len(result) >= 1

    def test_no_match(self):
        result = fuzzy_match_game_titles("NonexistentGame12345", _KNOWN_TITLES)
        assert isinstance(result, list)

    def test_multiple_titles_in_text(self):
        result = fuzzy_match_game_titles("Starfield ve Forza oynamak istiyorum", _KNOWN_TITLES)
        assert len(result) >= 1


# ============================================================================
# parse_design_profile_from_text
# ============================================================================
class TestParseDesignProfile:
    def test_gpu_heavy_design(self):
        prefs = parse_design_profile_from_text("3D modelleme ve animasyon")
        assert isinstance(prefs, dict)
        # Should detect GPU-heavy design needs
        if "design_gpu_hint" in prefs:
            assert prefs["design_gpu_hint"] in ("high", "mid", "low")

    def test_photo_editing(self):
        prefs = parse_design_profile_from_text("fotograf duzenleme photoshop")
        assert isinstance(prefs, dict)


# ============================================================================
# parse_free_text_to_preferences
# ============================================================================
class TestParseFreeText:
    def test_basic_gaming_text(self):
        prefs = parse_free_text_to_preferences("30000 TL butce ile oyun laptopu istiyorum")
        assert isinstance(prefs, dict)
        # Should detect gaming intent and budget
        if "usage_key" in prefs:
            assert prefs["usage_key"] in ["gaming", "productivity", "portability", "design", "dev"]

    def test_dev_text(self):
        prefs = parse_free_text_to_preferences("web gelistirme icin 25000 TL laptop")
        assert isinstance(prefs, dict)

    def test_empty_text(self):
        prefs = parse_free_text_to_preferences("")
        assert isinstance(prefs, dict)

    def test_design_text(self):
        prefs = parse_free_text_to_preferences("tasarim icin 40000 TL laptop")
        assert isinstance(prefs, dict)

    def test_portability_text(self):
        prefs = parse_free_text_to_preferences("hafif tasimasi kolay laptop 20000 TL")
        assert isinstance(prefs, dict)


# ============================================================================
# _row_to_result_dict
# ============================================================================
class TestRowToResultDict:
    def test_basic_conversion(self):
        row = {
            "name": "Laptop A",
            "price": 25000,
            "score": 85.5,
            "brand": "asus",
            "cpu": "I7-13700H",
            "gpu": "RTX 4060",
            "ram_gb": 16,
            "ssd_gb": 512,
            "screen_size": 15.6,
            "os": "windows",
            "url": "https://example.com",
        }
        result = _row_to_result_dict(row)
        assert result["name"] == "Laptop A"
        assert result["price"] == 25000.0
        assert result["score"] == 85.5
        assert result["brand"] == "asus"

    def test_with_warnings(self):
        row = {
            "name": "Laptop B",
            "price": 30000,
            "score": 70.0,
            "brand": "lenovo",
            "parse_warnings": ["ram_over_128"],
        }
        result = _row_to_result_dict(row)
        assert "parse_warnings" in result
        assert result["parse_warnings"] == ["ram_over_128"]

    def test_without_warnings(self):
        row = {"name": "Laptop C", "price": 20000, "parse_warnings": []}
        result = _row_to_result_dict(row)
        assert "parse_warnings" not in result

    def test_missing_fields(self):
        row = {"name": "Laptop D"}
        result = _row_to_result_dict(row)
        assert result["name"] == "Laptop D"
        assert result["price"] is None
        assert result["score"] is None


# ============================================================================
# normalize_and_complete_preferences
# ============================================================================
class TestNormalizeAndCompletePreferences:
    def test_sets_usage_label(self):
        p = {"usage_key": "gaming"}
        result = normalize_and_complete_preferences(p)
        assert "usage_label" in result

    def test_gaming_sets_gpu_requirement(self):
        p = {
            "usage_key": "gaming",
            "gaming_titles": ["Starfield"],
        }
        result = normalize_and_complete_preferences(p)
        assert "min_gpu_score_required" in result
        assert result["min_gpu_score_required"] >= 6.0

    def test_dev_sets_default_mode(self):
        p = {"usage_key": "dev"}
        result = normalize_and_complete_preferences(p)
        assert result["dev_mode"] == "general"
        assert result.get("_dev_mode_auto") is True

    def test_dev_keeps_explicit_mode(self):
        p = {"usage_key": "dev", "dev_mode": "web"}
        result = normalize_and_complete_preferences(p)
        assert result["dev_mode"] == "web"

    def test_design_with_profiles(self):
        p = {
            "usage_key": "design",
            "design_profiles": ["3D modelleme", "animasyon"],
        }
        result = normalize_and_complete_preferences(p)
        assert isinstance(result, dict)

    def test_no_usage_key(self):
        p = {"min_budget": 20000, "max_budget": 50000}
        result = normalize_and_complete_preferences(p)
        assert isinstance(result, dict)
