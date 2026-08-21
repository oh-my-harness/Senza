"""Run the Academy reliability evaluator or delegate to observability examples."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = LAB_DIR.parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from academy.common import (  # noqa: E402
    live_examples_for_lab,
    load_trace,
    render_trace,
    run_live_example,
)

from evaluation import evaluate, load_jsonl, render_markdown  # noqa: E402


LIVE_EXAMPLES = live_examples_for_lab("09")


def build_report():
    fixtures = LAB_DIR / "fixtures"
    return evaluate(
        load_jsonl(fixtures / "cases.jsonl"),
        load_jsonl(fixtures / "recorded_runs.jsonl"),
        k=3,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("recorded", "live"), default="recorded")
    parser.add_argument("--live-example", choices=tuple(LIVE_EXAMPLES), default="audit")
    args = parser.parse_args()

    if args.mode == "live":
        run_live_example(LIVE_EXAMPLES[args.live_example])
        return

    print(render_trace(load_trace(LAB_DIR / "expected_trace.json")))
    print("\n" + render_markdown(build_report()))


if __name__ == "__main__":
    main()
