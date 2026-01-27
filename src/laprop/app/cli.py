import json
import re
import difflib
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

import numpy as np
import pandas as pd

from ..config.settings import BASE_DIR
from ..config.rules import USAGE_OPTIONS, GAMING_TITLE_SCORES
from ..ingestion.orchestrator import run_scrapers
from ..processing.read import load_data, _get_domain_counts
from ..processing.clean import (
    clean_data,
    clean_price,
    clean_ram_value,
    clean_ssd_value,
)
from ..processing.normalize import normalize_gpu_model
from ..recommend.engine import (
    get_recommendations,
    filter_by_usage,
    calculate_score,
)
from ..recommend.scenarios import SCENARIOS
def _prompt_design_details() -> dict:
    """
    Kullanıcıya tasarım alan(lar)ını çoklu seçimle sorar.
    Çıktı örn:
      {
        'design_profiles': ['graphic', 'video'],
        'design_gpu_hint': 'mid',   # low | mid | high
        'design_min_ram_hint': 32
      }
    """
    print("\n🎨 Tasarım profili (birden çok seçebilirsiniz)")
    print("-" * 40)
    options = {
        1: ('graphic', "Grafik tasarım / fotoğraf (Photoshop, Illustrator, Figma)"),
        2: ('video',   "Video düzenleme / motion (Premiere, After Effects, DaVinci)"),
        3: ('3d',      "3D modelleme / render (Blender, Maya, 3ds Max, C4D)"),
        4: ('cad',     "Mimari / teknik çizim (AutoCAD, Revit, Solidworks)")
    }
    for k, (_, desc) in options.items():
        print(f"{k}. {desc}")

    print("\nBirden fazla seçim için virgül kullanın (örn: 1,3). Boş bırakılırsa 1 (Grafik) kabul edilir.")
    raw = input("Seçimleriniz: ").strip()

    chosen_keys = []
    if raw:
        for tok in raw.split(","):
            tok = tok.strip()
            if tok.isdigit():
                idx = int(tok)
                if idx in options:
                    chosen_keys.append(options[idx][0])

    if not chosen_keys:
        chosen_keys = ['graphic']  # varsayılan

    # Basit ipuçları (şimdilik skora dokunmuyoruz; ileride kullanacağız)
    # GPU ihtiyacı ipucu:
    if any(k in chosen_keys for k in ['3d']):
        gpu_hint = 'high'
    elif any(k in chosen_keys for k in ['video', 'cad']):
        gpu_hint = 'mid'
    else:
        gpu_hint = 'low'

    # RAM ipucu:
    if '3d' in chosen_keys or 'video' in chosen_keys or 'cad' in chosen_keys:
        min_ram = 32
    else:
        min_ram = 16

    return {
        'design_profiles': chosen_keys,         # ['graphic', 'video', ...]
        'design_gpu_hint': gpu_hint,            # low | mid | high
        'design_min_ram_hint': min_ram          # 16 | 32 (ileride 64 de eklenebilir)
    }

def _prompt_productivity_details() -> dict:
    print("\n📈 Üretkenlik profili")
    print("-" * 30)
    opts = {
        1: ('office', "Ofis işleri / doküman düzenleme / sunum"),
        2: ('data', "Veri yoğun işler (Excel, analiz, raporlama)"),
        3: ('light_dev', "Hafif yazılım geliştirme"),
        4: ('multitask', "Çoklu görev (çok pencere / çok monitör)")
    }
    for k, (_, desc) in opts.items():
        print(f"{k}. {desc}")

    profile = 'office'
    try:
        sel = int(input("Seçiminiz (1-4): ").strip())
        if sel in opts:
            profile = opts[sel][0]
    except:
        pass

    return {'productivity_profile': profile}

def _prompt_gaming_titles() -> list:
    """CLI: 10 oyunu numaralı listeyle gösterir, kullanıcıdan seçim alır."""
    print("\n🎮 Oyun listesi (gelecekte oynamak istediklerinizi seçin)")
    titles = list(GAMING_TITLE_SCORES.keys())
    for i, t in enumerate(titles, 1):
        print(f"{i}. {t}  (gpu_score ≥ {GAMING_TITLE_SCORES[t]:.1f})")

    print("\nBirden fazla seçim için virgül kullanın (örn: 1,3,7).")
    raw = input("Seçimleriniz: ").strip()
    chosen = []
    if raw:
        for tok in raw.split(","):
            tok = tok.strip()
            if tok.isdigit():
                idx = int(tok)
                if 1 <= idx <= len(titles):
                    chosen.append(titles[idx - 1])
    return chosen

def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, float) and np.isnan(x):
            return None
        s = str(x).strip()
        if not s or s.lower() == "nan":
            return None
        return float(s)
    except Exception:
        return None

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
    print(f"Simülasyon bitti: {total} senaryo | sonuç bulunan: {ok_cnt}/{total}")
    print(f"Çıktı: {out_path}")
    print(f"Simulation vatan recs: {vatan_rec_total}")
    if vatan_rec_total == 0:
        print("Warning: vatan domain recommendations count is 0")

