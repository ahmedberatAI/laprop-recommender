import pickle
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from ..config.settings import DATA_FILES, CACHE_FILE
from ..utils.console import safe_print

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

def load_data(use_cache=True):
    """CSV dosyalarını yükle ve birleştir"""

    expected_files = [p.name for p in DATA_FILES]
    vatan_stats = None

    if use_cache and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'rb') as f:
                df = pickle.load(f)
                if getattr(df, "attrs", {}).get("data_files") == expected_files:
                    df = _standardize_columns(df)
                    vatan_stats = getattr(df, "attrs", {}).get("vatan_stats")
                    if vatan_stats is None and 'url' in df.columns:
                        urls = df['url'].fillna("").astype(str).str.lower()
                        vatan_mask = urls.str.contains("vatanbilgisayar.com", na=False)
                        vatan_total = int(vatan_mask.sum())
                        vatan_filled = _count_filled_urls(df.loc[vatan_mask, 'url'])
                        vatan_stats = (vatan_total, vatan_filled)
                    if vatan_stats is not None:
                        v_total, v_filled = vatan_stats
                        safe_print(f"Vatan load: rows {v_total}, url filled {v_filled}/{v_total}")
                    safe_print(f"[OK] Önbellekten {len(df)} laptop yüklendi")
                    return df
        except:
            pass

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
                            safe_print(
                                f"[WARN] {file_path.name}: beklenen kolonlar bulunamadı (name/price). "
                                f"Kolonlar: {list(df.columns)[:6]}..."
                            )
                            continue
                if file_path.name == "vatan_laptops.csv":
                    v_total = len(df)
                    v_filled = _count_filled_urls(df['url']) if 'url' in df.columns else 0
                    vatan_stats = (v_total, v_filled)
                    safe_print(f"Vatan load: rows {v_total}, url filled {v_filled}/{v_total}")
                all_data.append(df)
                safe_print(f"[OK] {file_path.name}: {len(df)} ürün yüklendi")
            except Exception as e:
                safe_print(f"[WARN] {file_path.name} okunamadı: {e}")

    if not all_data:
        safe_print("\n[ERROR] Hiç veri dosyası bulunamadı!")
        safe_print("Önce scraper'ları çalıştırın: --run-scrapers")
        return None

    df = pd.concat(all_data, ignore_index=True)
    if vatan_stats is None and 'url' in df.columns:
        urls = df['url'].fillna("").astype(str).str.lower()
        vatan_mask = urls.str.contains("vatanbilgisayar.com", na=False)
        v_total = int(vatan_mask.sum())
        v_filled = _count_filled_urls(df.loc[vatan_mask, 'url'])
        vatan_stats = (v_total, v_filled)
        safe_print(f"Vatan load: rows {v_total}, url filled {v_filled}/{v_total}")

    try:
        if hasattr(df, "attrs"):
            df.attrs['data_files'] = expected_files
            if vatan_stats is not None:
                df.attrs['vatan_stats'] = vatan_stats
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump(df, f)
    except:
        pass

    return df
