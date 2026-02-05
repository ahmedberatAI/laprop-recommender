from pathlib import Path

import os
import subprocess
from datetime import datetime
from typing import Iterable, Optional, Tuple

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent

from laprop.config.rules import USAGE_OPTIONS, DEV_PRESETS, GAMING_TITLE_SCORES
from laprop.config.settings import DATA_FILES
from laprop.processing.clean import clean_data
from laprop.processing.read import _get_domain_counts, load_data
from laprop.recommend.engine import get_recommendations
from laprop.app.cli import normalize_and_complete_preferences


SOURCE_OPTIONS = ["amazon", "incehesap", "vatan"]
SOURCE_PATTERNS = {
    "amazon": "amazon",
    "incehesap": "incehesap",
    "vatan": "vatanbilgisayar.com",
}
FOLLOWUP_KEYS = [
    "fu_gaming_titles",
    "fu_productivity_profile",
    "fu_design_profiles",
    "fu_dev_mode",
]

st.set_page_config(page_title="Laprop Recommender", page_icon="💻", layout="wide")


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_columns(df: pd.DataFrame) -> set:
    return set(df.columns) if isinstance(df, pd.DataFrame) else set()


def _source_summary(df: pd.DataFrame) -> list:
    if df is None or "url" not in df.columns:
        return []
    counts = _get_domain_counts(df["url"])
    other_count = len(df) - sum(counts.values())
    if other_count > 0:
        counts["other"] = other_count
    return [(name, count) for name, count in counts.items() if count > 0]


def _filter_sources(df: pd.DataFrame, sources: Iterable[str]) -> pd.DataFrame:
    if df is None or "url" not in df.columns:
        return df
    selected = [s for s in sources if s in SOURCE_PATTERNS]
    if not selected:
        return df.iloc[0:0]
    urls = df["url"].fillna("").astype(str).str.lower()
    mask = pd.Series([False] * len(df), index=df.index)
    for src in selected:
        pattern = SOURCE_PATTERNS[src]
        mask = mask | urls.str.contains(pattern, na=False)
    return df.loc[mask].copy()


def _is_integrated_gpu(text: str) -> bool:
    s = str(text or "").lower()
    if not s:
        return True
    hints = [
        "integrated",
        "igpu",
        "iris",
        "uhd",
        "radeon graphics",
        "vega",
        "apple m",
        "(igpu)",
    ]
    return any(h in s for h in hints)


@st.cache_data(show_spinner=False)
def _load_data_cached(use_cache: bool, sources: Tuple[str, ...]) -> Optional[pd.DataFrame]:
    df = load_data(use_cache=use_cache)
    if df is None:
        return None
    df = clean_data(df)
    return _filter_sources(df, sources)


def _price_bounds(df: pd.DataFrame) -> tuple:
    if df is None or "price" not in df.columns:
        return 0, 0
    prices = pd.to_numeric(df["price"], errors="coerce").dropna()
    if prices.empty:
        return 0, 0
    return int(prices.min()), int(prices.max())


def _apply_user_filters(
    df: pd.DataFrame,
    min_ram: int,
    min_ssd: int,
    screen_range: Optional[Tuple[float, float]],
    gpu_filter: str,
) -> pd.DataFrame:
    filtered = df.copy()
    if min_ram is not None and "ram_gb" in filtered.columns:
        ram_vals = pd.to_numeric(filtered["ram_gb"], errors="coerce").fillna(0)
        filtered = filtered[ram_vals >= float(min_ram)]
    if min_ssd is not None and "ssd_gb" in filtered.columns:
        ssd_vals = pd.to_numeric(filtered["ssd_gb"], errors="coerce").fillna(0)
        filtered = filtered[ssd_vals >= float(min_ssd)]
    if screen_range is not None and "screen_size" in filtered.columns:
        s_min, s_max = screen_range
        screen_vals = pd.to_numeric(filtered["screen_size"], errors="coerce")
        filtered = filtered[(screen_vals >= float(s_min)) & (screen_vals <= float(s_max))]
    if gpu_filter != "Any":
        gpu_col = "gpu_norm" if "gpu_norm" in filtered.columns else ("gpu" if "gpu" in filtered.columns else None)
        if gpu_col:
            is_integrated = filtered[gpu_col].apply(_is_integrated_gpu)
            if gpu_filter == "Integrated only":
                filtered = filtered[is_integrated]
            elif gpu_filter == "Dedicated only":
                filtered = filtered[~is_integrated]
    return filtered


def _data_files_exist() -> bool:
    return any(path.exists() for path in DATA_FILES)


st.title("Laprop Recommender")
st.markdown("A fast, configurable demo for laptop recommendations built on the existing Laprop engine.")
with st.expander("How it works"):
    st.markdown(
        "- Load CSVs from local data files (or cache) and clean them.\n"
        "- Apply filters and usage presets to compute recommendations.\n"
        "- Inspect details, warnings, and export results as CSV."
    )


