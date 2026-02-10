# FAZ 2: Test Altyapisi - Ozet Rapor

## Sonuc Ozeti

| Kriter | Hedef | Gerceklesen | Durum |
|--------|-------|-------------|-------|
| Toplam test sayisi | 40-50+ | **379** | BASARILI |
| Genel coverage | %60+ | **%61.6** | BASARILI |
| normalize.py coverage | %80+ | **%92.1** | BASARILI |
| engine.py coverage | %70+ | **%81.6** | BASARILI |
| clean.py coverage | - | **%85.2** | BASARILI |
| read.py parquet test | En az 1 | **7 test** | BASARILI |
| Integration test | En az 1 | **7 test** | BASARILI |
| CI pipeline | Calisiyor | **GitHub Actions** | BASARILI |

---

## 1. Pytest Altyapisi

### Konfigurason (pyproject.toml)
- `[tool.pytest.ini_options]` — test paths, markers (slow, integration), strict mode
- `[tool.coverage.run]` — source_pkgs=laprop, omit patterns
- `[tool.coverage.report]` — show_missing, exclude_lines

### Shared Fixtures (conftest.py)
- `sample_laptop_row` — tek laptop satiri dict
- `sample_laptop_df` — 5 farkli laptoplu DataFrame (ASUS, Lenovo, Apple, MSI, HP)
- `base_preferences` / `gaming_preferences` / `dev_web_preferences` — farkli senaryo tercihleri
- `raw_csv_df` — temizleme oncesi ham CSV formatinda veri
- `tmp_cache_dir` — gecici dizin (cache testleri icin)

---

## 2. Test Dosyalari ve Kapsam

### test_normalize.py (113 test)
Hedef: %80+ → Gerceklesen: **%92.1**
- `_normalize_title_text` — 5 test (None, lowercase, inc/inch, virgul/nokta, non-ASCII)
- `normalize_gpu_model` — 20 test (RTX, GTX, MX, RX, Arc, Iris, UHD, Vega, iGPU, Apple, fallbacks)
- `normalize_cpu` — 9 test (Intel i-serisi, Ryzen, Ultra, Apple M, no match)
- `normalize_gpu` — 9 test (RTX, GTX, MX, RX, Arc, Iris, UHD, Apple GPU, None)
- `_normalize_capacity_gb` — 6 test (500->512, 1000->1024, 2000->2048)
- `_extract_capacity_candidates` — 3 test (GB, TB, no match)
- `_extract_no_unit_ssd_candidates` — 3 test (SSD/NVMe ile, TB, no match)
- `_window_has_any` / `_score_ssd_candidate` — 4 test (pozitif/negatif skor)
- `_coerce_int` — 5 test (None, NaN, float, string, invalid)
- `_is_valid_ssd_value` — 5 test (valid, form factor, too small/large, None)
- `_find_larger_ssd_in_title` — 3 test
- `parse_ram_gb` — 6 parametreli test
- `sanitize_ram` — 4 test (normal, VRAM ayristirma, no match, empty)
- `parse_ssd_gb` — 5 parametreli test
- `parse_screen_size` — 16 parametreli test (birim varyantlari, edge cases)
- `_find_ram_candidates` / `_find_screen_candidates` — 4 test

### test_engine.py (77 test)
Hedef: %70+ → Gerceklesen: **%81.6**
- `get_cpu_score` — 11 test (NA, i3-i9, Ryzen, M4, Ultra, HX bonus)
- `get_gpu_score` — 13 test (NA, RTX/GTX/MX/RX, Arc, iGPU, Apple, discrete, unknown)
- `_cpu_suffix` — 6 parametreli test
- `_has_dgpu` / `_is_nvidia_cuda` / `_rtx_tier` / `_is_heavy_dgpu_for_dev` — 12 test
- `_safe_num` — 5 test
- `_series_with_default` — 2 test
- `get_dynamic_weights` — 7 test (5 usage tipi sum=100, gaming performance, portability)
- `calculate_score` — 5 test (tuple format, gaming/dev/budget, breakdown)
- `compute_dev_fit` — 5 test (web, ml dgpu, ml+dgpu, mobile, general)
- `filter_by_usage` — 5 test (gaming, portability, productivity, design, relaxation)
- `get_recommendations` — 6 test (DataFrame, top_n, budget, gaming, score, metadata)

### test_clean.py (47 test)
Coverage: **%85.2**
- `clean_ram_value` — 10 test
- `clean_ssd_value` — 8 test
- `clean_price` — 8 parametreli test
- `extract_brand` — 17 test (12 marka + keyword variants)
- `clean_data` — 5 integration-like test (columns, invalid price, low price, flow, vatan filter)

### test_read.py (21 test)
Coverage: **%64.2**
- `_sanitize_column_name` — 3 test
- `_standardize_columns` — 2 test (lowercase, BOM merge)
- `_count_filled_urls` — 2 test
- `_get_domain_counts` — 2 test
- `read_csv_robust` — 5 test (UTF-8, BOM, invalid, semicolon, cp1254)
- `_save_cache` / `_load_cache` — 4 test (round-trip, mismatch, missing, None stats)
- `load_data` — 3 test (CSV'lerden, cache'ten, dosya yoksa)

