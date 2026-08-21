"""Lab 04: render provider-free context-layer diffs or delegate to live examples."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional


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


LAYER_ORDER = ("stable_prefix", "skill", "status", "trajectory", "compaction")
LIVE_EXAMPLES = live_examples_for_lab("04")

STABLE_PREFIX = (
    "system: You are a Senza Developer Agent; inspect before editing.",
    "tool schemas: read_file, search_files, run_tests (fixed order)",
)
SKILL_CATALOG = (
    "catalog: code-review — use for repository review tasks (metadata only)",
)


def context_snapshots() -> list[dict[str, Any]]:
    """Return deterministic snapshots of the five conceptual context layers."""

    return [
        {
            "name": "request_0_catalog",
            "layers": {
                "stable_prefix": STABLE_PREFIX,
                "skill": SKILL_CATALOG,
                "status": (),
                "trajectory": ("user: Review the payment patch and cite evidence.",),
                "compaction": (),
            },
        },
        {
            "name": "request_1_skill_loaded",
            "layers": {
                "stable_prefix": STABLE_PREFIX,
                "skill": SKILL_CATALOG
                + ("loaded: code-review checklist — tests, security, errors, evidence",),
                "status": (),
                "trajectory": (
                    "user: Review the payment patch and cite evidence.",
                    "assistant: call skill_read(name=code-review)",
                    "tool: skill_read returned the review checklist",
                ),
                "compaction": (),
            },
        },
        {
            "name": "request_2_status_and_trajectory",
            "layers": {
                "stable_prefix": STABLE_PREFIX,
                "skill": SKILL_CATALOG
                + ("loaded: code-review checklist — tests, security, errors, evidence",),
                "status": (
                    "<agent_status>todo=inspect(in_progress), test(pending); read_file=2</agent_status>",
                ),
                "trajectory": (
                    "user: Review the payment patch and cite evidence.",
                    "assistant: call skill_read(name=code-review)",
                    "tool: skill_read returned the review checklist",
                    "assistant: call read_file(src/payment.py)",
                    "tool: payment.py contains retry and signature verification code",
                    "user: Keep the original constraint: do not edit files.",
                ),
                "compaction": (),
            },
        },
        {
            "name": "request_3_after_compaction",
            "layers": {
                "stable_prefix": STABLE_PREFIX,
                "skill": SKILL_CATALOG,
                "status": (
                    "<agent_status>todo=inspect(done), test(in_progress); read_file=2</agent_status>",
                ),
                "trajectory": (
                    "user: Keep the original constraint: do not edit files.",
                    "assistant: prepare evidence-backed review",
                ),
                "compaction": (
                    "## Goal: review the payment patch without editing files",
                    "## Progress: inspected payment.py and loaded code-review skill",
                    "## Key Decisions: verify retry and signature behavior",
                    "## Next Steps: run focused tests and report evidence",
                    "## Critical Context: preserve the user's no-edit constraint",
                ),
            },
        },
    ]


def _preview(values: tuple[str, ...]) -> str:
    if not values:
        return "<empty>"
    head = values[0]
    return head if len(head) <= 76 else f"{head[:73]}..."


def diff_snapshots(before: dict[str, Any], after: dict[str, Any]) -> str:
    """Render every layer so unchanged stable-prefix behavior stays visible."""

    lines = [f"Context diff: {before['name']} -> {after['name']}"]
    before_layers = before["layers"]
    after_layers = after["layers"]

    for layer in LAYER_ORDER:
        old = before_layers[layer]
        new = after_layers[layer]
        if old == new:
            marker = "="
        elif not old and new:
            marker = "+"
        elif old and not new:
            marker = "-"
        else:
            marker = "~"
        lines.append(
            f"  {marker} {layer:<14} {len(old)} -> {len(new)} | {_preview(new)}"
        )
    return "\n".join(lines)


def context_diffs() -> list[str]:
    snapshots = context_snapshots()
    return [
        diff_snapshots(before, after)
        for before, after in zip(snapshots, snapshots[1:])
    ]


def run_recorded() -> None:
    snapshots = context_snapshots()
    prefixes = [snapshot["layers"]["stable_prefix"] for snapshot in snapshots]
    if any(prefix != STABLE_PREFIX for prefix in prefixes):
        raise RuntimeError("stable prefix changed in recorded context model")
    if len(snapshots[-1]["layers"]["trajectory"]) >= len(
        snapshots[-2]["layers"]["trajectory"]
    ):
        raise RuntimeError("compaction did not reduce the recorded trajectory")

    trace = load_trace(LAB_DIR / "expected_trace.json")
    print(render_trace(trace))
    print("\nContext layer diffs")
    for rendered_diff in context_diffs():
        print(f"\n{rendered_diff}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("recorded", "live"),
        default="recorded",
        help="recorded is provider-free; live delegates to a canonical example",
    )
    parser.add_argument(
        "--live-example",
        choices=tuple(LIVE_EXAMPLES),
        default="skills",
        help="canonical example selected when --mode live (default: skills)",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    if args.mode == "live":
        run_live_example(LIVE_EXAMPLES[args.live_example])
        return
    run_recorded()


if __name__ == "__main__":
    main()
