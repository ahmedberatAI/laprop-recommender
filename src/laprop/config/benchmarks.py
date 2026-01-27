from pathlib import Path
import pandas as pd

from .settings import BASE_DIR

BENCH_GPU_PATH = BASE_DIR / "bench_gpu.csv"
BENCH_CPU_PATH = BASE_DIR / "bench_cpu.csv"

GPU_BENCH, CPU_BENCH = None, None

def _safe_load_bench(path: Path):
    """
    bench csv format beklentisi:
      - model: str
      - score_0_10 (varsa direkt) veya perf_idx/time_spy_gfx/cinebench_r23_multi/geekbench6_multi
    """
    def _safe_print(msg: str) -> None:
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode("ascii", errors="replace").decode("ascii"))

    try:
        if path.exists():
            df = pd.read_csv(path, encoding="utf-8")

            if 'model' not in df.columns:
                _safe_print(f"⚠️  {path.name} içinde 'model' kolonu yok.")
                return None

            df['model'] = df['model'].astype(str).str.lower().str.strip()

            score_col = None
            for c in ['score_0_10', 'perf_idx', 'time_spy_gfx', 'cinebench_r23_multi', 'geekbench6_multi']:
                if c in df.columns:
                    score_col = c
                    break

            if score_col is None:
                _safe_print(f"⚠️  {path.name}: skor kolonu (score_0_10/perf_idx/...) bulunamadı.")
                return None

            if score_col != 'score_0_10':
                x = pd.to_numeric(df[score_col], errors='coerce')
                xmin, xmax = float(x.min()), float(x.max())
                if xmax > xmin:
                    df['score_0_10'] = 10 * (x - xmin) / (xmax - xmin)
                else:
                    df['score_0_10'] = 5.0

            return df

        _safe_print(f"ℹ️  {path.name} bulunamadı (opsiyonel). İç puanlama ile devam edilecek.")
        return None

    except Exception as e:
        _safe_print(f"⚠️  {path.name} okunamadı: {e}")
        return None

GPU_BENCH = _safe_load_bench(BENCH_GPU_PATH)
CPU_BENCH = _safe_load_bench(BENCH_CPU_PATH)