def detect_budget(text: str) -> Tuple[Optional[float], Optional[float]]:
    """Serbest metinden bütçe aralığını yakalamaya çalışır."""
    if not text:
        return None, None

    t = text.lower()

    def parse_amount(raw: str, suffix: Optional[str]) -> Optional[float]:
        s = raw.strip().replace(" ", "")
        s = re.sub(r'(?<=\d)[.,](?=\d{3}\b)', '', s)
        s = s.replace(',', '.')
        try:
            val = float(s)
        except ValueError:
            return None
        if suffix in ('k', 'bin'):
            val *= 1000
        return val

    range_pattern = r'(\d[\d.,]*)\s*(k|bin)?\s*(?:-|–|to|ile|arası|arasi|~)\s*(\d[\d.,]*)\s*(k|bin)?'
    m = re.search(range_pattern, t)
    if m:
        a_raw, a_suf, b_raw, b_suf = m.group(1), m.group(2), m.group(3), m.group(4)
        if not a_suf and b_suf:
            a_suf = b_suf
        if not b_suf and a_suf:
            b_suf = a_suf
        a_val = parse_amount(a_raw, a_suf)
        b_val = parse_amount(b_raw, b_suf)
        if a_val is not None and b_val is not None:
            if a_val > b_val:
                a_val, b_val = b_val, a_val
            if b_val >= 5000 or (a_suf or b_suf):
                return a_val, b_val

    max_pattern = r'(?:max|maksimum|en fazla|en çok|üst limit|tavan|<=)\s*(\d[\d.,]*)\s*(k|bin)?'
    min_pattern = r'(?:min|minimum|en az|taban|>=)\s*(\d[\d.,]*)\s*(k|bin)?'

    max_m = re.search(max_pattern, t)
    min_m = re.search(min_pattern, t)

    min_val = None
    max_val = None
    if max_m:
        max_val = parse_amount(max_m.group(1), max_m.group(2))
        if max_val is not None and not (max_val >= 5000 or max_m.group(2)):
            max_val = None
    if min_m:
        min_val = parse_amount(min_m.group(1), min_m.group(2))
        if min_val is not None and not (min_val >= 5000 or min_m.group(2)):
            min_val = None
    if min_val is not None or max_val is not None:
        return min_val, max_val

    generic_pattern = r'(\d[\d.,]*)\s*(k|bin|tl|₺)?'
    for m in re.finditer(generic_pattern, t):
        val = parse_amount(m.group(1), m.group(2) if m.group(2) in ('k', 'bin') else None)
        if val is None:
            continue
        if m.group(2) in ('k', 'bin') or val >= 5000:
            return None, val

    return None, None

def detect_usage_intent(text: str) -> Optional[str]:
    """Anahtar kelimeler ile kullanım amacını tahmin eder."""
    if not text:
        return None
    t = text.lower()

    usage_keywords = {
        'gaming': [
            'oyun', 'gamer', 'fps', 'rpg', 'moba', 'e-spor', 'espor', 'battle',
            'cyberpunk', 'starfield', 'fortnite', 'apex', 'cod', 'call of duty',
            'valorant', 'cs2', 'pubg', 'helldivers', 'forza'
        ],
        'portability': [
            'hafif', 'ince', 'taşınabilir', 'tasinabilir', 'pil', 'batarya',
            'ultrabook', 'kompakt'
        ],
        'productivity': [
            'ofis', 'office', 'excel', 'rapor', 'sunum', 'doküman', 'belge',
            'multitask', 'çoklu görev', 'verim', 'üretken'
        ],
        'design': [
            'tasarım', 'photoshop', 'illustrator', 'figma', 'premiere',
            'after effects', 'davinci', 'blender', 'autocad', 'revit',
            'solidworks', 'render', '3d', 'motion', 'grafik', 'cad'
        ],
        'dev': [
            'yazılım', 'coding', 'programlama', 'backend', 'web', 'api',
            'django', 'flask', 'spring', 'node', 'react', 'mobil', 'android',
            'ios', 'xcode', 'swift', 'kotlin', 'ml', 'ai', 'yapay zeka',
            'pytorch', 'tensorflow', 'cuda', 'unity', 'unreal'
        ],
    }

    scores = {}
    for key, kws in usage_keywords.items():
        score = 0
        for kw in kws:
            if kw in t:
                score += 1
        if key == 'portability':
            if re.search(r'\b1[34](?:[.,]\d)?\s*(?:inç|inch|\")\b', t):
                score += 1
        scores[key] = score

    best_key = max(scores, key=scores.get)
    return best_key if scores[best_key] > 0 else None

def detect_dev_mode(text: str) -> Optional[str]:
    """Dev için alt profil tespiti yapar."""
    if not text:
        return None
    t = text.lower()

    dev_keywords = {
        'web': ['web', 'backend', 'api', 'django', 'flask', 'spring', 'node', 'react'],
        'ml': ['ml', 'ai', 'yapay zeka', 'pytorch', 'tensorflow', 'cuda', 'model training'],
        'mobile': ['android', 'ios', 'xcode', 'swift', 'kotlin', 'react native'],
        'gamedev': ['unity', 'unreal', 'oyun motoru', '3d engine'],
    }

    scores = {}
    for key, kws in dev_keywords.items():
        scores[key] = sum(1 for kw in kws if kw in t)

    best_key = max(scores, key=scores.get)
    return best_key if scores[best_key] > 0 else None