if "data" not in st.session_state:
    st.session_state["data"] = None
if "data_loaded_at" not in st.session_state:
    st.session_state["data_loaded_at"] = None
if "data_sources" not in st.session_state:
    st.session_state["data_sources"] = SOURCE_OPTIONS.copy()
if "results" not in st.session_state:
    st.session_state["results"] = None
if "scrape_logs" not in st.session_state:
    st.session_state["scrape_logs"] = ""
if "scrape_returncode" not in st.session_state:
    st.session_state["scrape_returncode"] = None

data_df = st.session_state.get("data")

st.sidebar.header("Control Panel")

st.sidebar.subheader("Data")
use_cache = st.sidebar.checkbox("Use cache", value=True)
show_sources = data_df is None or "url" in _safe_columns(data_df)
if show_sources:
    selected_sources = st.sidebar.multiselect(
        "Sources",
        options=SOURCE_OPTIONS,
        default=st.session_state.get("data_sources", SOURCE_OPTIONS),
    )
else:
    selected_sources = st.session_state.get("data_sources", SOURCE_OPTIONS)
    st.sidebar.caption("Source selection unavailable (missing url column).")
if st.sidebar.button("📥 Load data"):
    with st.spinner("Loading data..."):
        loaded = _load_data_cached(use_cache, tuple(selected_sources))
    if loaded is None:
        st.session_state["data"] = None
        st.session_state["data_loaded_at"] = None
        st.session_state["results"] = None
        st.sidebar.error("No data found.")
    else:
        st.session_state["data"] = loaded
        st.session_state["data_loaded_at"] = _now_str()
        st.session_state["data_sources"] = selected_sources
        st.session_state["results"] = None
        st.sidebar.success(f"Loaded {len(loaded):,} rows.")

data_df = st.session_state.get("data")
if data_df is None:
    st.sidebar.warning("Status: not loaded")
else:
    st.sidebar.success("Status: loaded")
    st.sidebar.caption(f"Rows: {len(data_df):,}")
    if st.session_state.get("data_loaded_at"):
        st.sidebar.caption(f"Last load: {st.session_state['data_loaded_at']}")
    source_stats = _source_summary(data_df)
    if source_stats:
        st.sidebar.caption(
            "Sources: " + ", ".join(f"{name} ({count})" for name, count in source_stats)
        )
    elif "url" not in _safe_columns(data_df):
        st.sidebar.caption("Sources: unavailable (missing url column)")

st.sidebar.divider()
st.sidebar.subheader("Filters")

usage_items = [USAGE_OPTIONS[key] for key in sorted(USAGE_OPTIONS)]
usage_labels = [label for _, label in usage_items]
usage_label_to_key = {label: key for key, label in usage_items}
selected_label = st.sidebar.selectbox("Usage preset", usage_labels, index=0)
selected_key = usage_label_to_key.get(selected_label, "productivity")

min_price_default, max_price_default = _price_bounds(data_df)
if min_price_default <= 0 or max_price_default <= 0 or min_price_default == max_price_default:
    min_price_default, max_price_default = 10000, 80000
budget_min, budget_max = st.sidebar.slider(
    "Budget range",
    min_value=int(min_price_default),
    max_value=int(max_price_default),
    value=(int(min_price_default), int(max_price_default)),
    step=500,
)

min_ram = st.sidebar.number_input("Min RAM (GB)", min_value=0, value=16, step=1)
min_ssd = st.sidebar.number_input("Min SSD (GB)", min_value=0, value=256, step=64)

screen_range = None
if data_df is not None and "screen_size" in _safe_columns(data_df):
    screen_vals = pd.to_numeric(data_df["screen_size"], errors="coerce").dropna()
    if not screen_vals.empty:
        scr_min, scr_max = float(screen_vals.min()), float(screen_vals.max())
        if scr_min != scr_max:
            default_min = max(13.0, scr_min)
            default_max = min(16.0, scr_max)
            if default_min > default_max:
                default_min, default_max = scr_min, scr_max
            screen_range = st.sidebar.slider(
                "Screen size (inches)",
                min_value=float(scr_min),
                max_value=float(scr_max),
                value=(default_min, default_max),
                step=0.1,
            )

gpu_filter = "Any"
if data_df is not None and ("gpu_norm" in _safe_columns(data_df) or "gpu" in _safe_columns(data_df)):
    gpu_filter = st.sidebar.radio(
        "GPU type",
        ["Any", "Integrated only", "Dedicated only"],
        horizontal=False,
    )

