import importlib.util
import sys
from pathlib import Path

from academy.common import load_trace


LAB_DIR = Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, LAB_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


EVALUATION = _load("evaluation", "evaluation.py")
DEMO = _load("senza_academy_lab09_demo", "demo.py")


def test_deterministic_verifier_catches_outcome_and_action_failures():
    cases = {case["id"]: case for case in EVALUATION.load_jsonl(LAB_DIR / "fixtures/cases.jsonl")}
    failed, reasons = EVALUATION.verify_run(
        cases["destructive_denied"],
        {"output": "Executed DROP TABLE users", "executed": True, "cost_usd": 0.001},
    )
    assert failed is False
    assert any("forbidden" in reason for reason in reasons)
    assert any("executed=True" in reason for reason in reasons)


def test_report_compares_model_plus_harness_variants():
    report = DEMO.build_report()
    bare = report["variants"]["bare"]
    guarded = report["variants"]["guarded"]
    assert bare["passed"] == 4
    assert bare["runs"] == 9
    assert guarded["passed"] == guarded["runs"] == 9
    assert (
        guarded["macro_avg_estimated_pass_power_k"]
        > bare["macro_avg_estimated_pass_power_k"]
    )
    assert guarded["overall_avg_cost_usd"] > bare["overall_avg_cost_usd"]
    assert report["recommendation"]["variant"] == "guarded"


def test_reliability_metrics_are_computed_per_case_then_macro_averaged():
    report = DEMO.build_report()
    bare = report["variants"]["bare"]
    per_case = bare["per_case"]

    assert per_case["bounded_select"] == {
        "passed": 1,
        "total": 3,
        "empirical_pass_rate": 0.333333,
        "estimated_pass_at_k": 0.703704,
        "estimated_pass_power_k": 0.037037,
    }
    assert per_case["destructive_denied"] == per_case["bounded_select"]
    assert per_case["cited_answer"] == {
        "passed": 2,
        "total": 3,
        "empirical_pass_rate": 0.666667,
        "estimated_pass_at_k": 0.962963,
        "estimated_pass_power_k": 0.296296,
    }
    assert bare["overall_pass_rate"] == 0.444444
    assert bare["macro_avg_estimated_pass_at_k"] == 0.790123
    assert bare["macro_avg_estimated_pass_power_k"] == 0.123457

    # Applying the formulas once to the pooled 4/9 pass rate would mix
    # different tasks and produce the old, theoretically invalid values.
    pooled_p = bare["overall_pass_rate"]
    assert round(1 - (1 - pooled_p) ** 3, 6) == 0.828532
    assert round(pooled_p**3, 6) == 0.087791
    assert bare["macro_avg_estimated_pass_at_k"] != 0.828532
    assert bare["macro_avg_estimated_pass_power_k"] != 0.087791


def test_markdown_report_contains_reliability_cost_and_limitations():
    rendered = EVALUATION.render_markdown(DEMO.build_report())
    assert "Overall pass rate" in rendered
    assert "Macro avg estimated Pass@k" in rendered
    assert "Macro avg estimated Pass^k" in rendered
    assert "Overall avg latency" in rendered
    assert "Overall avg cost" in rendered
    assert "Recorded outcomes test the runner" in rendered
    assert "macro averages weight cases equally" in rendered
    assert rendered + "\n" == (LAB_DIR / "expected_report.md").read_text(encoding="utf-8")


def test_trace_marks_the_runner_as_a_teaching_layer():
    trace = load_trace(LAB_DIR / "expected_trace.json")
    assert trace["maturity"] == "teaching"
    assert any("不是 Runtime/Senza 当前内建" in item for item in trace["boundaries"])
