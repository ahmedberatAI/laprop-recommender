import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from ..config.settings import DATA_FILES, CACHE_FILE
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Metadata sidecar lives next to the parquet cache
_CACHE_META = CACHE_FILE.with_suffix(".meta.json")


def _sanitize_column_name(name: Any) -> str:
    return str(name).replace("\ufeff", "").strip().lower()

def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    url_col = None
    bom_url_col = None
    for col in df.columns:
        col_str = str(col)
        cleaned = _sanitize_column_name(col)
        if cleaned == "url":
            if "\ufeff" in col_str:
                bom_url_col = col
            else:
                url_col = col

    if (
        url_col is not None
        and bom_url_col is not None
        and url_col in df.columns
        and bom_url_col in df.columns
    ):
        df[url_col] = df[url_col].fillna(df[bom_url_col])
        df = df.drop(columns=[bom_url_col])

    df.columns = [_sanitize_column_name(c) for c in df.columns]
    return df

def _count_filled_urls(url_series: pd.Series) -> int:
    return url_series.fillna("").astype(str).str.strip().ne("").sum()

def _get_domain_counts(url_series: pd.Series) -> Dict[str, int]:
    urls = url_series.fillna("").astype(str).str.lower()
    return {
        "amazon": int(urls.str.contains("amazon", na=False).sum()),
        "vatan": int(urls.str.contains("vatanbilgisayar.com", na=False).sum()),
        "incehesap": int(urls.str.contains("incehesap", na=False).sum()),
    }

def read_csv_robust(path: Path) -> pd.DataFrame:
    """Read CSV with encoding fallbacks and auto delimiter detection."""
    encodings: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp1254", "latin1")
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            df = pd.read_csv(
                path,
                encoding=encoding,
                sep=None,
                engine="python",
                on_bad_lines="skip",
            )
            return _standardize_columns(df)
        except Exception as e:
            last_error = e
    assert last_error is not None
    raise last_error


