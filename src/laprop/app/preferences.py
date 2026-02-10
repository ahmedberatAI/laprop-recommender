"""User preference gathering — interactive CLI prompts."""

from ..config.rules import USAGE_OPTIONS, GAMING_TITLE_SCORES
from ..utils.console import safe_print
from .nlp import (
    normalize_and_complete_preferences,
    parse_design_profile_from_text,
)
from .llm_prefs import parse_preferences_hybrid


def _prompt_design_details() -> dict:
    """
    Kullanıcıya tasarım alan(lar)ını çoklu seçimle sorar.
    """
    safe_print("\n🎨 Tasarım profili (birden çok seçebilirsiniz)")
    safe_print("-" * 40)
    options = {
        1: ('graphic', "Grafik tasarım / fotoğraf (Photoshop, Illustrator, Figma)"),
        2: ('video',   "Video düzenleme / motion (Premiere, After Effects, DaVinci)"),
        3: ('3d',      "3D modelleme / render (Blender, Maya, 3ds Max, C4D)"),
        4: ('cad',     "Mimari / teknik çizim (AutoCAD, Revit, Solidworks)")
    }
    for k, (_, desc) in options.items():
        safe_print(f"{k}. {desc}")

    safe_print("\nBirden fazla seçim için virgül kullanın (örn: 1,3). Boş bırakılırsa 1 (Grafik) kabul edilir.")
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
        chosen_keys = ['graphic']

    if any(k in chosen_keys for k in ['3d']):
        gpu_hint = 'high'
    elif any(k in chosen_keys for k in ['video', 'cad']):
        gpu_hint = 'mid'
    else:
        gpu_hint = 'low'

    min_ram = 32 if any(k in chosen_keys for k in ['3d', 'video', 'cad']) else 16

    return {
        'design_profiles': chosen_keys,
        'design_gpu_hint': gpu_hint,
        'design_min_ram_hint': min_ram
    }


def _prompt_productivity_details() -> dict:
    safe_print("\n📈 Üretkenlik profili")
    safe_print("-" * 30)
    opts = {
        1: ('office', "Ofis işleri / doküman düzenleme / sunum"),
        2: ('data', "Veri yoğun işler (Excel, analiz, raporlama)"),
        3: ('light_dev', "Hafif yazılım geliştirme"),
        4: ('multitask', "Çoklu görev (çok pencere / çok monitör)")
    }
    for k, (_, desc) in opts.items():
        safe_print(f"{k}. {desc}")

    profile = 'office'
    try:
        sel = int(input("Seçiminiz (1-4): ").strip())
        if sel in opts:
            profile = opts[sel][0]
    except (ValueError, EOFError):
        pass

    return {'productivity_profile': profile}


def _prompt_gaming_titles() -> list:
    """CLI: 10 oyunu numaralı listeyle gösterir, kullanıcıdan seçim alır."""
    safe_print("\n🎮 Oyun listesi (gelecekte oynamak istediklerinizi seçin)")
    titles = list(GAMING_TITLE_SCORES.keys())
    for i, t in enumerate(titles, 1):
        safe_print(f"{i}. {t}  (gpu_score ≥ {GAMING_TITLE_SCORES[t]:.1f})")

    safe_print("\nBirden fazla seçim için virgül kullanın (örn: 1,3,7).")
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
            safe_print("Lütfen geçerli bir sayı girin.")

    min_b = p.get('min_budget')
    max_b = p.get('max_budget')

    if min_b is None:
        min_b = ask_float("Minimum bütçe (TL): ")
    if max_b is None:
        max_b = ask_float("Maksimum bütçe (TL): ")

    if min_b is not None and max_b is not None and min_b > max_b:
        safe_print("Uyarı: Minimum bütçe maksimumdan büyük, yer değiştirildi.")
        min_b, max_b = max_b, min_b

    p['min_budget'] = float(min_b)
    p['max_budget'] = float(max_b)

    if not p.get('usage_key'):
        safe_print("\nKullanım amacını seçin:")
        for k, (_, label) in USAGE_OPTIONS.items():
            safe_print(f"{k}. {label}")
        while True:
            sel = input("Seçiminiz (1-5): ").strip()
            if sel.isdigit() and int(sel) in USAGE_OPTIONS:
                p['usage_key'] = USAGE_OPTIONS[int(sel)][0]
                p['usage_label'] = USAGE_OPTIONS[int(sel)][1]
                break
            safe_print("Geçersiz seçim, tekrar deneyin.")
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
            safe_print("\nYazılım geliştirme profili")
            dev_opts = {
                1: ('web', 'Web/Backend'),
                2: ('ml', 'Veri/ML'),
                3: ('mobile', 'Mobil (Android/iOS)'),
                4: ('gamedev', 'Oyun Motoru / 3D'),
                5: ('general', 'Genel CS')
            }
            for i, (_, label) in dev_opts.items():
                safe_print(f"{i}. {label}")
            while True:
                sel = input("Seçiminiz (1-5, boş=genel): ").strip()
                if not sel:
                    p['dev_mode'] = 'general'
                    break
                if sel.isdigit() and int(sel) in dev_opts:
                    p['dev_mode'] = dev_opts[int(sel)][0]
                    break
                safe_print("Geçersiz seçim, tekrar deneyin.")

    return p


