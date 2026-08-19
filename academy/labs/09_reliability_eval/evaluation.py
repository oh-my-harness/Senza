"""Small, deterministic evaluation runner for Academy teaching purposes."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Dict, Iterable, List, Tuple, Union


JsonObject = Dict[str, Any]


def load_jsonl(path: Union[str, Path]) -> List[JsonObject]:
    records = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            records.append(value)
    return records


def verify_run(case: JsonObject, run: JsonObject) -> Tuple[bool, List[str]]:
    """Apply deterministic outcome, safety, and budget checks."""

    output = str(run.get("output", ""))
    reasons = []
    for required in case["required_substrings"]:
        if required.lower() not in output.lower():
            reasons.append(f"missing required substring: {required}")
    for forbidden in case["forbidden_substrings"]:
        if forbidden.lower() in output.lower():
            reasons.append(f"contains forbidden substring: {forbidden}")

    expected_executed = case.get("expected_executed")
    if expected_executed is not None and run.get("executed") is not expected_executed:
        reasons.append(
            f"executed={run.get('executed')!r}, expected {expected_executed!r}"
        )
    if float(run["cost_usd"]) > float(case["max_cost_usd"]):
        reasons.append("cost exceeds case budget")
    return not reasons, reasons


def evaluate(
    cases: Iterable[JsonObject], runs: Iterable[JsonObject], k: int = 3
) -> JsonObject:
    """Evaluate repeated recorded runs for each Model+Harness variant."""

    if k <= 0:
        raise ValueError("k must be positive")
    case_map = {case["id"]: case for case in cases}
    if not case_map:
        raise ValueError("at least one case is required")

    verified_by_variant = defaultdict(list)
    verified_by_variant_case = defaultdict(list)
    for run in runs:
        case_id = run.get("case_id")
        if case_id not in case_map:
            raise ValueError(f"run references unknown case: {case_id!r}")
        passed, reasons = verify_run(case_map[case_id], run)
        variant = str(run["variant"])
        verified_run = {**run, "passed": passed, "reasons": reasons}
        verified_by_variant[variant].append(verified_run)
        verified_by_variant_case[(variant, case_id)].append(verified_run)
    if not verified_by_variant:
        raise ValueError("at least one run is required")

    variants = {}
    for name, verified in sorted(verified_by_variant.items()):
        total = len(verified)
        passed = sum(1 for item in verified if item["passed"])
        overall_pass_rate = passed / total
        per_case = {}
        case_pass_at_k = []
        case_pass_power_k = []
        for case_id in sorted(case_map):
            selected = verified_by_variant_case[(name, case_id)]
            if not selected:
                raise ValueError(f"variant {name!r} has no runs for case {case_id!r}")
            case_passed = sum(1 for item in selected if item["passed"])
            empirical_pass_rate = case_passed / len(selected)
            estimated_pass_at_k = 1 - (1 - empirical_pass_rate) ** k
            estimated_pass_power_k = empirical_pass_rate**k
            case_pass_at_k.append(estimated_pass_at_k)
            case_pass_power_k.append(estimated_pass_power_k)
            per_case[case_id] = {
                "passed": case_passed,
                "total": len(selected),
                "empirical_pass_rate": round(empirical_pass_rate, 6),
                "estimated_pass_at_k": round(estimated_pass_at_k, 6),
                "estimated_pass_power_k": round(estimated_pass_power_k, 6),
            }
        variants[name] = {
            "runs": total,
            "passed": passed,
            "overall_pass_rate": round(overall_pass_rate, 6),
            "macro_avg_estimated_pass_at_k": round(fmean(case_pass_at_k), 6),
            "macro_avg_estimated_pass_power_k": round(fmean(case_pass_power_k), 6),
            "overall_avg_latency_ms": round(
                fmean(float(item["latency_ms"]) for item in verified), 2
            ),
            "overall_avg_cost_usd": round(
                fmean(float(item["cost_usd"]) for item in verified), 6
            ),
            "total_input_tokens": sum(int(item["input_tokens"]) for item in verified),
            "total_output_tokens": sum(int(item["output_tokens"]) for item in verified),
            "per_case": per_case,
        }

    recommended = max(
        variants,
        key=lambda name: (
            variants[name]["macro_avg_estimated_pass_power_k"],
            variants[name]["overall_pass_rate"],
            -variants[name]["overall_avg_cost_usd"],
        ),
    )
    return {
        "schema_version": 1,
        "k": k,
        "case_count": len(case_map),
        "variants": variants,
        "recommendation": {
            "variant": recommended,
            "criterion": "highest macro-average estimated Pass^k, then overall pass rate, then lower average cost",
        },
        "limitations": [
            "Recorded outcomes test the runner, not a live model.",
            "Each case's Pass@k and Pass^k use empirical p from only three repeated runs; macro averages weight cases equally.",
            "Audit, usage, and budget are inputs to evaluation; they are not a complete eval platform.",
        ],
    }


def render_markdown(report: JsonObject) -> str:
    lines = [
        "# Senza Academy reliability report",
        "",
        f"Cases: {report['case_count']} | k: {report['k']}",
        "",
        "| Variant | Passed | Overall pass rate | Macro avg estimated Pass@k | Macro avg estimated Pass^k | Overall avg latency | Overall avg cost |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, metrics in report["variants"].items():
        lines.append(
            f"| {name} | {metrics['passed']}/{metrics['runs']} | "
            f"{metrics['overall_pass_rate']:.3f} | "
            f"{metrics['macro_avg_estimated_pass_at_k']:.3f} | "
            f"{metrics['macro_avg_estimated_pass_power_k']:.3f} | "
            f"{metrics['overall_avg_latency_ms']:.2f} ms | "
            f"${metrics['overall_avg_cost_usd']:.6f} |"
        )
    lines.extend(
        [
            "",
            f"Recommendation: **{report['recommendation']['variant']}** — "
            f"{report['recommendation']['criterion']}.",
            "",
            "Limitations",
        ]
    )
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines)
