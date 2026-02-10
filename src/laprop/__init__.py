"""laprop — Laptop Recommendation Engine for the Turkish market.

Public API surface — import submodules directly for full access:
  laprop.config.rules        — scoring weights, usage options
  laprop.config.settings     — paths, file locations
  laprop.processing.clean    — data cleaning pipeline
  laprop.processing.read     — CSV loading utilities
  laprop.recommend.engine    — scoring + recommendations
  laprop.app.cli             — CLI entry point
"""

from .processing.read import load_data
from .processing.clean import clean_data
from .recommend.engine import get_recommendations
from .config.rules import USAGE_OPTIONS


def main():
    """CLI entry point."""
    from .app.main import main as _main
    return _main()


__all__ = [
    "load_data",
    "clean_data",
    "get_recommendations",
    "USAGE_OPTIONS",
    "main",
]