def get_user_preferences_free_text() -> dict:
    """Serbest metinle tercih toplama akışı."""
    safe_print("\nİhtiyacını tek cümlede yaz (örn: 35-55k, oyun + okul, 15.6, RTX 4060 olsun, pil önemli)")
    raw = input("Tercihin: ").strip()

    prefs = parse_preferences_hybrid(raw)
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
    safe_print(f"\nAnladığım: bütçe={budget_summary}, amaç={usage_label}{extra}")

    if not prefs.get('usage_key'):
        safe_print("Amaç net değil, birkaç soru soracağım.")

    prefs = ask_missing_preferences(prefs)

    if prefs.get('usage_key') == 'dev' and prefs.get('dev_mode') == 'ml':
        safe_print("Not: ML için NVIDIA/CUDA uyumu genelde kritik.")

    prefs['show_breakdown'] = globals().get('preferences', {}).get('show_breakdown', False)
    return prefs


def get_user_preferences():
    """Kullanıcıdan tercihlerini al"""
    safe_print("\n" + "=" * 60)
    safe_print("💻 LAPTOP ÖNERİ – Tercihler".center(60))
    safe_print("=" * 60)

    preferences = {}

    # Bütçe
    safe_print("\n💰 BÜTÇE BİLGİLERİ")
    safe_print("-" * 30)

    while True:
        try:
            min_budget = float(input("Minimum bütçe (TL): "))
            max_budget = float(input("Maksimum bütçe (TL): "))

            if min_budget <= 0 or max_budget <= 0:
                safe_print("⚠️ Bütçe 0'dan büyük olmalı!")
                continue
            if min_budget > max_budget:
                safe_print("⚠️ Minimum bütçe maksimumdan büyük olamaz!")
                continue

            preferences['min_budget'] = min_budget
            preferences['max_budget'] = max_budget
            break
        except ValueError:
            safe_print("⚠️ Lütfen geçerli bir sayı girin!")

    # Kullanım amacı
    safe_print("\n🎯 KULLANIM AMACI")
    safe_print("-" * 30)
    for k, (_, label) in USAGE_OPTIONS.items():
        safe_print(f"{k}. {label}")

    while True:
        try:
            sel = int(input("Seçiminiz (1-5): ").strip())
            if sel in USAGE_OPTIONS:
                preferences['usage_key'] = USAGE_OPTIONS[sel][0]
                preferences['usage_label'] = USAGE_OPTIONS[sel][1]
                break
        except (ValueError, EOFError):
            pass
        safe_print("⚠️ Geçersiz seçim, tekrar deneyin.")

    if preferences['usage_key'] == 'dev':
        safe_print("\n🔧 Yazılım geliştirme profili")
        safe_print("-" * 30)
        dev_opts = {
            1: ('web', '🌐 Web/Backend'),
            2: ('ml', '📊 Veri/ML'),
            3: ('mobile', '📱 Mobil (Android/iOS)'),
            4: ('gamedev', '🎮 Oyun Motoru / 3D'),
            5: ('general', '🧰 Genel CS')
        }
        for i, (_, label) in dev_opts.items():
            safe_print(f"{i}. {label}")
        while True:
            try:
                sel = int(input("Seçiminiz (1-5): ").strip())
                if sel in dev_opts:
                    preferences['dev_mode'] = dev_opts[sel][0]
                    break
            except (ValueError, EOFError):
                pass
            safe_print("⚠️ Geçersiz seçim, tekrar deneyin.")
    elif preferences.get('usage_key') == 'gaming':
        picked = _prompt_gaming_titles()
        if picked:
            preferences['gaming_titles'] = picked
            needed = max(GAMING_TITLE_SCORES[t] for t in picked)
            preferences['min_gpu_score_required'] = max(6.0, needed)
            safe_print(f"\n🧮 Oyun eşiği ayarlandı → min gpu_score: {preferences['min_gpu_score_required']:.1f}")
        else:
            preferences['gaming_titles'] = []
            preferences['min_gpu_score_required'] = 6.0
    elif preferences.get('usage_key') == 'productivity':
        prod = _prompt_productivity_details()
        preferences.update(prod)
    elif preferences.get('usage_key') == 'design':
        des = _prompt_design_details()
        preferences.update(des)

    return preferences
