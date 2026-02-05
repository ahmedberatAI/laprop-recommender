import sys
from typing import Any

_DEFAULT_ERRORS = "backslashreplace"


def _get_encoding(stream) -> str:
    return getattr(stream, "encoding", None) or getattr(sys.stdout, "encoding", None) or "utf-8"


def safe_str(x: Any, encoding: str | None = None, errors: str = _DEFAULT_ERRORS) -> str:
    if isinstance(x, bytes):
        enc = encoding or "utf-8"
        try:
            return x.decode(enc, errors=errors)
        except Exception:
            return x.decode("utf-8", errors=errors)

    s = str(x)
    enc = encoding or _get_encoding(sys.stdout)
    try:
        s.encode(enc)
        return s
    except UnicodeEncodeError:
        try:
            return s.encode(enc, errors=errors).decode(enc, errors=errors)
        except Exception:
            return s.encode("utf-8", errors=errors).decode("utf-8", errors=errors)


def safe_print(*args: Any, **kwargs: Any) -> None:
    sep = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    file = kwargs.pop("file", sys.stdout)
    flush = kwargs.pop("flush", False)
    errors = kwargs.pop("errors", _DEFAULT_ERRORS)

    if kwargs:
        unexpected = ", ".join(sorted(kwargs))
        raise TypeError(f"safe_print() got unexpected keyword arguments: {unexpected}")

    encoding = _get_encoding(file)
    safe_sep = safe_str(sep, encoding=encoding, errors=errors)
    safe_end = safe_str(end, encoding=encoding, errors=errors)
    safe_args = [safe_str(arg, encoding=encoding, errors=errors) for arg in args]
    text = safe_sep.join(safe_args) + safe_end

    try:
        file.write(text)
    except UnicodeEncodeError:
        safe_text = text.encode(encoding, errors=errors).decode(encoding, errors=errors)
        file.write(safe_text)

    if flush:
        try:
            file.flush()
        except Exception:
            pass
