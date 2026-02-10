"""NLP text parsing and intent detection for laptop preferences."""

import re
import difflib
from typing import Optional, Tuple, List, Any

import numpy as np

from ..config.rules import GAMING_TITLE_SCORES


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
    from ..config.rules import USAGE_OPTIONS

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