### test_cli_nlp.py (51 test)
- `_safe_float` — 5 test
- `detect_budget` — 12 test (range, single, none, k, empty, dash, max/min, reversed, TL, bin, dots)
- `detect_usage_intent` — 7 test (gaming, dev, portability, design, productivity, none, empty)
- `detect_dev_mode` — 6 test (web, ml, mobile, general, empty, gamedev)
- `fuzzy_match_game_titles` — 4 test
- `parse_design_profile_from_text` — 2 test
- `parse_free_text_to_preferences` — 5 test
- `_row_to_result_dict` — 4 test
- `normalize_and_complete_preferences` — 6 test

### test_repository.py (17 test)
- `_normalize_key_value` — 6 test (None, NaN, float, string)
- `_build_row_key` — 3 test (URL, fallback, None URL)
- `_iter_existing_keys` — 3 test (nonexistent, existing, corrupt)
- `_dedupe_dataframe` — 5 test (duplicates, internal, empty, no dups, missing cols)

### test_rules.py (22 test)
- `BASE_WEIGHTS` sum=100, all positive
- `DEV_PRESETS` 5 mode, required keys, ML CUDA, web no dGPU
- `CPU_SCORES` / `GPU_SCORES` / `BRAND_SCORES` range kontrolu
- `USAGE_OPTIONS` 5 secenek, bilinen key'ler
- Model skorlari (RTX, GTX, MX, RX) pozitif kontrol
- `GAMING_TITLE_SCORES` range kontrol

### test_validate.py (5 test)
Coverage: **%100**

### test_console.py (14 test)
- `_get_encoding` — 2 test
- `safe_str` — 5 test (string, unicode, bytes, non-string, None)
- `safe_print` — 7 test (stream, multi args, sep, end, flush, unexpected kwargs, unicode)

### test_logging.py (4 test)
Coverage: **%84.4**

### test_integration.py (7 test) `@pytest.mark.integration`
- `clean_data` uretim kontrol
- Tam pipeline: productivity, gaming, portability, dev_web
- Determinizm testi (ayni girdi = ayni cikti)
- `filter_by_usage` temiz veri ile

---

## 3. CI Pipeline (GitHub Actions)

Dosya: `.github/workflows/ci.yml`

### test job
- **Matrix**: Python 3.10, 3.11, 3.12, 3.13
- **Adimlar**: checkout → setup python → cache pip → install → pytest --cov
- Coverage minimum: %55 (fail-under)
- Coverage XML artifact upload (3.12 icin)

### lint job
- Import yapisi kontrolu: `import laprop` basarili mi?

---

## 4. Coverage Detay Tablosu

| Modul | Stmts | Miss | Cover |
|-------|-------|------|-------|
| normalize.py | 330 | 26 | **92.1%** |
| clean.py | 229 | 34 | **85.2%** |
| logging.py | 45 | 7 | **84.4%** |
| engine.py | 526 | 97 | **81.6%** |
| console.py | 46 | 12 | **73.9%** |
| read.py | 165 | 59 | **64.2%** |
| repository.py | 123 | 54 | **56.1%** |
| benchmarks.py | 44 | 24 | **45.5%** |
| cli.py | 760 | 542 | **28.7%** |
| **TOPLAM** | **2414** | **928** | **61.6%** |

### Dusuk Coverage Nedenleri
- **cli.py (%28.7)**: 760 satirlik God Module — interaktif `input()` ve `safe_print()` kullanan fonksiyonlar unit test ile test edilemez. NLP/detection fonksiyonlari test edildi.
- **orchestrator.py (%12.5)**: Scraper calistirma — subprocess/network bagimli
- **ingestion/sources/*.py (%0)**: Sadece import forwarding, 2-3 satir

---

## 5. Olusturulan / Degistirilen Dosyalar

### Yeni Dosyalar
| Dosya | Satir | Aciklama |
|-------|-------|----------|
| `tests/conftest.py` | 180 | Shared fixtures |
| `tests/test_normalize.py` | 390 | normalize.py testleri |
| `tests/test_engine.py` | 360 | engine.py testleri |
| `tests/test_clean.py` | 175 | clean.py testleri |
| `tests/test_read.py` | 270 | read.py + cache testleri |
| `tests/test_cli_nlp.py` | 270 | CLI NLP testleri |
| `tests/test_validate.py` | 63 | validate.py testleri |
| `tests/test_rules.py` | 100 | config/rules.py integrity |
| `tests/test_repository.py` | 120 | storage dedup testleri |
| `tests/test_console.py` | 60 | console.py testleri |
| `tests/test_logging.py` | 30 | logging.py testleri |
| `tests/test_integration.py` | 125 | End-to-end pipeline |
| `.github/workflows/ci.yml` | 60 | CI pipeline |

### Degistirilen Dosyalar
| Dosya | Degisiklik |
|-------|-----------|
| `pyproject.toml` | pytest, coverage config eklendi |

---

## 6. Bilinen Kisitlamalar
1. `test_scraper_smoke.py::test_incehesap_parse_list_fixture` — `lxml` parser eksik (pre-existing, FAZ 1'den once mevcut)
2. `cli.py` coverage %28.7 — interaktif fonksiyonlar (input/print) mock'lanmadan test edilemez, FAZ 3'te refactoring ile cozulebilir
3. `orchestrator.py` / `ingestion/sources/` — network/subprocess bagimli, mock-heavy test gerektirir

## 7. Calistirma Komutlari

```bash
# Tum testler
pytest tests/ -v

# Coverage raporu
pytest tests/ --cov --cov-report=term-missing --ignore=tests/test_scraper_smoke.py

# Sadece unit testler (integration haric)
pytest tests/ -m "not integration" -v

# Tek modul testi
pytest tests/test_normalize.py -v
```
