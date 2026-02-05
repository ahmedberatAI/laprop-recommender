from pathlib import Path
import pandas as pd

from ..utils.console import safe_print
from .settings import BASE_DIR

BENCH_GPU_PATH = BASE_DIR / "bench_gpu.csv"
BENCH_CPU_PATH = BASE_DIR / "bench_cpu.csv"

GPU_BENCH, CPU_BENCH = None, None
_WARNED_KEYS: set[str] = set()


def _warn_once(key: str, msg: str) -> None:
    if key in _WARNED_KEYS:
        return
    _WARNED_KEYS.add(key)
    safe_print(msg)


def _safe_load_bench(path: Path):
    """
    bench csv format expectation:
      - model: str
      - score_0_10 (preferred) or perf_idx/time_spy_gfx/cinebench_r23_multi/geekbench6_multi
    """
    try:
        if path.exists():
            df = pd.read_csv(path, encoding="utf-8")

            if "model" not in df.columns:
                _warn_once(
                    f"missing_model:{path.name}",
                    f"[WARN] {path.name} missing required 'model' column.",
                )
                return None

            df["model"] = df["model"].astype(str).str.lower().str.strip()

            score_col = None
            for c in [
                "score_0_10",
                "perf_idx",
                "time_spy_gfx",
                "cinebench_r23_multi",
                "geekbench6_multi",
            ]:
                if c in df.columns:
                    score_col = c
                    break

            if score_col is None:
                _warn_once(
                    f"missing_score:{path.name}",
                    f"[WARN] {path.name} missing score column (score_0_10/perf_idx/...).",
                )
                return None

            if score_col != "score_0_10":
                x = pd.to_numeric(df[score_col], errors="coerce")
                xmin, xmax = float(x.min()), float(x.max())
                if xmax > xmin:
                    df["score_0_10"] = 10 * (x - xmin) / (xmax - xmin)
                else:
                    df["score_0_10"] = 5.0

            return df

        _warn_once(
            f"missing_file:{path.name}",
            f"[WARN] {path.name} not found; skipping benchmark table.",
        )
        return None

    except Exception as e:
        _warn_once(
            f"read_error:{path.name}",
            f"[WARN] {path.name} could not be read: {e}",
        )
        return None


GPU_BENCH = _safe_load_bench(BENCH_GPU_PATH)
CPU_BENCH = _safe_load_bench(BENCH_CPU_PATH)
