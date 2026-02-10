"""Display, inspection, and data export functions for CLI output."""

from typing import Dict, Any

import pandas as pd

from ..config.settings import BASE_DIR
from ..processing.normalize import normalize_gpu_model
from ..processing.clean import (
    clean_data,
    clean_price,
    clean_ram_value,
    clean_ssd_value,
)
from ..recommend.engine import (
    filter_by_usage,
    calculate_score,
)
from ..utils.console import safe_print
from .nlp import _safe_float


def _row_to_result_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "name": row.get("name"),
        "price": _safe_float(row.get("price")),
        "score": _safe_float(row.get("score")),
        "brand": row.get("brand"),
        "cpu": row.get("cpu"),
        "gpu": row.get("gpu"),
        "ram_gb": _safe_float(row.get("ram_gb")),
        "ssd_gb": _safe_float(row.get("ssd_gb")),
        "screen_size": _safe_float(row.get("screen_size")),
        "os": row.get("os"),
        "url": row.get("url"),
    }

    warnings = row.get("parse_warnings")
    if isinstance(warnings, list) and warnings:
        out["parse_warnings"] = warnings

    return out


def display_recommendations(recommendations, preferences):
    """Önerileri göster - preferences parametresi eklendi"""
    if recommendations.empty:
        return

    usage_lbl = recommendations.attrs.get('usage_label', '')
    avg_score = recommendations.attrs.get('avg_score', 0)
    price_range = recommendations.attrs.get('price_range', (0, 0))

    safe_print("\n" + "=" * 60)
    title = "🏆 ÖNERİLER"
    if usage_lbl:
        title += f" – {usage_lbl}"
    safe_print(title.center(60))
    safe_print("=" * 60)

    safe_print(f"\n📊 Ortalama Skor: {avg_score:.1f}/100")
    safe_print(f"💰 Fiyat Aralığı: {price_range[0]:,.0f} - {price_range[1]:,.0f} TL")
    safe_print("-" * 60)

    for i, (_, lap) in enumerate(recommendations.iterrows(), 1):
        safe_print(f"\n{i}. {lap.get('name', '(isimsiz)')}")
        safe_print("-" * 60)

        safe_print(f"💰 Fiyat: {lap['price']:,.0f} TL")
        safe_print(f"⭐ Puan: {lap['score']:.1f}/100")

        if preferences.get('show_breakdown', False):
            safe_print(f"   📈 Detay: {lap.get('score_breakdown', '')}")

        safe_print(f"🏷️ Marka: {str(lap.get('brand', '')).title()}")
        safe_print(f"💻 CPU: {lap.get('cpu', 'Belirtilmemiş')} (Skor: {lap.get('cpu_score', 0):.1f})")
        safe_print(f"🎮 GPU: {lap.get('gpu', 'Belirtilmemiş')} (Skor: {lap.get('gpu_score', 0):.1f})")
        safe_print(f"💾 RAM: {lap.get('ram_gb', 0):.0f} GB")
        safe_print(f"💿 SSD: {lap.get('ssd_gb', 0):.0f} GB")
        safe_print(f"📺 Ekran: {lap.get('screen_size', 0):.1f}\"")
        safe_print(f"🖥️ OS: {lap.get('os', 'FreeDOS')}")

        if 'url' in lap and pd.notna(lap['url']):
            safe_print(f"🔗 Link: {lap['url']}")


