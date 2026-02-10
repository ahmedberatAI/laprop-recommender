"""CLI entry point — main loop and simulation runner.

Submodules:
  - nlp: NLP text parsing, intent detection, preference normalization
  - preferences: Interactive user preference prompts
  - display: Result display, data inspection, export
"""

import json
from datetime import datetime
from typing import List, Dict, Any

from ..ingestion.orchestrator import run_scrapers
from ..processing.read import load_data, _get_domain_counts
from ..processing.clean import clean_data
from ..recommend.engine import get_recommendations
from ..recommend.scenarios import SCENARIOS
from ..utils.console import safe_print
from ..utils.logging import get_logger

# --- Public sub-module imports (used by main loop) ---
from .nlp import (  # noqa: F401
    _safe_float,
    detect_budget,
    detect_usage_intent,
    detect_dev_mode,
    fuzzy_match_game_titles,
    parse_design_profile_from_text,
    parse_free_text_to_preferences,
    normalize_and_complete_preferences,
)
from .preferences import (  # noqa: F401
    _prompt_design_details,
    _prompt_productivity_details,
    _prompt_gaming_titles,
    ask_missing_preferences,
    get_user_preferences_free_text,
    get_user_preferences,
)
from .display import (  # noqa: F401
    _row_to_result_dict,
    display_recommendations,
    inspect_data,
    save_data,
    inspect_scrapers_separately,
)

logger = get_logger(__name__)


