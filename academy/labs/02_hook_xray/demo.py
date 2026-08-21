"""Lesson 02: replay the 12-hook atlas or run the canonical Python hook demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from academy.common import (
    live_examples_for_lab,
    load_trace,
    render_trace,
    run_live_example,
)


TRACE_PATH = Path(__file__).with_name("expected_trace.json")
LIVE_EXAMPLE = live_examples_for_lab("02")["default"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show Runtime's fixed hook lifecycle in recorded or live mode."
    )
    parser.add_argument(
        "--mode",
        choices=("recorded", "live"),
        default="recorded",
        help="recorded shows the 12-hook atlas; live delegates to 07_hooks.py",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode == "live":
        run_live_example(LIVE_EXAMPLE)
        return 0

    print(render_trace(load_trace(TRACE_PATH)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
