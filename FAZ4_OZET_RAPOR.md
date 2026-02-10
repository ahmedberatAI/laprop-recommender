# FAZ 4: Mimari İyileştirmeler - Özet Rapor

## Tarih: 2026-02-10

---

## 1. cli.py Parçalama (1231 → 4 modül)

**Sorun:** Tek dosyada CLI + NLP + kullanıcı etkileşimi + görüntüleme (1231 satır "God Module").

**Çözüm:** 3 yeni modül oluşturuldu, `cli.py` ince giriş noktasına dönüştürüldü:

| Dosya | İçerik | Satır |
|-------|--------|-------|
| `app/nlp.py` | `detect_budget`, `detect_usage_intent`, `detect_dev_mode`, `fuzzy_match_game_titles`, `parse_design_profile_from_text`, `parse_free_text_to_preferences`, `normalize_and_complete_preferences`, `_safe_float` | 320 |
| `app/preferences.py` | `get_user_preferences`, `get_user_preferences_free_text`, `ask_missing_preferences`, `_prompt_design_details`, `_prompt_productivity_details`, `_prompt_gaming_titles` | 319 |
| `app/display.py` | `display_recommendations`, `inspect_data`, `inspect_scrapers_separately`, `save_data`, `_row_to_result_dict` | 332 |
| `app/cli.py` | `main()`, `run_simulation()` + re-exports | 237 |

**Geriye Uyumluluk:** `cli.py` tüm eski sembolleri re-export ediyor. `from laprop.app.cli import detect_budget` hâlâ çalışıyor.

---

## 2. engine.py Parçalama (787 → 4 modül)

**Sorun:** Tek dosyada donanım skorlama + ana skorlama + filtreleme + orkestrasyon (787 satır).

**Çözüm:** 3 yeni modül oluşturuldu:

| Dosya | İçerik | Satır |
|-------|--------|-------|
| `recommend/hardware.py` | `get_cpu_score`, `get_gpu_score`, `gpu_normalize_and_score`, `_cpu_suffix`, `_has_dgpu`, `_is_nvidia_cuda`, `_rtx_tier`, `_is_heavy_dgpu_for_dev` | 177 |
| `recommend/scoring.py` | `calculate_score`, `compute_dev_fit`, `get_dynamic_weights`, `_safe_num`, `_series_with_default` | 376 |
| `recommend/filtering.py` | `filter_by_usage`, `_apply_design_hints` | 127 |
| `recommend/engine.py` | `get_recommendations()` + re-exports | 148 |

**Geriye Uyumluluk:** `engine.py` tüm eski sembolleri re-export ediyor. `from laprop.recommend.engine import get_cpu_score` hâlâ çalışıyor.

---

## 3. `__init__.py` Temizliği (231 → 31 satır)

**Sorun:** 90+ private fonksiyon (`_safe_float`, `_cpu_suffix`, vb.) dışarıya açılıyordu. API yüzeyi gereksiz büyük.

**Çözüm:** Yalnızca 5 temel public API korundu:

```python
from .processing.read import load_data
from .processing.clean import clean_data
from .recommend.engine import get_recommendations
from .config.rules import USAGE_OPTIONS

def main(): ...
```

**Sonuç:** 231 satır → 31 satır (**%87 azalma**). Dış kullanıcılar zaten `laprop.recommend.engine`, `laprop.app.cli` gibi tam yolları kullanıyordu.

---

## Başarı Kriterleri Kontrolü

| Kriter | Hedef | Sonuç | Durum |
|--------|-------|-------|-------|
| cli.py satır sayısı | <200 | 237 (re-exports + run_simulation) | ⚠️ Yakın |
| engine.py satır sayısı | <200 | 148 | ✅ |
| `__init__.py` satır sayısı | <50 | 31 | ✅ |
| Tüm testler geçiyor | 382 | 382 passed | ✅ |
| Coverage ≥%63 | %63 | %63.0 | ✅ |
| Geriye uyumluluk | Evet | Evet (re-exports) | ✅ |
| `smoke_imports.py` | Çalışıyor | OK | ✅ |

**Not:** `cli.py` 237 satır olarak kaldı çünkü:
- `run_simulation()` 87 satırlık karmaşık fonksiyon (başka modüle taşınması anlamsız)
- 19 satır backward-compat re-export gerekli
- Ana `main()` döngüsü ~100 satır

---

## Coverage Detayı

| Modül | Önceki | Sonrası |
|-------|--------|---------|
| engine.py | %84.7 | %81.6 |
| hardware.py (YENİ) | - | %81.3 |
| scoring.py (YENİ) | - | %88.8 |
| filtering.py (YENİ) | - | %82.8 |
| `__init__.py` | %100 | %100 |
| **Toplam** | **%63.4** | **%63.0** |

---

## Yeni Dosya Yapısı

```
src/laprop/
├── __init__.py          (31 satır — sadece public API)
├── app/
│   ├── __init__.py
│   ├── cli.py           (237 satır — giriş noktası + re-exports)
│   ├── display.py       (332 satır — görüntüleme/inceleme)
│   ├── main.py
│   ├── nlp.py           (320 satır — NLP parsing)
│   └── preferences.py   (319 satır — kullanıcı tercihleri)
├── config/
│   ├── benchmarks.py
│   ├── rules.py
│   ├── scoring_constants.py
│   └── settings.py
├── recommend/
│   ├── __init__.py
│   ├── engine.py        (148 satır — orkestrasyon + re-exports)
│   ├── filtering.py     (127 satır — kullanım filtreleri)
│   ├── hardware.py      (177 satır — CPU/GPU skorlama)
│   ├── scenarios.py
│   └── scoring.py       (376 satır — ana skorlama)
├── processing/
│   ├── clean.py
│   ├── normalize.py
│   ├── read.py
│   └── validate.py
├── storage/
│   └── repository.py
└── utils/
    ├── console.py
    └── logging.py
```

---

## Değişen/Oluşan Dosyalar

| Dosya | Değişiklik |
|-------|-----------|
| `src/laprop/app/nlp.py` | **YENİ** — NLP fonksiyonları cli.py'den taşındı |
| `src/laprop/app/preferences.py` | **YENİ** — Tercih toplama fonksiyonları taşındı |
| `src/laprop/app/display.py` | **YENİ** — Görüntüleme fonksiyonları taşındı |
| `src/laprop/app/cli.py` | **YENİDEN YAZILDI** — 1231 → 237 satır (entry point) |
| `src/laprop/recommend/hardware.py` | **YENİ** — CPU/GPU skorlama engine.py'den taşındı |
| `src/laprop/recommend/scoring.py` | **YENİ** — Skor hesaplama engine.py'den taşındı |
| `src/laprop/recommend/filtering.py` | **YENİ** — Filtreleme engine.py'den taşındı |
| `src/laprop/recommend/engine.py` | **YENİDEN YAZILDI** — 787 → 148 satır (orchestrator) |
| `src/laprop/__init__.py` | **YENİDEN YAZILDI** — 231 → 31 satır (public API only) |
