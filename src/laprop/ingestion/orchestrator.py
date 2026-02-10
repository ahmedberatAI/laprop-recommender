import os
import subprocess
import sys

from ..config.settings import SCRAPERS, DATA_FILES, CACHE_FILE
from ..storage.repository import append_to_all_data
from ..utils.logging import get_logger

logger = get_logger(__name__)


def run_scrapers():
    """Run scrapers and refresh master dataset."""
    logger.info("Scrapers are running...")

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
                logger.warning("%s not found", script_path)
                continue

            try:
                logger.info("Fetching %s data...", name.title())

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
                logger.info(
                    "%s %s %s",
                    "[OK]" if ok else "[WARN]",
                    name.title(),
                    "done" if ok else f"failed (code {result.returncode})",
                )

                stdout = (result.stdout or "").strip()
                stderr = (result.stderr or "").strip()
                if stdout and len(stdout) > 100:
                    logger.debug("[STDOUT] %s", stdout[:800])
                if stderr and len(stderr) > 100:
                    logger.warning("[STDERR] %s", stderr[:800])

            except subprocess.TimeoutExpired as e:
                logger.warning("%s timed out (> %ss)", name.title(), e.timeout)
            except Exception as e:
                logger.error("%s failed to run: %s", name.title(), e)
    finally:
        append_to_all_data()

    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        logger.info("Cache cleared")

    # Also clean up legacy pickle if it still exists
    legacy_pkl = CACHE_FILE.with_suffix(".pkl")
    if legacy_pkl.exists():
        legacy_pkl.unlink(missing_ok=True)
        logger.info("Legacy pickle cache removed: %s", legacy_pkl)

    after_mtime = {p.name: _mtime(p) for p in DATA_FILES}
    for p in DATA_FILES:
        nm = p.name
        if after_mtime[nm] > before_mtime[nm]:
            logger.info("[OK] %s updated", nm)
        else:
            logger.info("%s not updated", nm)
