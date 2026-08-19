"""Lesson 08: deterministic manager lifecycle or canonical live spawn demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from academy.common import load_trace, render_trace, run_live_example

from state_model import run_recorded_scenario


TRACE_PATH = Path(__file__).with_name("expected_trace.json")
LIVE_EXAMPLE = "11_spawn_subagent.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show isolated child contexts and the spawn control lifecycle."
    )
    parser.add_argument(
        "--mode",
        choices=("recorded", "live"),
        default="recorded",
        help="recorded runs a deterministic state model; live delegates to example 11",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode == "live":
        run_live_example(LIVE_EXAMPLE)
        return 0

    scenario = run_recorded_scenario()
    trace = load_trace(TRACE_PATH)
    if scenario.events != trace["events"]:
        raise RuntimeError("recorded state model drifted from expected_trace.json")

    print(render_trace(trace))
    print("\nDeterministic final state")
    for snapshot in scenario.coordinator.query_subagent():
        print(f"- {snapshot['agent_id']}: {snapshot['status']} (role metadata: {snapshot['role']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
