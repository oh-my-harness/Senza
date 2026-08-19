"""Run Academy Lab 06 in recorded or canonical live mode."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from academy.common import load_trace, render_trace, run_live_example

try:
    from .workflow_scenario import approve_and_publish, create_paused_checkpoint, restore_from_step
except ImportError:  # Direct script execution.
    from workflow_scenario import approve_and_publish, create_paused_checkpoint, restore_from_step


LIVE_EXAMPLES = {
    "workflow": "08_workflow.py",
    "executor": "39_executor_steps.py",
    "hitl": "41_human_in_the_loop.py",
    "recovery": "45_hooks_retries.py",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("recorded", "live"), default="recorded")
    parser.add_argument("--live-example", choices=tuple(LIVE_EXAMPLES), default="recovery")
    args = parser.parse_args()

    if args.mode == "live":
        run_live_example(LIVE_EXAMPLES[args.live_example])
        return

    trace = load_trace(Path(__file__).with_name("expected_trace.json"))
    print(render_trace(trace))

    with tempfile.TemporaryDirectory(prefix="senza-academy-workflow-") as tmp:
        checkpoint = Path(tmp) / "task.json"
        paused = create_paused_checkpoint(checkpoint)
        restored = restore_from_step(checkpoint, "check")
        completed = approve_and_publish(checkpoint, reviewer="academy-reviewer")

    print("\nDeterministic checkpoint evidence")
    print(f"- initial state: {paused['status']} at {paused['current_step']}")
    print(f"- restored check attempt: {restored['history'][1]['attempt']}")
    print(f"- after approval: {completed['status']}")
    print(f"- final step: {completed['history'][-1]['step']}")


if __name__ == "__main__":
    main()
