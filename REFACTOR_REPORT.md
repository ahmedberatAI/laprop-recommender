# Refactor Report: recommender_2

This project was refactored from a single monolithic script (`recommender.py`) into a modular, pipeline-based package under `src/laprop/`.

Key goals of the refactor:
- Preserve runtime behavior and the existing CLI flow.
- Preserve all logic (no code loss): every function/constant from the old monolith still exists (moved into modules and re-exported).
- Keep default file names/paths unchanged (CSV outputs, cache, etc.).
- Avoid circular imports and keep imports explicit.
- Provide a new package entrypoint while keeping `python recommender.py` working.

---

## 1) What Changed (Architecture Overview)

### New package layout

```
recommender_2/
  recommender.py              # legacy wrapper (unchanged UX)
  laprop/                     # shim package so `import laprop` works from repo root
  sitecustomize.py            # keeps `src/` importable in common setups
  scripts/
    smoke_imports.py
  src/
    laprop/
      __init__.py
      app/
      config/
      ingestion/
      processing/
      recommend/
      storage/
```

### `src/laprop/app`
Responsibility: user interaction + entrypoints.
- Owns the CLI/menu flow and argument parsing.
- Keeps the interactive prompts (classic Q/A + free-text mode) intact.
- Provides a new module entrypoint (`python -m laprop.app.main`).

### `src/laprop/config`
Responsibility: configuration, constants, presets, and optional benchmark loading.
- Centralizes project paths (project root, CSV paths, cache paths) in one place.
- Holds all scoring presets, weights, thresholds, and brand/rule tables.
- Loads optional benchmark CSVs (if present) without changing fallback behavior.

### `src/laprop/ingestion`
Responsibility: scraper orchestration.
- Runs the existing top-level scrapers via `subprocess`.
- Keeps the same default outputs (`amazon_laptops.csv`, `vatan_laptops.csv`, `incehesap_laptops.csv`).
- Provides a single orchestration function used by the CLI (`run_scrapers`).

### `src/laprop/processing`
Responsibility: data loading, standardization, parsing/normalization, and cleaning.
- Loads CSVs robustly (encoding fallbacks, delimiter handling, column name normalization).
- Normalizes structured signals from titles (CPU/GPU/RAM/SSD/screen parsing helpers).
- Cleans/validates the combined dataset and computes derived columns (scores, OS detection, etc.).

### `src/laprop/recommend`
Responsibility: recommendation logic + scenarios.
- Contains the recommendation engine (filtering and scoring).
- Holds the large simulation scenario list in its own module.
- Keeps scoring math and heuristics exactly as before.

### `src/laprop/storage`
Responsibility: file I/O helpers and persistent artifacts.
- Updates `all_data.csv` by appending new scrape results with timestamps.
- Keeps file names and output formats unchanged.

### Supporting files added
- `src/laprop/__init__.py`: re-exports the public API (constants + functions) so legacy code can still access them from one place.
- `laprop/__init__.py` (repo root): a shim so `import laprop` works when running from the repo root without extra env setup.
- `sitecustomize.py`: adds `src/` to `sys.path` in environments where Python loads `sitecustomize`.
- `scripts/smoke_imports.py`: minimal smoke test that imports `laprop` and prints `OK`.

---

## 2) Module Map (Old 

All functions/constants from the old `recommender.py` were moved to modules below and are re-exported by `src/laprop/__init__.py`.