def fuzzy_match_game_titles(text: str, titles: List[str]) -> List[str]:
    """Oyun isimlerini basit fuzzy + token içi eşleşme ile yakalar."""
    if not text:
        return []

    t = text.lower()
    found = set()

    title_map = {title.lower(): title for title in titles}
    stop = {'of', 'the', 'and'}

    for title in titles:
        t_low = title.lower()
        if t_low in t:
            found.add(title)
            continue
        tokens = [tok for tok in re.findall(r'[a-z0-9]+', t_low) if tok not in stop]
        if any(len(tok) >= 4 and tok in t for tok in tokens):
            found.add(title)

    pieces = [p.strip() for p in re.split(r'[,+;/\n]| ve | and ', t) if p.strip()]
    for piece in pieces:
        matches = difflib.get_close_matches(piece, title_map.keys(), n=2, cutoff=0.75)
        for m in matches:
            found.add(title_map[m])

    return [t for t in titles if t in found]

def parse_design_profile_from_text(text: str) -> dict:
    """Tasarım alt profillerini ve ipuçlarını çıkarır."""
    if not text:
        return {}

    t = text.lower()
    profiles = []

    graphic_kw = ['photoshop', 'illustrator', 'figma', 'grafik', 'graphic']
    video_kw = ['premiere', 'after effects', 'davinci', 'motion', 'video']
    d3_kw = ['blender', 'maya', '3ds max', 'c4d', 'render', '3d']
    cad_kw = ['autocad', 'revit', 'solidworks', 'cad']

    if any(kw in t for kw in graphic_kw):
        profiles.append('graphic')
    if any(kw in t for kw in video_kw):
        profiles.append('video')
    if any(kw in t for kw in d3_kw):
        profiles.append('3d')
    if any(kw in t for kw in cad_kw):
        profiles.append('cad')

    if not profiles:
        return {}

    if '3d' in profiles:
        gpu_hint = 'high'
    elif any(k in profiles for k in ['video', 'cad']):
        gpu_hint = 'mid'
    else:
        gpu_hint = 'low'

    min_ram = 32 if any(k in profiles for k in ['3d', 'video', 'cad']) else 16

    return {
        'design_profiles': sorted(set(profiles)),
        'design_gpu_hint': gpu_hint,
        'design_min_ram_hint': min_ram
    }

def parse_free_text_to_preferences(text: str) -> dict:
    """
    Serbest metinden tercihleri çıkarır.
    Hedeflenen örnekler:
    - "30-45k arası, oyun için, cyberpunk + starfield, 16gb üstü"
    - "max 50 bin, hafif olsun, pil önemli, 14 inç"
    - "40-60k, yapay zeka / pytorch, cuda şart"
    - "35k civarı, photoshop+premiere"
    """
    prefs = {}
    t = text or ""

    min_b, max_b = detect_budget(t)
    if min_b is not None:
        prefs['min_budget'] = float(min_b)
    if max_b is not None:
        prefs['max_budget'] = float(max_b)

    usage_key = detect_usage_intent(t)

    gaming_titles = fuzzy_match_game_titles(t, list(GAMING_TITLE_SCORES.keys()))
    design_info = parse_design_profile_from_text(t)
    dev_mode = detect_dev_mode(t)

    prod_profile = None
    t_low = t.lower()
    prod_keywords = {
        'multitask': ['multitask', 'çoklu görev', 'çok pencere', 'çok monitör'],
        'data': ['excel', 'analiz', 'rapor', 'data', 'tablo'],
        'light_dev': ['hafif yazılım', 'script', 'scripting'],
        'office': ['ofis', 'office', 'sunum', 'doküman', 'belge'],
    }
    prod_scores = {k: sum(1 for kw in kws if kw in t_low) for k, kws in prod_keywords.items()}
    best_prod = max(prod_scores, key=prod_scores.get)
    if prod_scores[best_prod] > 0:
        prod_profile = best_prod

    if not usage_key:
        if gaming_titles:
            usage_key = 'gaming'
        elif design_info:
            usage_key = 'design'
        elif dev_mode:
            usage_key = 'dev'
        elif prod_profile:
            usage_key = 'productivity'

    if usage_key:
        prefs['usage_key'] = usage_key

    if usage_key == 'gaming':
        prefs['gaming_titles'] = gaming_titles
    if usage_key == 'design' and design_info:
        prefs.update(design_info)
    if usage_key == 'dev':
        if dev_mode:
            prefs['dev_mode'] = dev_mode
    if usage_key == 'productivity' and prod_profile:
        prefs['productivity_profile'] = prod_profile

    return prefs

def normalize_and_complete_preferences(p: dict) -> dict:
    """Tercihleri normalize eder, eksik alanları tamamlamaya hazırlar."""
    usage_key = p.get('usage_key')
    if usage_key:
        for _, (k, label) in USAGE_OPTIONS.items():
            if k == usage_key:
                p['usage_label'] = label
                break

    if usage_key == 'gaming':
        picked = p.get('gaming_titles') or []
        if picked:
            needed = max(GAMING_TITLE_SCORES[t] for t in picked)
            p['min_gpu_score_required'] = max(6.0, needed)
    if usage_key == 'dev' and not p.get('dev_mode'):
        p['dev_mode'] = 'general'
        p['_dev_mode_auto'] = True

    if usage_key == 'design' and p.get('design_profiles'):
        if not p.get('design_gpu_hint') or not p.get('design_min_ram_hint'):
            hint = parse_design_profile_from_text(" ".join(p.get('design_profiles', [])))
            if hint:
                p.setdefault('design_gpu_hint', hint.get('design_gpu_hint'))
                p.setdefault('design_min_ram_hint', hint.get('design_min_ram_hint'))

    return p

