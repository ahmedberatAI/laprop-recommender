from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Set

import pandas as pd

from ..config.settings import DATA_FILES, ALL_DATA_FILE
from ..utils.console import safe_print

FALLBACK_FIELDS = ("name", "price", "cpu", "gpu", "ram", "ssd", "screen_size")


def _normalize_key_value(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
    return str(value).strip().lower()


def _build_row_key(source: str, url: str, row: pd.Series) -> str:
    src = _normalize_key_value(source)
    url_norm = _normalize_key_value(url)
    if url_norm:
        return f"{src}||url||{url_norm}"

    parts = []
    for field in FALLBACK_FIELDS:
        parts.append(_normalize_key_value(row.get(field)))
    return f"{src}||fb||" + "|".join(parts)


def _iter_existing_keys(path: Path, chunksize: int = 50000) -> Set[str]:
    desired = {"source", "url", *FALLBACK_FIELDS}
    keys: Set[str] = set()

    if not path.exists():
        return keys

    try:
        for chunk in pd.read_csv(
            path,
            encoding="utf-8",
            chunksize=chunksize,
            usecols=lambda c: c in desired,
        ):
            if "source" not in chunk.columns:
                chunk["source"] = "unknown"
            if "url" not in chunk.columns:
                chunk["url"] = ""
            for field in FALLBACK_FIELDS:
                if field not in chunk.columns:
                    chunk[field] = ""
            for _, row in chunk.iterrows():
                keys.add(_build_row_key(row.get("source"), row.get("url"), row))
    except Exception:
        # If the file is unreadable for some reason, fall back to an empty set.
        return set()

    return keys


def _dedupe_dataframe(df: pd.DataFrame, existing_keys: Set[str]) -> tuple[pd.DataFrame, int]:
    if df.empty:
        return df, 0

    if "source" not in df.columns:
        df["source"] = "unknown"
    if "url" not in df.columns:
        df["url"] = ""
    for field in FALLBACK_FIELDS:
        if field not in df.columns:
            df[field] = ""

    keys = df.apply(lambda r: _build_row_key(r.get("source"), r.get("url"), r), axis=1)
    seen_new: Set[str] = set()
    keep_mask = []
    deduped = 0
    for key in keys:
        if key in existing_keys or key in seen_new:
            keep_mask.append(False)
            deduped += 1
        else:
            keep_mask.append(True)
            seen_new.add(key)
    return df.loc[keep_mask].copy(), deduped


def append_to_all_data():
    """Yeni scraping verilerini all_data.csv'ye ekler (tarih damgası ile)"""
    safe_print("\n[INFO] all_data.csv güncelleniyor...")

    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_data_list = []
    ALL_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Mevcut CSV dosyalarını oku
    for file_path in DATA_FILES:
        if file_path.exists():
            try:
                df = pd.read_csv(
                    file_path,
                    encoding="utf-8",
                    sep=None,
                    engine="python",
                    on_bad_lines="skip",
                )
                df['scraped_at'] = current_time  # Tarih damgası ekle
                df['source'] = file_path.stem.replace('_laptops', '')  # Kaynak bilgisi
                new_data_list.append(df)
                safe_print(f"  [OK] {file_path.name}: {len(df)} kayıt eklendi")
            except Exception as e:
                safe_print(f"  [WARN] {file_path.name} okunamadı: {e}")

    if not new_data_list:
        if not ALL_DATA_FILE.exists():
            empty = pd.DataFrame(columns=["source", "scraped_at"])
            empty.to_csv(ALL_DATA_FILE, index=False, encoding="utf-8-sig")
            safe_print("  [INFO] all_data.csv oluşturuldu (boş)")
        else:
            safe_print("  [INFO] Eklenecek yeni veri yok")
        return

    # Yeni verileri birleştir
    new_data = pd.concat(new_data_list, ignore_index=True)
    incoming_count = len(new_data)

    existing_keys = _iter_existing_keys(ALL_DATA_FILE)
    deduped_data, deduped_count = _dedupe_dataframe(new_data, existing_keys)
    added_count = len(deduped_data)

    safe_print(f"  [INFO] Gelen satır: {incoming_count}")
    safe_print(f"  [OK] Eklenecek satır: {added_count}")
    safe_print(f"  [ERROR] Dedupe edilen: {deduped_count}")

    if added_count == 0:
        safe_print("  [INFO] Eklenecek yeni veri yok (tümü dedupe edildi)")
        return

    # Kaydet (append)
    try:
        write_header = not ALL_DATA_FILE.exists()
        deduped_data.to_csv(
            ALL_DATA_FILE,
            index=False,
            encoding='utf-8-sig',
            mode='a' if not write_header else 'w',
            header=write_header,
        )
        total_note = "append edildi" if not write_header else "oluşturuldu"
        safe_print(f"  [OK] all_data.csv {total_note}: {added_count} satır")
    except Exception as e:
        safe_print(f"  [ERROR] all_data.csv kaydedilemedi: {e}")


def _self_test_dedupe() -> None:
    """Minimal self-test for dedupe logic using a temp file."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "all_data.csv"

        existing = pd.DataFrame(
            [
                {"source": "amazon", "url": "u1", "name": "A", "price": 100},
                {"source": "vatan", "url": "", "name": "B", "price": 200, "cpu": "i5"},
            ]
        )
        existing.to_csv(tmp_path, index=False, encoding="utf-8-sig")

        new_data = pd.DataFrame(
            [
                {"source": "amazon", "url": "u1", "name": "A", "price": 100},  # dup url
                {"source": "amazon", "url": "u2", "name": "C", "price": 300},  # new
                {"source": "vatan", "url": "", "name": "B", "price": 200, "cpu": "i5"},  # dup fallback
                {"source": "vatan", "url": "", "name": "B", "price": 200, "cpu": "i5"},  # dup within new
                {"source": "vatan", "url": "", "name": "B", "price": 210, "cpu": "i5"},  # new fallback
            ]
        )

        existing_keys = _iter_existing_keys(tmp_path)
        filtered, deduped = _dedupe_dataframe(new_data, existing_keys)
        safe_print("[self-test] incoming:", len(new_data))
        safe_print("[self-test] added:", len(filtered))
        safe_print("[self-test] deduped:", deduped)