def _save_cache(df: pd.DataFrame, expected_files: list, vatan_stats) -> None:
    """Save DataFrame to parquet with a JSON metadata sidecar."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Coerce object columns to string to avoid mixed-type parquet errors
        df_out = df.copy()
        for col in df_out.columns:
            if df_out[col].dtype == object:
                df_out[col] = df_out[col].astype(str).replace("nan", pd.NA).replace("None", pd.NA)
        df_out.to_parquet(CACHE_FILE, index=False, engine="pyarrow")
        meta = {"data_files": expected_files}
        if vatan_stats is not None:
            meta["vatan_stats"] = [int(v) for v in vatan_stats]
        _CACHE_META.write_text(json.dumps(meta, ensure_ascii=False, default=str), encoding="utf-8")
    except Exception as exc:
        logger.warning("Cache yazılamadı: %s", exc)


def _load_cache(expected_files: list):
    """Try to load cached parquet + metadata.  Return (df, vatan_stats) or None."""
    if not CACHE_FILE.exists():
        return None

    # --- backward compat: delete legacy pickle files ---
    if CACHE_FILE.suffix == ".pkl":
        _migrate_legacy_pickle(expected_files)
        if not CACHE_FILE.exists():
            return None

    try:
        meta = {}
        if _CACHE_META.exists():
            meta = json.loads(_CACHE_META.read_text(encoding="utf-8"))
        if meta.get("data_files") != expected_files:
            logger.info("Cache metadata uyuşmuyor, yeniden yükleniyor.")
            return None
        df = pd.read_parquet(CACHE_FILE, engine="pyarrow")
        df = _standardize_columns(df)
        vatan_stats = meta.get("vatan_stats")
        if vatan_stats is not None:
            vatan_stats = tuple(vatan_stats)
        return df, vatan_stats
    except Exception as exc:
        logger.warning("Cache okunamadı: %s", exc)
        return None


def _migrate_legacy_pickle(expected_files: list) -> None:
    """One-shot migration: convert old .pkl cache to parquet, then delete .pkl."""
    pkl_path = CACHE_FILE  # still .pkl at this point
    if not pkl_path.exists() or pkl_path.suffix != ".pkl":
        return
    try:
        import pickle as _pickle  # only imported during migration

        with open(pkl_path, "rb") as f:
            df = _pickle.load(f)
        attrs = getattr(df, "attrs", {})
        if attrs.get("data_files") == expected_files:
            _save_cache(df, expected_files, attrs.get("vatan_stats"))
            logger.info("Eski pickle cache parquet'e migrate edildi.")
        pkl_path.unlink(missing_ok=True)
        logger.info("Eski pickle dosyası silindi: %s", pkl_path)
    except Exception as exc:
        logger.warning("Pickle migration başarısız: %s", exc)
        # Remove the dangerous pickle regardless
        try:
            pkl_path.unlink(missing_ok=True)
        except OSError:
            pass


def load_data(use_cache=True):
    """CSV dosyalarını yükle ve birleştir"""

    expected_files = [p.name for p in DATA_FILES]
    vatan_stats = None

    if use_cache:
        cached = _load_cache(expected_files)
        if cached is not None:
            df, vatan_stats = cached
            if vatan_stats is not None and 'url' in df.columns:
                v_total, v_filled = vatan_stats
                logger.info("Vatan load: rows %d, url filled %d/%d", v_total, v_filled, v_total)
            elif vatan_stats is None and 'url' in df.columns:
                urls = df['url'].fillna("").astype(str).str.lower()
                vatan_mask = urls.str.contains("vatanbilgisayar.com", na=False)
                vatan_total = int(vatan_mask.sum())
                vatan_filled = _count_filled_urls(df.loc[vatan_mask, 'url'])
                vatan_stats = (vatan_total, vatan_filled)
                logger.info("Vatan load: rows %d, url filled %d/%d", vatan_total, vatan_filled, vatan_total)
            logger.info("[OK] Önbellekten %d laptop yüklendi", len(df))
            return df

    all_data = []

    for file_path in DATA_FILES:
        if file_path.exists():
            try:
                df = read_csv_robust(file_path)

                columns_lower = [str(c).lower().strip() for c in df.columns]
                has_name = 'name' in columns_lower
                has_price = 'price' in columns_lower
                if not (has_name and has_price) and len(df.columns) == 1:
                    header = str(df.columns[0])
                    if ';' in header or ',' in header:
                        df_retry: pd.DataFrame | None = None
                        for encoding in ("utf-8-sig", "utf-8", "cp1254", "latin1"):
                            try:
                                df_retry = pd.read_csv(
                                    file_path,
                                    encoding=encoding,
                                    sep=';',
                                    engine="python",
                                    on_bad_lines="skip",
                                )
                                break
                            except Exception:
                                continue
                        if df_retry is not None:
                            df = _standardize_columns(df_retry)
                        columns_lower = [str(c).lower().strip() for c in df.columns]
                        has_name = 'name' in columns_lower
                        has_price = 'price' in columns_lower
                        if not (has_name and has_price):
                            logger.warning(
                                "%s: beklenen kolonlar bulunamadı (name/price). Kolonlar: %s...",
                                file_path.name,
                                list(df.columns)[:6],
                            )
                            continue
                if file_path.name == "vatan_laptops.csv":
                    v_total = len(df)
                    v_filled = _count_filled_urls(df['url']) if 'url' in df.columns else 0
                    vatan_stats = (v_total, v_filled)
                    logger.info("Vatan load: rows %d, url filled %d/%d", v_total, v_filled, v_total)
                all_data.append(df)
                logger.info("[OK] %s: %d ürün yüklendi", file_path.name, len(df))
            except Exception as e:
                logger.warning("%s okunamadı: %s", file_path.name, e)

    if not all_data:
        logger.error("Hiç veri dosyası bulunamadı! Önce scraper'ları çalıştırın: --run-scrapers")
        return None

    df = pd.concat(all_data, ignore_index=True)
    if vatan_stats is None and 'url' in df.columns:
        urls = df['url'].fillna("").astype(str).str.lower()
        vatan_mask = urls.str.contains("vatanbilgisayar.com", na=False)
        v_total = int(vatan_mask.sum())
        v_filled = _count_filled_urls(df.loc[vatan_mask, 'url'])
        vatan_stats = (v_total, v_filled)
        logger.info("Vatan load: rows %d, url filled %d/%d", v_total, v_filled, v_total)

    _save_cache(df, expected_files, vatan_stats)

    return df