st.sidebar.divider()
st.sidebar.subheader("🔎 Kullanıma özel sorular")
if st.sidebar.button("Reset follow-ups"):
    for key in FOLLOWUP_KEYS:
        if key in st.session_state:
            del st.session_state[key]
    st.sidebar.success("Follow-up answers reset.")

if selected_key == "gaming":
    if "fu_gaming_titles" not in st.session_state:
        st.session_state["fu_gaming_titles"] = []
    game_titles = list(GAMING_TITLE_SCORES.keys())
    st.sidebar.multiselect(
        "Oynamak istediğiniz oyunlar",
        options=game_titles,
        default=st.session_state.get("fu_gaming_titles", []),
        key="fu_gaming_titles",
    )
    selected_titles = st.session_state.get("fu_gaming_titles", [])
    if selected_titles:
        needed = max(GAMING_TITLE_SCORES[t] for t in selected_titles)
        threshold = max(6.0, needed)
        st.sidebar.caption(f"GPU eşiği yaklaşık: {threshold:.1f}")
    else:
        st.sidebar.caption("GPU eşiği varsayılan: 6.0")

elif selected_key == "productivity":
    prod_options = {
        "office": "Ofis işleri / doküman düzenleme / sunum",
        "data": "Veri yoğun işler (Excel, analiz, raporlama)",
        "light_dev": "Hafif yazılım geliştirme",
        "multitask": "Çoklu görev (çok pencere / çok monitör)",
    }
    if "fu_productivity_profile" not in st.session_state:
        st.session_state["fu_productivity_profile"] = "office"
    st.sidebar.selectbox(
        "Üretkenlik profili",
        options=list(prod_options.keys()),
        format_func=lambda k: prod_options.get(k, k),
        key="fu_productivity_profile",
    )

elif selected_key == "design":
    design_options = {
        "graphic": "Grafik tasarım / fotoğraf (Photoshop, Illustrator, Figma)",
        "video": "Video düzenleme / motion (Premiere, After Effects, DaVinci)",
        "3d": "3D modelleme / render (Blender, Maya, 3ds Max, C4D)",
        "cad": "Mimari / teknik çizim (AutoCAD, Revit, Solidworks)",
    }
    if "fu_design_profiles" not in st.session_state:
        st.session_state["fu_design_profiles"] = ["graphic"]
    st.sidebar.multiselect(
        "Tasarım alanları",
        options=list(design_options.keys()),
        default=st.session_state.get("fu_design_profiles", []),
        format_func=lambda k: design_options.get(k, k),
        key="fu_design_profiles",
    )
    st.sidebar.caption("Seçimler GPU/RAM ipuçlarını otomatik ayarlar.")

elif selected_key == "dev":
    dev_labels = {
        "web": "Web/Backend",
        "ml": "Veri/ML",
        "mobile": "Mobil (Android/iOS)",
        "gamedev": "Oyun Motoru / 3D",
        "general": "Genel CS",
    }
    dev_keys = [k for k in dev_labels.keys() if k in DEV_PRESETS]
    if not dev_keys:
        dev_keys = list(DEV_PRESETS.keys())
    if "fu_dev_mode" not in st.session_state:
        st.session_state["fu_dev_mode"] = "general" if "general" in dev_keys else dev_keys[0]
    st.sidebar.selectbox(
        "Yazılım geliştirme profili",
        options=dev_keys,
        format_func=lambda k: dev_labels.get(k, k),
        key="fu_dev_mode",
    )
    if st.session_state.get("fu_dev_mode") == "ml":
        st.sidebar.info("Not: ML için NVIDIA/CUDA uyumu genelde kritik.")
else:
    st.sidebar.info("Bu kullanım türü için ek soru yok.")

st.sidebar.divider()
st.sidebar.subheader("Output")
top_n = st.sidebar.slider("Top N", min_value=5, max_value=50, value=10, step=1)
st.sidebar.caption("Sorting: engine default (score desc, price asc)")

