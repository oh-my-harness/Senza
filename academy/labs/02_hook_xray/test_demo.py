from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = LAB_ROOT.parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from academy.common import load_trace


EXPECTED_HOOKS = {
    "before_run",
    "before_turn",
    "after_turn",
    "before_tool_call",
    "after_tool_call",
    "transform_context",
    "prepare_next_turn",
    "should_stop",
    "before_provider_request",
    "after_provider_response",
    "final_answer_validator",
    "before_compact",
}


def _load_demo():
    spec = importlib.util.spec_from_file_location("academy_lab_02_demo", LAB_ROOT / "demo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recorded_atlas_names_every_fixed_hook_once():
    trace = load_trace(LAB_ROOT / "expected_trace.json")
    lifecycle = [event["lifecycle"] for event in trace["events"]]
    assert len(lifecycle) == 12
    assert set(lifecycle) == EXPECTED_HOOKS
    assert set(trace["composition"]) == EXPECTED_HOOKS


def test_recorded_atlas_preserves_distinct_composition_semantics():
    trace = load_trace(LAB_ROOT / "expected_trace.json")
    composition = trace["composition"]
    assert "short-circuits" in composition["before_tool_call"]
    assert "prior transformed context" in composition["transform_context"]
    assert "any true" in composition["should_stop"]
    assert "first rejection" in composition["final_answer_validator"]
    assert any("教学图谱" in boundary for boundary in trace["boundaries"])


def test_demo_defaults_to_recorded_mode(capsys):
    demo = _load_demo()
    assert demo.main([]) == 0
    output = capsys.readouterr().out
    assert "12 个固定生命周期边界" in output
    assert "before_provider_request" in output
    assert "final_answer_validator" in output


def test_live_mode_delegates_without_claiming_full_hook_coverage(monkeypatch):
    demo = _load_demo()
    delegated: list[str] = []
    monkeypatch.setattr(demo, "run_live_example", delegated.append)
    assert demo.main(["--mode", "live"]) == 0
    assert delegated == ["07_hooks.py"]