def ask_missing_preferences(p: dict) -> dict:
    """Eksik veya çelişkili alanlar için net sorular sorar."""
    def ask_float(prompt: str) -> float:
        while True:
            try:
                val = float(input(prompt))
                if val > 0:
                    return val
            except ValueError:
                pass
            print("Lütfen geçerli bir sayı girin.")

    min_b = p.get('min_budget')
    max_b = p.get('max_budget')

    if min_b is None:
        min_b = ask_float("Minimum bütçe (TL): ")
    if max_b is None:
        max_b = ask_float("Maksimum bütçe (TL): ")

    if min_b is not None and max_b is not None and min_b > max_b:
        print("Uyarı: Minimum bütçe maksimumdan büyük, yer değiştirildi.")
        min_b, max_b = max_b, min_b

    p['min_budget'] = float(min_b)
    p['max_budget'] = float(max_b)

    if not p.get('usage_key'):
        print("\nKullanım amacını seçin:")
        for k, (_, label) in USAGE_OPTIONS.items():
            print(f"{k}. {label}")
        while True:
            sel = input("Seçiminiz (1-5): ").strip()
            if sel.isdigit() and int(sel) in USAGE_OPTIONS:
                p['usage_key'] = USAGE_OPTIONS[int(sel)][0]
                p['usage_label'] = USAGE_OPTIONS[int(sel)][1]
                break
            print("Geçersiz seçim, tekrar deneyin.")
    else:
        normalize_and_complete_preferences(p)

    usage_key = p.get('usage_key')

    if usage_key == 'gaming':
        if not p.get('gaming_titles'):
            picked = _prompt_gaming_titles()
            p['gaming_titles'] = picked
        if p.get('gaming_titles'):
            needed = max(GAMING_TITLE_SCORES[t] for t in p['gaming_titles'])
            p['min_gpu_score_required'] = max(6.0, needed)
        else:
            p['min_gpu_score_required'] = 6.0

    elif usage_key == 'design':
        if not p.get('design_profiles'):
            p.update(_prompt_design_details())
        else:
            normalize_and_complete_preferences(p)

    elif usage_key == 'productivity':
        if not p.get('productivity_profile'):
            p.update(_prompt_productivity_details())

    elif usage_key == 'dev':
        auto_dev = p.pop('_dev_mode_auto', False)
        if not p.get('dev_mode') or auto_dev:
            print("\nYazılım geliştirme profili")
            dev_opts = {
                1: ('web', 'Web/Backend'),
                2: ('ml', 'Veri/ML'),
                3: ('mobile', 'Mobil (Android/iOS)'),
                4: ('gamedev', 'Oyun Motoru / 3D'),
                5: ('general', 'Genel CS')
            }
            for i, (_, label) in dev_opts.items():
                print(f"{i}. {label}")
            while True:
                sel = input("Seçiminiz (1-5, boş=genel): ").strip()
                if not sel:
                    p['dev_mode'] = 'general'
                    break
                if sel.isdigit() and int(sel) in dev_opts:
                    p['dev_mode'] = dev_opts[int(sel)][0]
                    break
                print("Geçersiz seçim, tekrar deneyin.")

    return p

def get_user_preferences_free_text() -> dict:
    """Serbest metinle tercih toplama akışı."""
    print("\nİhtiyacını tek cümlede yaz (örn: 35-55k, oyun + okul, 15.6, RTX 4060 olsun, pil önemli)")
    raw = input("Tercihin: ").strip()

    prefs = parse_free_text_to_preferences(raw)
    prefs = normalize_and_complete_preferences(prefs)

    min_b = prefs.get('min_budget')
    max_b = prefs.get('max_budget')
    if min_b and max_b:
        budget_summary = f"{min_b:,.0f}-{max_b:,.0f} TL"
    elif max_b:
        budget_summary = f"max {max_b:,.0f} TL"
    elif min_b:
        budget_summary = f"min {min_b:,.0f} TL"
    else:
        budget_summary = "?"

    usage_label = prefs.get('usage_label') or "?"
    extra_parts = []
    if prefs.get('gaming_titles'):
        extra_parts.append(f"oyunlar={', '.join(prefs['gaming_titles'])}")
    if prefs.get('dev_mode'):
        extra_parts.append(f"dev_mode={prefs['dev_mode']}")
    if prefs.get('design_profiles'):
        extra_parts.append(f"tasarım={', '.join(prefs['design_profiles'])}")

    extra = f", {', '.join(extra_parts)}" if extra_parts else ""
    print(f"\nAnladığım: bütçe={budget_summary}, amaç={usage_label}{extra}")

    if not prefs.get('usage_key'):
        print("Amaç net değil, birkaç soru soracağım.")

    prefs = ask_missing_preferences(prefs)

    if prefs.get('usage_key') == 'dev' and prefs.get('dev_mode') == 'ml':
        print("Not: ML için NVIDIA/CUDA uyumu genelde kritik.")

    prefs['show_breakdown'] = globals().get('preferences', {}).get('show_breakdown', False)
    return prefs