def inspect_data(df):
    """Veri inceleme ve debug - Geliştirilmiş (GPU model sayımları eklendi)"""
    safe_print("\n📊 VERİ İNCELEME")
    safe_print("-" * 60)
    safe_print(f"Toplam kayıt: {len(df)}")
    safe_print(f"Kolonlar: {', '.join(df.columns)}")

    safe_print("\n🏷️ Marka Dağılımı:")
    brand_counts = df['brand'].value_counts()
    for brand, count in brand_counts.head(10).items():
        safe_print(f"  {brand.title()}: {count} laptop")

    if 'price' in df.columns:
        safe_print(f"\n💰 Fiyat Dağılımı:")
        safe_print(f"  Min: {df['price'].min():,.0f} TL")
        safe_print(f"  Max: {df['price'].max():,.0f} TL")
        safe_print(f"  Ortalama: {df['price'].mean():,.0f} TL")
        safe_print(f"  Medyan: {df['price'].median():,.0f} TL")

        safe_print(f"\n💵 Fiyat Aralıkları:")
        price_ranges = [
            (0, 20000, "0-20K"),
            (20000, 30000, "20K-30K"),
            (30000, 40000, "30K-40K"),
            (40000, 50000, "40K-50K"),
            (50000, 70000, "50K-70K"),
            (70000, 100000, "70K-100K"),
            (100000, 1000000, "100K+")
        ]
        for min_p, max_p, label in price_ranges:
            count = len(df[(df['price'] >= min_p) & (df['price'] < max_p)])
            if count > 0:
                pct = (count / len(df)) * 100
                safe_print(f"  {label}: {count} laptop ({pct:.1f}%)")

    if 'ram_gb' in df.columns:
        safe_print(f"\n💾 RAM Dağılımı:")
        ram_counts = df['ram_gb'].value_counts().sort_index()
        for ram, count in ram_counts.items():
            safe_print(f"  {ram:.0f} GB: {count} laptop")

    if 'gpu' in df.columns:
        safe_print("\n🧮 GPU Model Sayımları (detaylı):")
        gpu_norm = df['gpu'].apply(normalize_gpu_model)
        counts = gpu_norm.value_counts()

        total = counts.sum()
        integ = counts[counts.index.str.contains(r'iGPU|Integrated', case=False, regex=True)].sum()
        disc = total - integ
        safe_print(f"  Toplam: {total} | Integrated: {integ} | Discrete: {disc}")

        for model, c in counts.items():
            safe_print(f"  - {model}: {c}")

    safe_print(f"\n📝 Örnek Kayıtlar (ilk 3):")
    cols_to_show = ['name', 'price', 'brand', 'cpu_score', 'gpu_score', 'ram_gb', 'ssd_gb']
    available_cols = [c for c in cols_to_show if c in df.columns]
    sample_df = df[available_cols].head(3)
    for i, row in sample_df.iterrows():
        safe_print(f"\n  Laptop {i + 1}:")
        for col in available_cols:
            val = row[col]
            if col == 'price':
                safe_print(f"    {col}: {val:,.0f} TL")
            elif col == 'name':
                safe_print(f"    {col}: {str(val)[:50]}...")
            else:
                safe_print(f"    {col}: {val}")

    if 'gpu' in df.columns:
        safe_print("\n🧮 GPU Model Sayımları (normalize edilmiş):")
        gpu_norm = df['gpu'].apply(normalize_gpu_model)
        counts = gpu_norm.value_counts()

        total = counts.sum()
        integ = counts[counts.index.str.contains(r'\(iGPU\)|Integrated', case=False, regex=True)].sum()
        disc = total - integ
        safe_print(f"  Toplam: {total} | Integrated: {integ} | Discrete: {disc}")

        for model, c in counts.items():
            safe_print(f"  - {model}: {c}")
    else:
        safe_print("\nℹ️ 'gpu' kolonu bulunamadı; GPU model sayımı atlandı.")


def save_data(df, filename='laptop_data_export.csv'):
    """Veriyi CSV olarak kaydet"""
    try:
        filepath = BASE_DIR / filename
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        safe_print(f"\n✅ Veri kaydedildi: {filepath}")
        safe_print(f"   {len(df)} kayıt")
    except Exception as e:
        safe_print(f"\n❌ Kayıt hatası: {e}")


