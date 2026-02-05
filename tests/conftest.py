from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"

for path in (src_path, repo_root):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
