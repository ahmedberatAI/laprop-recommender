# Streamlit Follow-ups Report

## What was missing before
- The Streamlit UI did not ask the same usage-specific follow-up questions as the CLI.
- Missing follow-ups included: gaming title selection, design sub-profile selection, productivity profile selection, and dev sub-mode selection.

## Where follow-ups are defined in the codebase
- Gaming titles:
  - `src/laprop/app/cli.py` -> `_prompt_gaming_titles()`
  - `src/laprop/config/rules.py` -> `GAMING_TITLE_SCORES`
  - Effect: CLI sets `gaming_titles` and `min_gpu_score_required` (max(6.0, selected titles score)).
- Design profiles:
  - `src/laprop/app/cli.py` -> `_prompt_design_details()`
  - `src/laprop/app/cli.py` -> `parse_design_profile_from_text()`
  - Effect: `design_profiles`, `design_gpu_hint`, `design_min_ram_hint` (used in filtering).
- Productivity profile:
  - `src/laprop/app/cli.py` -> `_prompt_productivity_details()`
  - Effect: `productivity_profile` (used in scoring for multitask weighting).
- Dev mode:
  - `src/laprop/app/cli.py` -> `get_user_preferences()` / `ask_missing_preferences()`
  - Effect: `dev_mode` (used in filtering and scoring).

## Usage -> follow-ups -> keys -> engine impact (concise map)
- gaming
  - Follow-up: game titles
  - Keys: `gaming_titles`, `min_gpu_score_required`
  - Engine impact: `filter_by_usage()` and `get_recommendations()` use GPU threshold.
- design
  - Follow-up: design sub-profiles
  - Keys: `design_profiles`, `design_gpu_hint`, `design_min_ram_hint`
  - Engine impact: `filter_by_usage()` uses GPU/RAM hints for filtering.
- productivity
  - Follow-up: productivity profile
  - Keys: `productivity_profile`
  - Engine impact: `calculate_score()` adjusts CPU/GPU weighting for multitask.
- dev
  - Follow-up: dev mode (web/ml/mobile/gamedev/general)
  - Keys: `dev_mode`
  - Engine impact: `filter_by_usage()` and `compute_dev_fit()` use dev mode.
- portability
  - Follow-up: none found in CLI.

## What changed in `streamlit_app.py`
- Added a sidebar section: **"🔎 Kullanıma özel sorular"**.
- Rendered dynamic follow-ups based on `usage_key`:
  - Gaming: multiselect game titles.
  - Design: multiselect design sub-profiles.
  - Productivity: select productivity profile.
  - Dev: select dev mode.
  - Portability: no follow-ups (info message shown).
- Added a **Reset follow-ups** button that clears only follow-up-related `st.session_state` keys.
- Reused CLI normalization via `normalize_and_complete_preferences()` to keep behavior aligned with the CLI.

## How follow-up answers are passed to the engine
Preferences dict now includes the same keys as the CLI:
- Gaming:
  - `gaming_titles` (list of selected titles)
  - `min_gpu_score_required` (set to 6.0 if no titles; otherwise derived by CLI helper)
- Design:
  - `design_profiles` (list)
  - `design_gpu_hint`, `design_min_ram_hint` (filled by CLI helper)
- Productivity:
  - `productivity_profile`
- Dev:
  - `dev_mode`

These are merged into the existing preferences and normalized with:
`normalize_and_complete_preferences(preferences)`.

---

## Checklist
1) Pull latest changes
   - `git status`
   - `git pull`
2) Run locally
   - `pip install -r requirements.txt`
   - `streamlit run streamlit_app.py`
3) Verify follow-ups appear
   - Choose **Gaming** -> see game selection
   - Choose **Design** -> see design profiles
   - Choose **Productivity** -> see productivity profile
   - Choose **Dev** -> see dev mode
4) Deploy on Streamlit Cloud
   - Push to your repo
   - Set main file to `streamlit_app.py`
5) Troubleshooting
   - "No data files detected": run `python recommender.py --run-scrapers` locally, then load data.
   - "No recommendations": widen budget or relax filters.
   - Import errors: ensure `src/` is present and dependencies are installed.
