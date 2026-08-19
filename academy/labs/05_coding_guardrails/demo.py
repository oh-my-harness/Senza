"""Run Academy Lab 05 in recorded or canonical live mode."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from academy.common import load_trace, render_trace, run_live_example

try:
    from .coding_scenario import run_scenario
except ImportError:  # Direct script execution.
    from coding_scenario import run_scenario


LIVE_EXAMPLES = {
    "fs": "22_fs_tools.py",
    "approval": "14_rules_approval.py",
    "safety": "15_safety_injection.py",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("recorded", "live"), default="recorded")
    parser.add_argument("--live-example", choices=tuple(LIVE_EXAMPLES), default="fs")
    args = parser.parse_args()

    if args.mode == "live":
        run_live_example(LIVE_EXAMPLES[args.live_example])
        return

    trace = load_trace(Path(__file__).with_name("expected_trace.json"))
    print(render_trace(trace))
    result = run_scenario()
    print("\nDeterministic evidence")
    print(f"- failing test return code: {result['before_returncode']}")
    print(f"- passing test return code: {result['after_returncode']}")
    print(f"- minimal change: {result['changed_line']}")
    print(
        "- dangerous command: "
        f"{result['dangerous_command']['action']} "
        f"(executed={result['dangerous_command']['executed']})"
    )


if __name__ == "__main__":
    main()
