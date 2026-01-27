import os
import subprocess
import sys

from ..config.settings import SCRAPERS, DATA_FILES, CACHE_FILE
from ..storage.repository import append_to_all_data
def run_scrapers():
    """Scraper'ları çalıştır"""
    print("\n🔄 Scraper'lar çalıştırılıyor...")
    print("-" * 50)

    def _mtime(p):
        try:
            return os.path.getmtime(p)
        except:
            return 0

    before_mtime = {p.name: _mtime(p) for p in DATA_FILES}

    for name, script_path in SCRAPERS.items():
        if not script_path.exists():
            print(f"⚠️ {script_path} bulunamadı")
            continue

        try:
            print(f"⏳ {name.title()} verisi çekiliyor...")

            env = os.environ.copy()
            env.setdefault("FAST_SCRAPE", "1")
            env.setdefault("PYTHONIOENCODING", "utf-8")

            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
                env=env
            )

            ok = (result.returncode == 0)
            print("✅" if ok else "⚠️", name.title(), "tamamlandı" if ok else f"hata verdi (code {result.returncode})")

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            if stdout and len(stdout) > 100:
                print(f"   ▶ stdout: {stdout[:800]}")
            if stderr and len(stderr) > 100:
                print(f"   ▶ stderr: {stderr[:800]}")

        except subprocess.TimeoutExpired as e:
            print(f"⏱️ {name.title()} zaman aşımı (> {e.timeout}s)")
        except Exception as e:
            print(f"❌ {name.title()} çalıştırılamadı: {e}")

    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        print("\n🧹 Önbellek temizlendi")

    after_mtime = {p.name: _mtime(p) for p in DATA_FILES}
    for p in DATA_FILES:
        nm = p.name
        if after_mtime[nm] > before_mtime[nm]:
            print(f"🆕 {nm} güncellendi")
        else:
            print(f"ℹ️  {nm} güncellenmedi")
    append_to_all_data()
