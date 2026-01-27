from pathlib import Path
from pkgutil import extend_path

# Shim package to expose src/laprop without requiring PYTHONPATH tweaks.
_root = Path(__file__).resolve().parent.parent
_src_pkg = _root / "src" / "laprop"

if not _src_pkg.exists():
    raise ImportError("src/laprop not found; expected package layout is missing.")

# Allow submodule discovery in src/laprop
__path__ = extend_path(__path__, __name__)
if str(_src_pkg) not in __path__:
    __path__.append(str(_src_pkg))

# Execute the real package initializer in this module's namespace.
_src_init = _src_pkg / "__init__.py"
code = compile(_src_init.read_text(encoding="utf-8"), str(_src_init), "exec")
globals()["__file__"] = str(_src_init)
globals()["__package__"] = __name__
exec(code, globals(), globals())
