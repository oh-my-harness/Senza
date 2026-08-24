from pathlib import Path

import pytest

from academy.common import load_trace

from .workflow_scenario import (
    approve_and_publish,
    create_paused_checkpoint,
    load_checkpoint,
    restore_from_step,
)


LAB_DIR = Path(__file__).resolve().parent


def test_checkpoint_pauses_before_publish(tmp_path):
    checkpoint = tmp_path / "task.json"
    state = create_paused_checkpoint(checkpoint)
    assert checkpoint.is_file()
    assert state["status"] == "paused"
    assert state["current_step"] == "approve"
    assert all(entry["step"] != "publish" for entry in state["history"])


def test_restore_from_check_replays_check_and_invalidates_downstream(tmp_path):
    checkpoint = tmp_path / "task.json"
    create_paused_checkpoint(checkpoint)
    state = restore_from_step(checkpoint, "check")
    assert state["history"][0] == {"step": "draft", "attempt": 1, "state": "completed"}
    assert state["history"][1] == {"step": "check", "attempt": 2, "state": "completed"}
    assert state["history"][-1] == {"step": "approve", "attempt": 2, "state": "paused"}


def test_publish_requires_explicit_approval(tmp_path):
    checkpoint = tmp_path / "task.json"
    create_paused_checkpoint(checkpoint)
    state = approve_and_publish(checkpoint, reviewer="alice")
    assert state["status"] == "succeeded"
    assert state["history"][-1]["step"] == "publish"
    assert load_checkpoint(checkpoint)["context"]["approval"]["reviewer"] == "alice"


def test_completed_workflow_cannot_be_approved_twice(tmp_path):
    checkpoint = tmp_path / "task.json"
    create_paused_checkpoint(checkpoint)
    approve_and_publish(checkpoint, reviewer="alice")
    with pytest.raises(RuntimeError, match="not waiting for approval"):
        approve_and_publish(checkpoint, reviewer="bob")


def test_trace_documents_step_boundary_limitation():
    trace = load_trace(LAB_DIR / "expected_trace.json")
    assert any("Provider 请求" in boundary for boundary in trace["boundaries"])
