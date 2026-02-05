from pathlib import Path
import os
import sys

_STDIO_ERRORS = "backslashreplace"


def _reconfigure_stream(stream) -> None:
    try:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors=_STDIO_ERRORS)
            return
    except Exception:
        return

    try:
        if hasattr(stream, "buffer"):
            import io

            wrapped = io.TextIOWrapper(stream.buffer, encoding="utf-8", errors=_STDIO_ERRORS)
            if stream is sys.stdout:
                sys.stdout = wrapped
            elif stream is sys.stderr:
                sys.stderr = wrapped
    except Exception:
        return

root = Path(__file__).resolve().parent
src = root / "src"
if src.exists():
    src_str = str(src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

if not os.environ.get("PYTHONIOENCODING"):
    _reconfigure_stream(sys.stdout)
    _reconfigure_stream(sys.stderr)