def run_simulation(
    n: int = 100,
    seed: int = 42,
    out_path: str = "simulation_outputs.jsonl",
    df=None,
    top_n: int = 5,
):
    """
    Deterministic simulation: run the static scenario list in order.
    seed parameter is kept for backward compatibility.
    """
    if df is None:
        raise ValueError("run_simulation: df param is required (cleaned DataFrame expected).")

    scenarios = SCENARIOS[: max(0, int(n))]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ok_cnt = 0
    vatan_rec_total = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for sc in scenarios:
            sid = sc.get("scenario_id")
            label = sc.get("scenario_label", "")
            prefs = dict(sc.get("prefs", {}))

            try:
                prefs = normalize_and_complete_preferences(prefs)
            except Exception:
                pass

            prefs.setdefault("show_breakdown", False)

            try:
                recs = get_recommendations(df, prefs, top_n=top_n)
            except Exception as e:
                out = {
                    "scenario_id": sid,
                    "scenario_label": label,
                    "prefs": prefs,
                    "meta": {"error": str(e)},
                    "results": [],
                    "timestamp": ts,
                }
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
                continue

            results: List[Dict[str, Any]] = []
            meta: Dict[str, Any] = {}

            if recs is not None and hasattr(recs, "empty") and not recs.empty:
                ok_cnt += 1
                if 'url' in recs.columns:
                    vatan_rec_total += _get_domain_counts(recs['url']).get('vatan', 0)
                try:
                    meta["usage_label"] = recs.attrs.get("usage_label", "")
                    meta["avg_score"] = float(recs.attrs.get("avg_score", 0) or 0)
                    pr = recs.attrs.get("price_range", (None, None))
                    meta["price_min"] = _safe_float(pr[0])
                    meta["price_max"] = _safe_float(pr[1])
                except Exception:
                    meta["usage_label"] = ""
                    meta["avg_score"] = 0.0

                for _, row in recs.iterrows():
                    results.append(_row_to_result_dict(row.to_dict()))
            else:
                meta["usage_label"] = prefs.get("usage_label", "")
                meta["avg_score"] = 0.0
                meta["price_min"] = None
                meta["price_max"] = None

            out = {
                "scenario_id": sid,
                "scenario_label": label,
                "prefs": prefs,
                "meta": meta,
                "results": results,
                "timestamp": ts,
            }
            f.write(json.dumps(out, ensure_ascii=False) + "\n")

    total = len(scenarios)
    safe_print(f"Simülasyon bitti: {total} senaryo | sonuç bulunan: {ok_cnt}/{total}")
    safe_print(f"Çıktı: {out_path}")
    safe_print(f"Simulation vatan recs: {vatan_rec_total}")
    if vatan_rec_total == 0:
        safe_print("Warning: vatan domain recommendations count is 0")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Geliştirilmiş Laptop Öneri Sistemi')
    parser.add_argument('--run-scrapers', action='store_true', help='Scraper\'ları çalıştır')
    parser.add_argument('--debug', action='store_true', help='Debug modu (detaylı skorlar)')
    parser.add_argument('--nl', '--free-text', dest='free_text', action='store_true',
                        help='Serbest metin (akıllı) modu varsayılan olsun')
    args = parser.parse_args()

    safe_print("=" * 60)
    safe_print("🚀 GELİŞTİRİLMİŞ LAPTOP ÖNERİ SİSTEMİ v2.0")
    safe_print("=" * 60)

    global preferences
    preferences = {'show_breakdown': args.debug}
    prefer_free_text = args.free_text

    if args.run_scrapers:
        run_scrapers()

    df = load_data()
    if df is None:
        return

    df = clean_data(df)

    while True:
        safe_print("\n" + "=" * 60)
        safe_print("ANA MENÜ")
        safe_print("=" * 60)
        safe_print("1. 🎯 Laptop önerisi al (klasik soru-cevap)")
        safe_print("2. 🤖 Laptop önerisi al (serbest metin / akıllı)")
        safe_print("3. 📊 Veri durumunu incele")
        safe_print("4. 📋 Scraper verilerini ayrı ayrı incele")
        safe_print("5. 💾 Veriyi CSV olarak kaydet")
        safe_print("6. 🔄 Veriyi güncelle (Scraper çalıştır)")
        safe_print("7. 🔍 Debug modunu aç/kapa")
        safe_print("8. 🧪 Simülasyonu aktifleştir (100 senaryo)")
        safe_print("9. ❌ Çıkış")

        if prefer_free_text:
            safe_print("Not: --nl aktif, serbest metin modu varsayılan.")

        choice = input("\nSeçiminiz (1-9): ").strip()
        if not choice and prefer_free_text:
            choice = '2'

        if choice == '1':
            user_prefs = get_user_preferences()
            user_prefs['show_breakdown'] = preferences.get('show_breakdown', False)
            recommendations = get_recommendations(df, user_prefs)
            display_recommendations(recommendations, user_prefs)
            input("\n\nDevam etmek için Enter'a basın...")

        elif choice == '2':
            user_prefs = get_user_preferences_free_text()
            user_prefs['show_breakdown'] = preferences.get('show_breakdown', False)
            recommendations = get_recommendations(df, user_prefs)
            display_recommendations(recommendations, user_prefs)
            input("\n\nDevam etmek için Enter'a basın...")

        elif choice == '3':
            inspect_data(df)
            input("\nDevam etmek için Enter'a basın...")

        elif choice == '4':
            inspect_scrapers_separately()
            input("\nDevam etmek için Enter'a basın...")

        elif choice == '5':
            save_data(df)
            input("\nDevam etmek için Enter'a basın...")

        elif choice == '6':
            run_scrapers()
            df = load_data(use_cache=False)
            if df is not None:
                df = clean_data(df)
                safe_print("✅ Veriler güncellendi!")

        elif choice == '7':
            preferences['show_breakdown'] = not preferences.get('show_breakdown', False)
            status = "açık" if preferences['show_breakdown'] else "kapalı"
            safe_print(f"\n🔍 Debug modu {status}")
            input("\nDevam etmek için Enter'a basın...")

        elif choice == '8':
            run_simulation(n=100, seed=42, out_path="simulation_outputs.jsonl", df=df)
            input("\nDevam etmek icin Enter'a basin...")

        elif choice == '9':
            safe_print("\n👋 İyi günler!")
            break

        else:
            safe_print("\n⚠️ Geçersiz seçim!")
