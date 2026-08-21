from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = LAB_ROOT.parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from academy.common import load_trace
from state_model import (
    MAIN_SIDE_TOOLS,
    RUNTIME_CHILD_SIDE_TOOLS,
    SENZA_CHILD_PLUGIN,
    SENZA_DEFAULT_CHILD_TOOLS,
    CoordinatorModel,
    run_recorded_scenario,
)


def _load_demo():
    spec = importlib.util.spec_from_file_location("academy_lab_08_demo", LAB_ROOT / "demo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recorded_scenario_reaches_one_done_and_one_aborted_terminal_state():
    scenario = run_recorded_scenario()
    snapshots = {
        item["agent_id"]: item for item in scenario.coordinator.query_subagent()
    }
    assert snapshots[scenario.completed_agent]["status"] == "done"
    assert snapshots[scenario.aborted_agent]["status"] == "aborted"
    assert scenario.coordinator.await_subagent_reply(scenario.aborted_agent)["result"] is None


def test_child_contexts_are_explicit_and_isolated():
    scenario = run_recorded_scenario()
    coordinator = scenario.coordinator
    first = coordinator.children[scenario.completed_agent]
    second = coordinator.children[scenario.aborted_agent]

    private_main_note = "private-main-note: leadership prefers option B"
    assert private_main_note in coordinator.main_context
    assert private_main_note not in first.context_view
    assert private_main_note not in second.context_view
    assert "Also state one measurable rollback signal." in first.context_view
    assert "Also state one measurable rollback signal." not in second.context_view
    assert first.injected_context != second.injected_context


def test_tool_catalog_distinguishes_runtime_protocol_from_senza_default_child():
    trace = load_trace(LAB_ROOT / "expected_trace.json")
    surface = trace["tool_surface"]
    assert tuple(surface["main_side"]) == MAIN_SIDE_TOOLS
    assert tuple(surface["runtime_child_side"]) == RUNTIME_CHILD_SIDE_TOOLS
    assert surface["senza_child_plugin"] == SENZA_CHILD_PLUGIN == "NoopPlugin"
    assert tuple(surface["senza_default_child_tools"]) == SENZA_DEFAULT_CHILD_TOOLS == ()


def test_role_is_snapshot_metadata_not_a_state_machine_input():
    coordinator = CoordinatorModel(("main-private",))
    first = coordinator.spawn_agent("same task", role="label-a")
    second = coordinator.spawn_agent("same task", role="label-b")
    assert coordinator.children[first].context_view == coordinator.children[second].context_view
    assert coordinator.query_subagent(first)["role"] == "label-a"
    coordinator.complete(first, "same result")
    coordinator.complete(second, "same result")
    assert coordinator.query_subagent(first)["status"] == "done"
    assert coordinator.query_subagent(second)["status"] == "done"


def test_recorded_events_cover_all_five_main_lifecycle_tools():
    scenario = run_recorded_scenario()
    lifecycles = {event["lifecycle"] for event in scenario.events}
    assert set(MAIN_SIDE_TOOLS) <= lifecycles
    trace = load_trace(LAB_ROOT / "expected_trace.json")
    assert trace["maturity"] == "teaching"
    assert scenario.events == trace["events"]


def test_demo_defaults_to_recorded_mode(capsys):
    demo = _load_demo()
    assert demo.main([]) == 0
    output = capsys.readouterr().out
    assert "Basic Multi-Agent" in output
    assert "sub-1: done" in output
    assert "sub-2: aborted" in output


def test_live_mode_delegates_to_the_canonical_example(monkeypatch):
    demo = _load_demo()
    delegated: list[str] = []
    monkeypatch.setattr(demo, "run_live_example", delegated.append)
    assert demo.main(["--mode", "live"]) == 0
    assert delegated == ["11_spawn_subagent.py"]
