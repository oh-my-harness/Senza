from pathlib import Path

from academy.common import load_trace

from .coding_scenario import evaluate_command, run_scenario


LAB_DIR = Path(__file__).resolve().parent


def test_fixture_reproduces_then_fixes_the_bug():
    result = run_scenario()
    assert result["before_returncode"] != 0
    assert result["after_returncode"] == 0
    assert result["changed_line"] == "return left - right  ->  return left + right"


def test_dangerous_command_is_denied_without_execution():
    result = evaluate_command("rm   -rf   /")
    assert result["action"] == "deny"
    assert result["executed"] is False


def test_trace_states_the_sandbox_boundary():
    trace = load_trace(LAB_DIR / "expected_trace.json")
    assert any("不是强 OS 沙箱" in boundary for boundary in trace["boundaries"])