st.sidebar.divider()
st.sidebar.subheader("Scrape (Local only)")
st.sidebar.info("Scraping is disabled on hosted demo.")
if os.getenv("ALLOW_SCRAPE_UI") == "1":
    if st.sidebar.button("🔄 Run scrapers (local)"):
        with st.spinner("Running scrapers..."):
            result = subprocess.run(
                [sys.executable, "recommender.py", "--run-scrapers"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        logs = (result.stdout or "") + ("\n" if result.stdout and result.stderr else "") + (result.stderr or "")
        st.session_state["scrape_logs"] = logs
        st.session_state["scrape_returncode"] = result.returncode


if data_df is None and not _data_files_exist():
    st.warning(
        "No data files detected. Run scrapers locally with "
        "`python recommender.py --run-scrapers`, then click 'Load data'."
    )


left_col, right_col = st.columns([2.4, 1.2], gap="large")

with left_col:
    st.subheader("Recommendations")
    run_button = st.button("Get recommendations", type="primary")
    if run_button:
        if data_df is None:
            st.error("Load data first from the sidebar.")
        elif budget_min > budget_max:
            st.error("Budget min must be less than or equal to budget max.")
        else:
            filtered = _apply_user_filters(data_df, min_ram, min_ssd, screen_range, gpu_filter)
            if filtered.empty:
                st.warning("No rows match the current filters. Try relaxing RAM/SSD/screen/GPU filters.")
            else:
                preferences = {
                    "min_budget": float(budget_min),
                    "max_budget": float(budget_max),
                    "usage_key": selected_key,
                    "usage_label": selected_label,
                }
                if selected_key == "gaming":
                    preferences["gaming_titles"] = st.session_state.get("fu_gaming_titles", [])
                    if not preferences["gaming_titles"]:
                        preferences["min_gpu_score_required"] = 6.0
                elif selected_key == "productivity":
                    preferences["productivity_profile"] = st.session_state.get(
                        "fu_productivity_profile", "office"
                    )
                elif selected_key == "design":
                    preferences["design_profiles"] = st.session_state.get(
                        "fu_design_profiles", ["graphic"]
                    )
                elif selected_key == "dev":
                    preferences["dev_mode"] = st.session_state.get("fu_dev_mode", "general")
                if screen_range is not None:
                    preferences["screen_max"] = float(screen_range[1])
                try:
                    preferences = normalize_and_complete_preferences(preferences)
                except Exception:
                    pass
                results = get_recommendations(filtered, preferences, top_n=int(top_n))
                st.session_state["results"] = results
                if results.empty:
                    st.warning("No recommendations found. Try widening the budget or relaxing filters.")

    results_df = st.session_state.get("results")
    if isinstance(results_df, pd.DataFrame) and not results_df.empty:
        search_term = st.text_input("Search results (name contains)", value="")
        display_df = results_df.copy()
        if search_term:
            name_series = display_df["name"].fillna("").astype(str)
            display_df = display_df[name_series.str.contains(search_term, case=False, na=False)]

        if display_df.empty:
            st.info("No results match the search term.")
        else:
            display_cols = [
                "name",
                "price",
                "cpu",
                "gpu",
                "ram_gb",
                "ssd_gb",
                "screen_size",
                "score",
            ]
            display_cols = [c for c in display_cols if c in display_df.columns]
            st.dataframe(display_df[display_cols], use_container_width=True)

            csv_bytes = display_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download results as CSV",
                data=csv_bytes,
                file_name="laprop_recommendations.csv",
                mime="text/csv",
            )
    elif isinstance(results_df, pd.DataFrame) and results_df.empty:
        st.info("No recommendations yet or the last query returned empty results.")


with right_col:
    st.subheader("Details")
    results_df = st.session_state.get("results")
    if not isinstance(results_df, pd.DataFrame) or results_df.empty:
        st.info("Select filters and run recommendations to view details.")
    else:
        options_df = results_df.reset_index(drop=False).rename(columns={"index": "row_id"})
        label_map = {
            row["row_id"]: f"{row['name']} - {int(row['price'])} TL"
            if "price" in row and pd.notna(row["price"])
            else str(row["name"])
            for _, row in options_df.iterrows()
        }
        selected_row_id = st.selectbox(
            "Select a recommendation",
            options=options_df["row_id"].tolist(),
            format_func=lambda v: label_map.get(v, str(v)),
        )
        selected_row = options_df[options_df["row_id"] == selected_row_id].iloc[0]

        st.markdown(f"**{selected_row.get('name', 'Unknown')}**")
        if "price" in selected_row:
            st.metric("Price", f"{int(selected_row['price']):,} TL" if pd.notna(selected_row["price"]) else "-")
        if "score" in selected_row:
            st.metric("Score", f"{selected_row['score']:.1f}")

        if selected_row.get("score_breakdown"):
            st.caption(f"Score breakdown: {selected_row['score_breakdown']}")
        if selected_row.get("parse_warnings"):
            st.warning(str(selected_row["parse_warnings"]))

        with st.expander("Show full record"):
            st.json({k: v for k, v in selected_row.items() if pd.notna(v)})

        with st.expander("Debug info"):
            attrs = results_df.attrs or {}
            if attrs:
                st.write(attrs)
            else:
                st.write("No extra metadata available.")


if st.session_state.get("scrape_logs"):
    with st.expander("Scraper logs"):
        st.code(st.session_state["scrape_logs"] or "(no output)")
        if st.session_state.get("scrape_returncode") not in (0, None):
            st.error(f"Scrapers exited with code {st.session_state['scrape_returncode']}.")

# Local: pip install -r requirements.txt then streamlit run streamlit_app.py
# Hosted: set main file to streamlit_app.py