| Old location (recommender.py section/function) | New file |
|-----------------------------------------------|----------|
| `main` (CLI entry) | `src/laprop/app/cli.py` |
| `python recommender.py` legacy entry | `recommender.py` (thin wrapper) |
| new entrypoint | `src/laprop/app/main.py` |
| CLI prompts: `_prompt_design_details`, `_prompt_productivity_details`, `_prompt_gaming_titles` | `src/laprop/app/cli.py` |
| user prefs (classic): `get_user_preferences` | `src/laprop/app/cli.py` |
| user prefs (free-text): `get_user_preferences_free_text` | `src/laprop/app/cli.py` |
| free-text parsing: `detect_budget`, `detect_usage_intent`, `detect_dev_mode` | `src/laprop/app/cli.py` |
| free-text parsing: `fuzzy_match_game_titles`, `parse_design_profile_from_text` | `src/laprop/app/cli.py` |
| free-text parsing: `parse_free_text_to_preferences`, `normalize_and_complete_preferences`, `ask_missing_preferences` | `src/laprop/app/cli.py` |
| simulation helpers: `_safe_float`, `_row_to_result_dict` | `src/laprop/app/cli.py` |
| simulation runner: `run_simulation` | `src/laprop/app/cli.py` |
| output/UI helpers: `display_recommendations`, `inspect_data`, `save_data`, `inspect_scrapers_separately` | `src/laprop/app/cli.py` |
| scraper orchestration: `run_scrapers` | `src/laprop/ingestion/orchestrator.py` |
| scraper script registry: `SCRAPERS` | `src/laprop/config/settings.py` |
| default data files list: `DATA_FILES` | `src/laprop/config/settings.py` |
| cache and all-data paths: `CACHE_FILE`, `ALL_DATA_FILE` | `src/laprop/config/settings.py` |
| optional bench paths and loader: `BENCH_GPU_PATH`, `BENCH_CPU_PATH`, `_safe_load_bench` | `src/laprop/config/benchmarks.py` |
| loaded bench globals: `GPU_BENCH`, `CPU_BENCH` | `src/laprop/config/benchmarks.py` |
| rules/presets: `DEV_PRESETS` | `src/laprop/config/rules.py` |
| rules/constants: `GAMING_TITLE_SCORES`, `CPU_SCORES`, `GPU_SCORES` | `src/laprop/config/rules.py` |
| rules/constants: `BRAND_SCORES`, `BRAND_PARAM_SCORES` | `src/laprop/config/rules.py` |
| rules/constants: `USAGE_OPTIONS`, `BASE_WEIGHTS`, model score maps | `src/laprop/config/rules.py` |
| rules/constants: `IMPORTANCE_MULT`, `MIN_REQUIREMENTS` | `src/laprop/config/rules.py` |
| scenario list: `SCENARIOS` | `src/laprop/recommend/scenarios.py` |
| CSV read + column standardization: `_sanitize_column_name`, `_standardize_columns` | `src/laprop/processing/read.py` |
| CSV diagnostics helpers: `_count_filled_urls`, `_get_domain_counts` | `src/laprop/processing/read.py` |
| CSV loading: `read_csv_robust` | `src/laprop/processing/read.py` |
| dataset loading + caching: `load_data` | `src/laprop/processing/read.py` |
| title normalization: `_normalize_title_text` | `src/laprop/processing/normalize.py` |
| CPU/GPU title parsing: `normalize_cpu`, `normalize_gpu` | `src/laprop/processing/normalize.py` |
| GPU label normalization: `normalize_gpu_model` | `src/laprop/processing/normalize.py` |
| RAM/SSD/screen parsing: `parse_ram_gb`, `parse_ssd_gb`, `parse_screen_size` | `src/laprop/processing/normalize.py` |
| SSD candidate helpers/constants | `src/laprop/processing/normalize.py` |
| validators: `validate_record` | `src/laprop/processing/validate.py` |
| cleaning helpers: `clean_price`, `extract_brand`, `clean_ram_value`, `clean_ssd_value` | `src/laprop/processing/clean.py` |
| main cleaner: `clean_data` | `src/laprop/processing/clean.py` |
| CPU/GPU scoring helpers: `get_cpu_score`, `get_gpu_score` | `src/laprop/recommend/engine.py` |
| dev-fit helpers: `_cpu_suffix`, `_has_dgpu`, `_is_nvidia_cuda`, `_rtx_tier`, `_is_heavy_dgpu_for_dev`, `compute_dev_fit` | `src/laprop/recommend/engine.py` |
| scoring: `_safe_num`, `_series_with_default`, `calculate_score` | `src/laprop/recommend/engine.py` |
| dynamic weights: `get_dynamic_weights` | `src/laprop/recommend/engine.py` |
| filtering: `filter_by_usage` | `src/laprop/recommend/engine.py` |
| ranking output: `get_recommendations` | `src/laprop/recommend/engine.py` |
| append scrape history: `append_to_all_data` | `src/laprop/storage/repository.py` |

Note: `src/laprop/processing/merge.py` and `src/laprop/recommend/explain.py` exist as thin placeholders for structure; the current runtime continues using the original logic paths from the monolith.

---

## 3) Backward Compatibility Guarantees

### CLI behavior
- `python recommender.py` still starts the same program flow (same argument flags, same interactive menu, same defaults).
- The legacy wrapper `recommender.py` only adds `src/` to `sys.path` and then calls the new entrypoint.

### Data files and cache paths
All default filenames remain unchanged and still resolve relative to the project root:
- `amazon_laptops.csv`
- `vatan_laptops.csv`
- `incehesap_laptops.csv`
- `all_data.csv`
- `laptop_cache.pkl`

These are defined in `src/laprop/config/settings.py` with `BASE_DIR` pointing at the same repo root where the legacy `recommender.py` lives.

### Scrapers are untouched
- Existing scraper scripts remain top-level and runnable directly as before:
  - `amazon_scraper.py`
  - `incehesap_scraper.py`
  - `vatan_scraper.py`
- The refactor does not modify scraper logic; `run_scrapers()` still executes these scripts via `subprocess`.

### Imports and safety
- `src/laprop/__init__.py` re-exports the public API so code moved out of the monolith remains accessible.
- Import failures are surfaced clearly via an `ImportError` message (both in the legacy wrapper and package init).

---

## 4) How to Run the Project (Step by step)

### Prerequisites
1. Use Python 3.9+.
2. Ensure dependencies are installed (at minimum: `pandas`, `numpy`).

### Option A  Legacy mode (unchanged)
```bash
python recommender.py
```

Common flags:
```bash
python recommender.py --help
python recommender.py --run-scrapers
python recommender.py --debug
python recommender.py --nl
```

### Option B  Package mode (new entry)
Run the same CLI via the module entrypoint:
```bash
python -m laprop.app.main
```

Flags are the same:
```bash
python -m laprop.app.main --help
python -m laprop.app.main --run-scrapers
python -m laprop.app.main --debug
python -m laprop.app.main --nl
```

### Option C  Smoke checks (no network)
```bash
python scripts/smoke_imports.py
python -c "import laprop; print('import ok')"
```

### Scrapers (still runnable directly)
```bash
python amazon_scraper.py
python incehesap_scraper.py
python vatan_scraper.py
```

---

## Appendix: Quick Pointers

- The legacy wrapper is `recommender.py`.
- The new CLI implementation is `src/laprop/app/cli.py`.
- Core scoring/filtering logic is `src/laprop/recommend/engine.py`.
- Data loading/caching is `src/laprop/processing/read.py`.
- Data cleaning/parsing is split across `src/laprop/processing/clean.py` and `src/laprop/processing/normalize.py`.
- All default file paths are centralized in `src/laprop/config/settings.py`.
