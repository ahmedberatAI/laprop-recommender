"""Run recommendation simulations from the command line.

Examples:
  python simulation.py --n 50
  python simulation.py --n 200 --seed 42
"""

from __future__ import annotations

import argparse
import inspect
from typing import Optional

from laprop.app.cli import run_simulation
from laprop.recommend.scenarios import SCENARIOS  # noqa: F401
from laprop.processing.read import load_data
from laprop.processing.clean import clean_data


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run simulation scenarios with the current dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  python simulation.py --n 50\n  python simulation.py --n 200 --seed 42",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=100,
        help="Number of scenarios to run (default: 100).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed (optional). Ignored if run_simulation does not accept it.",
    )
    return parser.parse_args(argv)


def _call_run_simulation(n: int, seed: Optional[int], df) -> None:
    kwargs = {"n": n, "df": df}

    try:
        sig = inspect.signature(run_simulation)
        params = sig.parameters
        supports_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )
        if seed is not None and ("seed" in params or supports_kwargs):
            kwargs["seed"] = seed
    except (TypeError, ValueError):
        # If we cannot inspect the signature, best-effort fallback.
        if seed is not None:
            try:
                run_simulation(n=n, seed=seed, df=df)
                return
            except TypeError:
                pass

    run_simulation(**kwargs)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    n = max(0, int(args.n))

    df = load_data()
    if df is None:
        return 1

    df = clean_data(df)
    _call_run_simulation(n=n, seed=args.seed, df=df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
