import importlib.util
import sys
from pathlib import Path

from academy.common import load_trace


LAB_DIR = Path(__file__).resolve().parent


def _load_demo():
    name = "senza_academy_lab03_demo"
    spec = importlib.util.spec_from_file_location(name, LAB_DIR / "demo.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


DEMO = _load_demo()


def test_guard_returns_current_allow_modify_deny_shapes():
    allow = DEMO.db_guard("run_query", {"sql": "SELECT id FROM users LIMIT 5"})
    modify = DEMO.db_guard("run_query", {"sql": "SELECT id FROM users"})
    deny = DEMO.db_guard("run_query", {"sql": "DROP TABLE users"})

    assert allow == "allow"
    assert modify == {
        "action": "modify",
        "args": {"sql": "SELECT id FROM users LIMIT 100"},
    }
    assert deny["action"] == "deny"
    assert deny["result"]["details"]["reason"] == "non_read_only_sql"


def test_recorded_runner_calls_guard_and_never_executes_denied_sql():
    records, executed_queries = DEMO.execute_recorded_scenarios()

    assert [record["action"] for record in records] == ["allow", "modify", "deny"]
    assert executed_queries == [
        "SELECT id, email FROM users LIMIT 5",
        "SELECT id, email FROM users LIMIT 100",
    ]
    assert records[-1]["effective_sql"] is None
    assert records[-1]["executed"] is False


def test_trace_matches_the_recorded_policy_and_common_contract():
    trace = load_trace(LAB_DIR / "expected_trace.json")
    statuses = [event["status"] for event in trace["events"]]

    assert trace["lab"] == "03"
    assert trace["maturity"] == "stable"
    assert "accepted" in statuses
    assert "modified" in statuses
    assert "denied" in statuses
    assert trace["live_examples"] == ["32_plugins.py"]


def test_readme_keeps_plugin_scope_and_capability_boundaries_explicit():
    readme = (LAB_DIR / "README.md").read_text(encoding="utf-8")
    normalized = " ".join(readme.split())

    assert "构建期" in readme
    assert "HarnessBuilder.plugin" in readme
    assert "WorkflowEngine.with_step_plugin" in readme
    assert "Python `create_plugin()` 当前只开放 **tools 和 hooks**" in normalized
    assert "构建时报错" in readme
    assert "运行时热插拔" in readme
