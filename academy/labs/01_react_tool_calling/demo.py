"""Lesson 01: replay or run the canonical ReAct/tool-calling demonstration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from academy.common import load_trace, render_trace, run_live_example


TRACE_PATH = Path(__file__).with_name("expected_trace.json")
LIVE_EXAMPLE = "02_tool_calling.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show the ReAct tool-calling loop in recorded or live mode."
    )
    parser.add_argument(
        "--mode",
        choices=("recorded", "live"),
        default="recorded",
        help="recorded is provider-free; live delegates to the canonical Senza example",
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
