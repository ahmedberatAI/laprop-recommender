from pathlib import Path
import sys

root = Path(__file__).resolve().parent
src = root / "src"
if src.exists():
    src_str = str(src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