def get_user_preferences():
    """Kullanıcıdan tercihlerini al"""
    print("\n" + "=" * 60)
    print("💻 LAPTOP ÖNERİ – Tercihler".center(60))
    print("=" * 60)

    preferences = {}

    # Bütçe
    print("\n💰 BÜTÇE BİLGİLERİ")
    print("-" * 30)

    while True:
        try:
            min_budget = float(input("Minimum bütçe (TL): "))
            max_budget = float(input("Maksimum bütçe (TL): "))

            if min_budget <= 0 or max_budget <= 0:
                print("⚠️ Bütçe 0'dan büyük olmalı!")
                continue
            if min_budget > max_budget:
                print("⚠️ Minimum bütçe maksimumdan büyük olamaz!")
                continue

            preferences['min_budget'] = min_budget
            preferences['max_budget'] = max_budget
            break
        except ValueError:
            print("⚠️ Lütfen geçerli bir sayı girin!")

    # Kullanım amacı
    print("\n🎯 KULLANIM AMACI")
    print("-" * 30)
    for k, (_, label) in USAGE_OPTIONS.items():
        print(f"{k}. {label}")

    while True:
        try:
            sel = int(input("Seçiminiz (1-5): ").strip())
            if sel in USAGE_OPTIONS:
                preferences['usage_key'] = USAGE_OPTIONS[sel][0]
                preferences['usage_label'] = USAGE_OPTIONS[sel][1]
                break
        except:
            pass
        print("⚠️ Geçersiz seçim, tekrar deneyin.")
    # Kullanım amacı seçildikten sonra:
    if preferences['usage_key'] == 'dev':
        print("\n🔧 Yazılım geliştirme profili")
        print("-" * 30)
        dev_opts = {
            1: ('web', '🌐 Web/Backend'),
            2: ('ml', '📊 Veri/ML'),
            3: ('mobile', '📱 Mobil (Android/iOS)'),
            4: ('gamedev', '🎮 Oyun Motoru / 3D'),
            5: ('general', '🧰 Genel CS')
        }
        for i, (_, label) in dev_opts.items():
            print(f"{i}. {label}")
        while True:
            try:
                sel = int(input("Seçiminiz (1-5): ").strip())
                if sel in dev_opts:
                    preferences['dev_mode'] = dev_opts[sel][0]
                    break
            except:
                pass
            print("⚠️ Geçersiz seçim, tekrar deneyin.")
    elif preferences.get('usage_key') == 'gaming':
        picked = _prompt_gaming_titles()
        if picked:
            preferences['gaming_titles'] = picked
            needed = max(GAMING_TITLE_SCORES[t] for t in picked)
            # Gaming genel alt eşiği olan 6.0 ile birleşik eşik:
            preferences['min_gpu_score_required'] = max(6.0, needed)
            print(f"\n🧮 Oyun eşiği ayarlandı → min gpu_score: {preferences['min_gpu_score_required']:.1f}")
        else:
            # Seçim yapmazsa varsayılan gaming filtresine (6.0) devam
            preferences['gaming_titles'] = []
            preferences['min_gpu_score_required'] = 6.0
    elif preferences.get('usage_key') == 'productivity':
        prod = _prompt_productivity_details()
        preferences.update(prod)
    elif preferences.get('usage_key') == 'design':
        des = _prompt_design_details()
        preferences.update(des)
    # ================================================================================
    # TASARIM (Design) KULLANIM AMACI – ALGORİTMA NOTLARI
    # ================================================================================
    # 1) Kullanıcıya tasarım alan(lar)ını sor:
    #    - Grafik tasarım / fotoğraf (Photoshop, Illustrator, Figma)
    #    - Video düzenleme / motion (Premiere, After Effects, DaVinci)
    #    - 3D modelleme / render (Blender, Maya, 3ds Max, C4D)
    #    - Mimari / teknik çizim (AutoCAD, Revit, Solidworks)
    #    -> Çoklu seçim yapılabilir (örn: grafik + video).
    #
    # 2) Seçimlere göre ipuçları üret:
    #    - GPU ihtiyacı:
    #        * 3D seçildiyse → high (güçlü GPU, RTX 3060+)
    #        * Video/CAD seçildiyse → mid (orta seviye GPU, RTX 3050–4060)
    #        * Grafik seçildiyse → low (iGPU da olabilir, ama renk doğruluğu önemli)
    #    - RAM ihtiyacı:
    #        * 3D / Video / CAD → en az 32 GB
    #        * Grafik → 16 GB genelde yeterli
    #
    # 3) Filtreleme aşamasında kullanılacak:
    #    - Eğer gpu_hint = high → gpu_score >= 6.5 şartı
    #    - gpu_hint = mid → gpu_score >= 4.5 şartı
    #    - gpu_hint = low → gpu_score >= 2.5 yeterli
    #    - RAM için de min_ram_hint değerini alt eşik olarak uygula
    #
    # 4) Skorlama aşamasında ek bonuslar:
    #    - Grafik seçildiyse → ekran boyutu 14–16 ve yüksek renk doğruluğu (IPS / OLED) bonus
    #    - Video seçildiyse → SSD kapasitesi ve CPU çok çekirdek puanına ekstra ağırlık
    #    - 3D seçildiyse → GPU seviyesi (RTX 4070+, VRAM 8GB+) bonus
    #    - CAD seçildiyse → CPU tek çekirdek performansı ve ekran çözünürlüğü bonus
    #
    # 5) OS tercihleri:
    #    - MacOS: Grafik/Video için küçük bir +bonus
    #    - Windows: 3D / CAD için tercih edilen ortam → küçük bir +bonus
    #
    # 6) Taşınabilirlik:
    #    - Grafik/Video yapanlar için 14–16" taşınabilir + renk doğruluğu önemli
    #    - 3D/CAD yapanlar için 15–16" ve gerekirse 17" ekran da kabul edilebilir
    #
    # 7) Özet:
    #    * Çoklu profil seçimi → ipuçları (gpu_hint, min_ram_hint)
    #    * Filtre → minimum GPU/RAM eşikleri
    #    * Skor → profil bazlı ekstra bonuslar (ekran kalitesi, SSD, CPU/GPU özellikleri)
    # ================================================================================

    return preferences

