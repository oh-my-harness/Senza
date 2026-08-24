from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = LAB_ROOT.parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from academy.common import load_trace


def _load_demo():
    spec = importlib.util.spec_from_file_location("academy_lab_01_demo", LAB_ROOT / "demo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recorded_trace_preserves_the_react_causal_chain():
    trace = load_trace(LAB_ROOT / "expected_trace.json")
    assert trace["maturity"] == "stable"
    assert [event["kind"] for event in trace["events"]] == [
        "user",
        "model",
        "tool",
        "tool",
        "model",
        "agent",
    ]
    assert "tool call" in trace["events"][1]["lifecycle"]
    assert "tool result" in trace["events"][3]["lifecycle"]
    assert "settled" in trace["events"][-1]["summary"]


def test_demo_defaults_to_recorded_mode(capsys):
    demo = _load_demo()
    assert demo.main([]) == 0
    output = capsys.readouterr().out
    assert "ReAct 与 Tool Calling" in output
    assert "Timeline" in output
    assert "02_tool_calling.py" in output


def test_live_mode_delegates_to_the_canonical_example(monkeypatch):
    demo = _load_demo()
    delegated: list[str] = []
    monkeypatch.setattr(demo, "run_live_example", delegated.append)
    assert demo.main(["--mode", "live"]) == 0
    assert delegated == ["02_tool_calling.py"]
