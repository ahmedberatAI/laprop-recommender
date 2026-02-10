"""Centralized logging configuration for laprop.

Usage in any module:
    from laprop.utils.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Something happened")
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

_CONFIGURED = False

LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
LOG_FILE = LOG_DIR / "laprop.log"

# Unicode-safe formatter that won't crash on Windows consoles
class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that gracefully handles encoding errors."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            stream = self.stream
            encoding = getattr(stream, "encoding", None) or "utf-8"
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                safe_msg = msg.encode(encoding, errors="backslashreplace").decode(
                    encoding, errors="backslashreplace"
                )
                stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
) -> None:
    """Configure the root ``laprop`` logger (console + file).

    Calling this multiple times is safe — only the first call takes effect.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    root = logging.getLogger("laprop")
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Console handler (unicode-safe) ---
    console = SafeStreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # --- File handler (optional, best-effort) ---
    target = log_file or LOG_FILE
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(target, encoding="utf-8", delay=True)
        fh.setLevel(logging.DEBUG)  # file captures everything
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception:
        # If log dir is read-only (e.g. deployed on Streamlit Cloud), skip silently.
        pass


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``laprop`` namespace.

    Automatically calls :func:`setup_logging` on first use so callers
    never need to worry about initialization order.
    """
    setup_logging()
    return logging.getLogger(name)
