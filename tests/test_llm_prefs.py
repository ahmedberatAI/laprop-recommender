"""Unit tests for optional LLM preference parsing helpers."""

from laprop.app.llm_prefs import (
    merge_preferences,
    parse_preferences_hybrid,
    sanitize_preferences,
)


class TestSanitizePreferences:
    def test_keeps_known_keys_and_normalizes_types(self):
        raw = {
            "usage_key": "DEV",
            "min_budget": "35000",
            "max_budget": 65000,
            "dev_mode": "Web",
            "screen_max": "14.0",
            "design_profiles": ["Graphic", "invalid"],
            "design_gpu_hint": "MID",
            "design_min_ram_hint": "32",
            "gaming_titles": "Starfield, Forza Motorsport (2023)",
            "unknown": "drop-me",
        }

        out = sanitize_preferences(raw)

        assert out["usage_key"] == "dev"
        assert out["min_budget"] == 35000.0
        assert out["max_budget"] == 65000.0
        assert out["dev_mode"] == "web"
        assert out["screen_max"] == 14.0
        assert out["design_profiles"] == ["graphic"]
        assert out["design_gpu_hint"] == "mid"
        assert out["design_min_ram_hint"] == 32
        assert out["gaming_titles"] == ["Starfield", "Forza Motorsport (2023)"]
        assert "unknown" not in out


class TestMergePreferences:
    def test_fills_only_missing_values(self):
        primary = {"usage_key": "portability", "min_budget": 28000.0}
        fallback = {"usage_key": "dev", "min_budget": 25000.0, "max_budget": 45000.0, "screen_max": 14.0}

        merged = merge_preferences(primary=primary, fallback=fallback)

        assert merged["usage_key"] == "portability"
        assert merged["min_budget"] == 28000.0
        assert merged["max_budget"] == 45000.0
        assert merged["screen_max"] == 14.0


class TestParsePreferencesHybrid:
    def test_llm_plus_rule_fallback_merge(self, monkeypatch):
        monkeypatch.setattr(
            "laprop.app.llm_prefs.parse_free_text_to_preferences",
            lambda _text: {"usage_key": "portability", "screen_max": 14.0, "max_budget": 45000.0},
        )
        monkeypatch.setattr(
            "laprop.app.llm_prefs.try_parse_preferences_with_llm",
            lambda _text: {"usage_key": "portability", "min_budget": 28000.0, "max_budget": 45000.0},
        )

        merged = parse_preferences_hybrid("28.000-45.000 TL, ultrabook tarzi")

        assert merged["usage_key"] == "portability"
        assert merged["min_budget"] == 28000.0
        assert merged["max_budget"] == 45000.0
        # LLM missed this field; fallback fills it.
        assert merged["screen_max"] == 14.0

    def test_rule_only_when_llm_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            "laprop.app.llm_prefs.parse_free_text_to_preferences",
            lambda _text: {"usage_key": "dev", "dev_mode": "web"},
        )
        monkeypatch.setattr(
            "laprop.app.llm_prefs.try_parse_preferences_with_llm",
            lambda _text: {},
        )

        prefs = parse_preferences_hybrid("node, web backend")
        assert prefs == {"usage_key": "dev", "dev_mode": "web"}

