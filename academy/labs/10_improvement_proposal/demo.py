"""Lab 10: generate a provider-free proposal or inspect canonical live evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


LAB_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = LAB_DIR.parents[2]
for import_path in (LAB_DIR, REPOSITORY_ROOT):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from academy.common import load_trace, render_trace, run_live_example  # noqa: E402
from proposal import run_proposal_pipeline  # noqa: E402


FIXTURES_DIR = LAB_DIR / "fixtures"
BAD_CASES_PATH = FIXTURES_DIR / "bad_cases.jsonl"
RETENTION_CASES_PATH = FIXTURES_DIR / "retention_cases.jsonl"
LIVE_EXAMPLES = {
    "plugins": "32_plugins.py",
    "audit": "12_tracing_audit.py",
}


def run_recorded() -> dict:
    report = run_proposal_pipeline(BAD_CASES_PATH, RETENTION_CASES_PATH)
    if report["status"] != "awaiting_human_approval":
        raise RuntimeError(f"offline gates did not pass: {report['status']}")

    print("Recorded improvement proposal (provider-free, proposal-only)\n")
    diagnosis = report["diagnosis"]
    print(f"Root cause: {diagnosis['root_cause']}")
    print(f"Evidence: {diagnosis['evidence_case_ids']}")
    print(f"Candidate digest: {report['proposal']['candidate_digest']}")
    print("\nCandidate JSON (in memory; not installed):")
    print(json.dumps(report["proposal"], ensure_ascii=False, indent=2))

    validation = report["validation"]
    preflight = {
        result["name"]: result["passed"]
        for result in validation["protected_boundaries"]["results"]
    }
    print("\nOffline gates:")
    print(f"  boundary set:            {validation['boundary']['passed']}")
    print(f"  retention set:           {validation['retention']['passed']}")
    print(f"  protected boundaries:    {validation['protected_boundaries']['passed']}")
    print(
        "  candidate digest bound:  "
        f"{str(preflight['candidate-digest-matches']).lower()}"
    )
    print(
        "  targets allowlisted:     "
        f"{str(preflight['candidate-targets-allowlisted']).lower()}"
    )
    print(f"  final state:              {report['status']}")
    print(
        "  candidate applied:       "
        f"{str(report['application']['performed']).lower()}"
    )
    print(
        "  proof scope:             in-memory bundle + declared targets; "
        "not arbitrary external side effects"
    )

    trace = load_trace(LAB_DIR / "expected_trace.json")
    print(f"\n{render_trace(trace)}")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("recorded", "live"),
        default="recorded",
        help="recorded generates an in-memory proposal; live delegates to evidence examples",
    )
    parser.add_argument(
        "--live-example",
        choices=tuple(LIVE_EXAMPLES),
        default="plugins",
        help="canonical example selected when --mode live (default: plugins)",
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
