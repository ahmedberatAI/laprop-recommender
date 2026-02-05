import os
import subprocess
import sys

from ..config.settings import SCRAPERS, DATA_FILES, CACHE_FILE
from ..storage.repository import append_to_all_data
from ..utils.console import safe_print


def run_scrapers():
    """Run scrapers and refresh master dataset."""
    safe_print("\n[INFO] Scrapers are running...")
    safe_print("-" * 50)

    def _mtime(p):
        try:
            return os.path.getmtime(p)
        except Exception:
            return 0

    if DATA_FILES:
        data_dir = DATA_FILES[0].parent
        os.makedirs(data_dir, exist_ok=True)
    else:
        data_dir = None

    output_paths = {
        "amazon": os.path.join(str(data_dir or "."), "amazon_laptops.csv"),
        "incehesap": os.path.join(str(data_dir or "."), "incehesap_laptops.csv"),
        "vatan": os.path.join(str(data_dir or "."), "vatan_laptops.csv"),
    }

    before_mtime = {p.name: _mtime(p) for p in DATA_FILES}

    try:
        for name, script_path in SCRAPERS.items():
            if not script_path.exists():
                safe_print(f"[WARN] {script_path} not found")
                continue

            try:
                safe_print(f"[INFO] Fetching {name.title()} data...")

                env = os.environ.copy()
                env.setdefault("FAST_SCRAPE", "1")
                env.setdefault("PYTHONIOENCODING", "utf-8")

                cmd = [sys.executable, str(script_path)]
                if name == "amazon":
                    cmd += ["--output", output_paths["amazon"]]
                elif name == "vatan":
                    cmd += ["--out", output_paths["vatan"]]
                elif name == "incehesap":
                    cmd += ["scrape", "--output", output_paths["incehesap"]]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=600,
                    env=env,
                )

                ok = (result.returncode == 0)
                safe_print(
                    "[OK]" if ok else "[WARN]",
                    name.title(),
                    "done" if ok else f"failed (code {result.returncode})",
                )

                stdout = (result.stdout or "").strip()
                stderr = (result.stderr or "").strip()
                if stdout and len(stdout) > 100:
                    safe_print(f"   [STDOUT] {stdout[:800]}")
                if stderr and len(stderr) > 100:
                    safe_print(f"   [STDERR] {stderr[:800]}")

            except subprocess.TimeoutExpired as e:
                safe_print(f"[WARN] {name.title()} timed out (> {e.timeout}s)")
            except Exception as e:
                safe_print(f"[ERROR] {name.title()} failed to run: {e}")
    finally:
        append_to_all_data()

    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        safe_print("\n[INFO] Cache cleared")

    after_mtime = {p.name: _mtime(p) for p in DATA_FILES}
    for p in DATA_FILES:
        nm = p.name
        if after_mtime[nm] > before_mtime[nm]:
            safe_print(f"[OK] {nm} updated")
        else:
            safe_print(f"[INFO]  {nm} not updated")