def inspect_scrapers_separately():
    """Her scraper'ın verilerini ayrı ayrı analiz eder"""
    safe_print("\n" + "=" * 60)
    safe_print("SCRAPER VERİLERİ DETAYLI ANALİZ")
    safe_print("=" * 60)

    scraper_files = {
        "Amazon": BASE_DIR / "amazon_laptops.csv",
    }

    for name, filepath in scraper_files.items():
        safe_print(f"\n{'─' * 60}")
        safe_print(f"📊 {name.upper()}")
        safe_print(f"{'─' * 60}")

        if not filepath.exists():
            safe_print(f"❌ Dosya bulunamadı: {filepath}")
            continue

        try:
            df = pd.read_csv(filepath, encoding='utf-8')

            safe_print(f"\n✓ Toplam kayıt: {len(df)}")
            safe_print(f"✓ Kolonlar: {', '.join(df.columns)}")

            if 'price' in df.columns:
                df['price_clean'] = df['price'].apply(clean_price)
                valid_prices = df['price_clean'].dropna()

                if len(valid_prices) > 0:
                    safe_print(f"\n💰 Fiyat İstatistikleri:")
                    safe_print(f"  • Geçerli fiyat: {len(valid_prices)}/{len(df)}")
                    safe_print(f"  • Min: {valid_prices.min():,.0f} TL")
                    safe_print(f"  • Max: {valid_prices.max():,.0f} TL")
                    safe_print(f"  • Ortalama: {valid_prices.mean():,.0f} TL")
                    safe_print(f"  • Medyan: {valid_prices.median():,.0f} TL")
                else:
                    safe_print(f"\n⚠️ Geçerli fiyat bulunamadı!")

            if 'ram' in df.columns:
                df['ram_clean'] = df['ram'].apply(clean_ram_value)
                safe_print(f"\n💾 RAM Dağılımı:")
                ram_counts = df['ram_clean'].value_counts().sort_index()
                for ram, count in ram_counts.items():
                    safe_print(f"  • {ram} GB: {count} laptop")

            if 'gpu' in df.columns:
                safe_print(f"\n🎮 GPU Dağılımı:")
                gpu_counts = df['gpu'].value_counts().head(10)
                for gpu, count in gpu_counts.items():
                    safe_print(f"  • {str(gpu)[:40]}: {count}")

            if 'cpu' in df.columns:
                safe_print(f"\n🔧 CPU Dağılımı (İlk 10):")
                cpu_counts = df['cpu'].value_counts().head(10)
                for cpu, count in cpu_counts.items():
                    safe_print(f"  • {str(cpu)[:40]}: {count}")

            score_scenarios = [
                {
                    'label': '30K-60K / Üretkenlik / Ofis',
                    'prefs': {
                        'min_budget': 30000, 'max_budget': 60000,
                        'usage_key': 'productivity', 'productivity_profile': 'office',
                    },
                },
                {
                    'label': '25K-45K / Taşınabilirlik',
                    'prefs': {
                        'min_budget': 25000, 'max_budget': 45000,
                        'usage_key': 'portability',
                    },
                },
                {
                    'label': '40K-80K / Oyun (Orta Seviye)',
                    'prefs': {
                        'min_budget': 40000, 'max_budget': 80000,
                        'usage_key': 'gaming', 'min_gpu_score_required': 6.0,
                    },
                },
                {
                    'label': '45K-90K / Tasarım (Video)',
                    'prefs': {
                        'min_budget': 45000, 'max_budget': 90000,
                        'usage_key': 'design', 'design_profiles': ['video'],
                        'design_gpu_hint': 'mid', 'design_min_ram_hint': 32,
                    },
                },
                {
                    'label': '35K-75K / Yazılım (Web/Backend)',
                    'prefs': {
                        'min_budget': 35000, 'max_budget': 75000,
                        'usage_key': 'dev', 'dev_mode': 'web',
                    },
                },
            ]
            try:
                df_score = clean_data(df.copy())
                for scenario in score_scenarios:
                    label = scenario['label']
                    score_prefs = scenario['prefs']
                    budget_filtered = df_score[
                        (df_score['price'] >= score_prefs['min_budget']) &
                        (df_score['price'] <= score_prefs['max_budget'])
                    ].copy()

                    if budget_filtered.empty:
                        safe_print(f"\n⭐ Ortalama Puan ({label}): bulunamadı")
                        continue

                    filtered = filter_by_usage(budget_filtered, score_prefs['usage_key'], score_prefs)
                    if 'url' in filtered.columns:
                        filtered = filtered.drop_duplicates(subset=['url'], keep='first')
                    filtered = filtered.drop_duplicates(subset=['name', 'price'], keep='first')

                    if filtered.empty:
                        safe_print(f"\n⭐ Ortalama Puan ({label}): bulunamadı")
                        continue

                    scores = []
                    for _, row in filtered.iterrows():
                        score, _ = calculate_score(row, score_prefs)
                        scores.append(score)
                    avg_score = float(sum(scores) / len(scores))
                    safe_print(f"\n⭐ Ortalama Puan ({label}): {avg_score:.1f}/100")
            except Exception as e:
                safe_print(f"\n⚠️ Ortalama puan hesaplanamadı: {e}")

            if 'os' in df.columns:
                safe_print(f"\n💻 İşletim Sistemi:")
                os_counts = df['os'].value_counts()
                for os, count in os_counts.items():
                    safe_print(f"  • {os}: {count}")

            safe_print(f"\n📝 Örnek Kayıtlar (İlk 2):")
            sample_cols = ['name', 'price', 'cpu', 'gpu', 'ram']
            available = [c for c in sample_cols if c in df.columns]
            for i, row in df[available].head(2).iterrows():
                safe_print(f"\n  [{i + 1}]")
                for col in available:
                    val = row[col]
                    if col == 'name':
                        safe_print(f"    {col}: {str(val)[:50]}...")
                    else:
                        safe_print(f"    {col}: {val}")

        except Exception as e:
            safe_print(f"❌ Okuma hatası: {e}")

    safe_print(f"\n{'=' * 60}")