def display_recommendations(recommendations, preferences):
    """Önerileri göster - preferences parametresi eklendi"""
    if recommendations.empty:
        return

    usage_lbl = recommendations.attrs.get('usage_label', '')
    avg_score = recommendations.attrs.get('avg_score', 0)
    price_range = recommendations.attrs.get('price_range', (0, 0))

    print("\n" + "=" * 60)
    title = "🏆 ÖNERİLER"
    if usage_lbl:
        title += f" – {usage_lbl}"
    print(title.center(60))
    print("=" * 60)

    print(f"\n📊 Ortalama Skor: {avg_score:.1f}/100")
    print(f"💰 Fiyat Aralığı: {price_range[0]:,.0f} - {price_range[1]:,.0f} TL")
    print("-" * 60)

    for i, (_, lap) in enumerate(recommendations.iterrows(), 1):
        print(f"\n{i}. {lap.get('name', '(isimsiz)')}")
        print("-" * 60)

        # Temel bilgiler
        print(f"💰 Fiyat: {lap['price']:,.0f} TL")
        print(f"⭐ Puan: {lap['score']:.1f}/100")

        # Skor detayı (opsiyonel - debug için)
        if preferences.get('show_breakdown', False):
            print(f"   📈 Detay: {lap.get('score_breakdown', '')}")

        # Donanım bilgileri
        print(f"🏷️ Marka: {str(lap.get('brand', '')).title()}")
        print(f"💻 CPU: {lap.get('cpu', 'Belirtilmemiş')} (Skor: {lap.get('cpu_score', 0):.1f})")
        print(f"🎮 GPU: {lap.get('gpu', 'Belirtilmemiş')} (Skor: {lap.get('gpu_score', 0):.1f})")
        print(f"💾 RAM: {lap.get('ram_gb', 0):.0f} GB")
        print(f"💿 SSD: {lap.get('ssd_gb', 0):.0f} GB")
        print(f"📺 Ekran: {lap.get('screen_size', 0):.1f}\"")
        print(f"🖥️ OS: {lap.get('os', 'FreeDOS')}")

        # Link
        if 'url' in lap and pd.notna(lap['url']):
            print(f"🔗 Link: {lap['url']}")

def inspect_data(df):
    """Veri inceleme ve debug - Geliştirilmiş (GPU model sayımları eklendi)"""
    print("\n📊 VERİ İNCELEME")
    print("-" * 60)
    print(f"Toplam kayıt: {len(df)}")
    print(f"Kolonlar: {', '.join(df.columns)}")

    # Marka dağılımı
    print("\n🏷️ Marka Dağılımı:")
    brand_counts = df['brand'].value_counts()
    for brand, count in brand_counts.head(10).items():
        print(f"  {brand.title()}: {count} laptop")

    if 'price' in df.columns:
        print(f"\n💰 Fiyat Dağılımı:")
        print(f"  Min: {df['price'].min():,.0f} TL")
        print(f"  Max: {df['price'].max():,.0f} TL")
        print(f"  Ortalama: {df['price'].mean():,.0f} TL")
        print(f"  Medyan: {df['price'].median():,.0f} TL")

        # Fiyat aralıklarını göster
        print(f"\n💵 Fiyat Aralıkları:")
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
                print(f"  {label}: {count} laptop ({pct:.1f}%)")

    # RAM dağılımı
    if 'ram_gb' in df.columns:
        print(f"\n💾 RAM Dağılımı:")
        ram_counts = df['ram_gb'].value_counts().sort_index()
        for ram, count in ram_counts.items():
            print(f"  {ram:.0f} GB: {count} laptop")

    # GPU skor dağılımı
    if 'gpu' in df.columns:
        print("\n🧮 GPU Model Sayımları (detaylı):")
        gpu_norm = df['gpu'].apply(normalize_gpu_model)
        counts = gpu_norm.value_counts()

        total = counts.sum()
        integ = counts[counts.index.str.contains(r'iGPU|Integrated', case=False, regex=True)].sum()
        disc = total - integ
        print(f"  Toplam: {total} | Integrated: {integ} | Discrete: {disc}")

        # Model bazında tam liste
        for model, c in counts.items():
            print(f"  - {model}: {c}")

    # Örnek kayıtlar
    print(f"\n📝 Örnek Kayıtlar (ilk 3):")
    cols_to_show = ['name', 'price', 'brand', 'cpu_score', 'gpu_score', 'ram_gb', 'ssd_gb']
    available_cols = [c for c in cols_to_show if c in df.columns]
    sample_df = df[available_cols].head(3)
    for i, row in sample_df.iterrows():
        print(f"\n  Laptop {i + 1}:")
        for col in available_cols:
            val = row[col]
            if col == 'price':
                print(f"    {col}: {val:,.0f} TL")
            elif col == 'name':
                print(f"    {col}: {str(val)[:50]}...")
            else:
                print(f"    {col}: {val}")

    # =============================
    # YENİ: GPU MODEL SAYIMLARI
    # =============================
    if 'gpu' in df.columns:
        print("\n🧮 GPU Model Sayımları (normalize edilmiş):")
        gpu_norm = df['gpu'].apply(normalize_gpu_model)
        counts = gpu_norm.value_counts()

        # Önce kısa özet
        total = counts.sum()
        integ = counts[counts.index.str.contains(r'\(iGPU\)|Integrated', case=False, regex=True)].sum()
        disc = total - integ
        print(f"  Toplam: {total} | Integrated: {integ} | Discrete: {disc}")

        # Tam liste (çok uzun olursa yine de tamamını göster diyor)
        for model, c in counts.items():
            print(f"  - {model}: {c}")
    else:
        print("\nℹ️ 'gpu' kolonu bulunamadı; GPU model sayımı atlandı.")

def save_data(df, filename='laptop_data_export.csv'):
    """Veriyi CSV olarak kaydet"""
    try:
        filepath = BASE_DIR / filename
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"\n✅ Veri kaydedildi: {filepath}")
        print(f"   {len(df)} kayıt")
    except Exception as e:
        print(f"\n❌ Kayıt hatası: {e}")

def inspect_scrapers_separately():
    """Her scraper'ın verilerini ayrı ayrı analiz eder"""
    print("\n" + "=" * 60)
    print("SCRAPER VERİLERİ DETAYLI ANALİZ")
    print("=" * 60)

    scraper_files = {
        "Amazon": BASE_DIR / "amazon_laptops.csv",
    }

    for name, filepath in scraper_files.items():
        print(f"\n{'─' * 60}")
        print(f"📊 {name.upper()}")
        print(f"{'─' * 60}")

        if not filepath.exists():
            print(f"❌ Dosya bulunamadı: {filepath}")
            continue

        try:
            df = pd.read_csv(filepath, encoding='utf-8')

            # Temel bilgiler
            print(f"\n✓ Toplam kayıt: {len(df)}")
            print(f"✓ Kolonlar: {', '.join(df.columns)}")

            # Fiyat analizi
            if 'price' in df.columns:
                df['price_clean'] = df['price'].apply(clean_price)
                valid_prices = df['price_clean'].dropna()

                if len(valid_prices) > 0:
                    print(f"\n💰 Fiyat İstatistikleri:")
                    print(f"  • Geçerli fiyat: {len(valid_prices)}/{len(df)}")
                    print(f"  • Min: {valid_prices.min():,.0f} TL")
                    print(f"  • Max: {valid_prices.max():,.0f} TL")
                    print(f"  • Ortalama: {valid_prices.mean():,.0f} TL")
                    print(f"  • Medyan: {valid_prices.median():,.0f} TL")
                else:
                    print(f"\n⚠️ Geçerli fiyat bulunamadı!")

            # RAM dağılımı
            if 'ram' in df.columns:
                df['ram_clean'] = df['ram'].apply(clean_ram_value)
                print(f"\n💾 RAM Dağılımı:")
                ram_counts = df['ram_clean'].value_counts().sort_index()
                for ram, count in ram_counts.items():
                    print(f"  • {ram} GB: {count} laptop")

            # GPU analizi
            if 'gpu' in df.columns:
                print(f"\n🎮 GPU Dağılımı:")
                gpu_counts = df['gpu'].value_counts().head(10)
                for gpu, count in gpu_counts.items():
                    print(f"  • {str(gpu)[:40]}: {count}")

            # CPU analizi
            if 'cpu' in df.columns:
                print(f"\n🔧 CPU Dağılımı (İlk 10):")
                cpu_counts = df['cpu'].value_counts().head(10)
                for cpu, count in cpu_counts.items():
                    print(f"  • {str(cpu)[:40]}: {count}")

            score_scenarios = [
                {
                    'label': '30K-60K / Üretkenlik / Ofis',
                    'prefs': {
                        'min_budget': 30000,
                        'max_budget': 60000,
                        'usage_key': 'productivity',
                        'productivity_profile': 'office',
                    },
                },
                {
                    'label': '25K-45K / Taşınabilirlik',
                    'prefs': {
                        'min_budget': 25000,
                        'max_budget': 45000,
                        'usage_key': 'portability',
                    },
                },
                {
                    'label': '40K-80K / Oyun (Orta Seviye)',
                    'prefs': {
                        'min_budget': 40000,
                        'max_budget': 80000,
                        'usage_key': 'gaming',
                        'min_gpu_score_required': 6.0,
                    },
                },
                {
                    'label': '45K-90K / Tasarım (Video)',
                    'prefs': {
                        'min_budget': 45000,
                        'max_budget': 90000,
                        'usage_key': 'design',
                        'design_profiles': ['video'],
                        'design_gpu_hint': 'mid',
                        'design_min_ram_hint': 32,
                    },
                },
                {
                    'label': '35K-75K / Yazılım (Web/Backend)',
                    'prefs': {
                        'min_budget': 35000,
                        'max_budget': 75000,
                        'usage_key': 'dev',
                        'dev_mode': 'web',
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
                        print(f"\n⭐ Ortalama Puan ({label}): bulunamadı")
                        continue

                    filtered = filter_by_usage(budget_filtered, score_prefs['usage_key'], score_prefs)
                    if 'url' in filtered.columns:
                        filtered = filtered.drop_duplicates(subset=['url'], keep='first')
                    filtered = filtered.drop_duplicates(subset=['name', 'price'], keep='first')

                    if filtered.empty:
                        print(f"\n⭐ Ortalama Puan ({label}): bulunamadı")
                        continue

                    scores = []
                    for _, row in filtered.iterrows():
                        score, _ = calculate_score(row, score_prefs)
                        scores.append(score)
                    avg_score = float(sum(scores) / len(scores))
                    print(f"\n⭐ Ortalama Puan ({label}): {avg_score:.1f}/100")
            except Exception as e:
                print(f"\n⚠️ Ortalama puan hesaplanamadı: {e}")

            # OS dağılımı
            if 'os' in df.columns:
                print(f"\n💻 İşletim Sistemi:")
                os_counts = df['os'].value_counts()
                for os, count in os_counts.items():
                    print(f"  • {os}: {count}")

            # Örnek kayıtlar
            print(f"\n📝 Örnek Kayıtlar (İlk 2):")
            sample_cols = ['name', 'price', 'cpu', 'gpu', 'ram']
            available = [c for c in sample_cols if c in df.columns]
            for i, row in df[available].head(2).iterrows():
                print(f"\n  [{i + 1}]")
                for col in available:
                    val = row[col]
                    if col == 'name':
                        print(f"    {col}: {str(val)[:50]}...")
                    else:
                        print(f"    {col}: {val}")

        except Exception as e:
            print(f"❌ Okuma hatası: {e}")

    print(f"\n{'=' * 60}")

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Geliştirilmiş Laptop Öneri Sistemi')
    parser.add_argument('--run-scrapers', action='store_true', help='Scraper\'ları çalıştır')
    parser.add_argument('--debug', action='store_true', help='Debug modu (detaylı skorlar)')
    parser.add_argument('--nl', '--free-text', dest='free_text', action='store_true',
                        help='Serbest metin (akıllı) modu varsayılan olsun')
    args = parser.parse_args()

    print("=" * 60)
    print("🚀 GELİŞTİRİLMİŞ LAPTOP ÖNERİ SİSTEMİ v2.0")
    print("=" * 60)

    # Debug modu
    global preferences
    preferences = {'show_breakdown': args.debug}
    prefer_free_text = args.free_text

    # Scraper'ları çalıştır
    if args.run_scrapers:
        run_scrapers()

    # Veri yükle
    df = load_data()
    if df is None:
        return

    # Veriyi temizle
    df = clean_data(df)

    # Ana döngü
    while True:
        print("\n" + "=" * 60)
        print("ANA MENÜ")
        print("=" * 60)
        print("1. 🎯 Laptop önerisi al (klasik soru-cevap)")
        print("2. 🤖 Laptop önerisi al (serbest metin / akıllı)")
        print("3. 📊 Veri durumunu incele")
        print("4. 📋 Scraper verilerini ayrı ayrı incele")  # YENİ
        print("5. 💾 Veriyi CSV olarak kaydet")
        print("6. 🔄 Veriyi güncelle (Scraper çalıştır)")
        print("7. 🔍 Debug modunu aç/kapa")
        print("8. 🧪 Simülasyonu aktifleştir (100 senaryo)")
        print("9. ❌ Çıkış")

        if prefer_free_text:
            print("Not: --nl aktif, serbest metin modu varsayılan.")

        choice = input("\nSeçiminiz (1-9): ").strip()
        if not choice and prefer_free_text:
            choice = '2'

        if choice == '1':
            # Kullanıcı tercihlerini al
            user_prefs = get_user_preferences()
            user_prefs['show_breakdown'] = preferences.get('show_breakdown', False)

            # Önerileri hesapla
            recommendations = get_recommendations(df, user_prefs)

            # Önerileri göster
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

        elif choice == '4':  # YENİ
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
                print("✅ Veriler güncellendi!")

        elif choice == '7':
            preferences['show_breakdown'] = not preferences.get('show_breakdown', False)
            status = "açık" if preferences['show_breakdown'] else "kapalı"
            print(f"\n🔍 Debug modu {status}")
            input("\nDevam etmek için Enter'a basın...")

        elif choice == '8':
            run_simulation(n=100, seed=42, out_path="simulation_outputs.jsonl", df=df)
            input("\nDevam etmek icin Enter'a basin...")

        elif choice == '9':
            print("\n👋 İyi günler!")
            break

        else:
            print("\n⚠️ Geçersiz seçim!")
