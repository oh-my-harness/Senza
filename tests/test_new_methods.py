"""Tests for newly exposed WorkflowEngine and AgentHarness methods."""

import tempfile

import pytest
import senza

# ── WorkflowEngine new methods ──────────────────────────────────────────────


def _make_workflow():
    return {
        "entry_step": "step1",
        "steps": [{"id": "step1", "name": "Step 1", "prompt": "Do something", "allowed_tools": []}],
        "edges": [],
    }


def _make_provider():
    return senza.create_openai_provider(api_key="test-key")


def _make_judge():
    return senza.create_judge(lambda ctx: "abort:done")


def test_workflow_engine_state():
    """state() returns 'idle' before run."""
    engine = senza.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    assert engine.state() == "idle"


def test_workflow_engine_current_step():
    """current_step() returns the entry step before run."""
    engine = senza.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    assert engine.current_step() == "step1"


def test_workflow_engine_step_history_empty():
    """step_history() returns empty list before run."""
    engine = senza.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    assert engine.step_history() == []


def test_workflow_engine_total_cost_zero():
    """total_cost() returns zero-cost dict before run."""
    engine = senza.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    cost = engine.total_cost()
    assert cost["total_input_tokens"] == 0
    assert cost["total_output_tokens"] == 0
    assert cost["total_cost"] == 0.0
    assert isinstance(cost["by_model"], dict)


def test_workflow_engine_pause_and_cancel():
    """pause() and cancel() can be called without error (even pre-run)."""
    engine = senza.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    engine.pause("testing")
    # cancel changes state to Cancelled
    engine.cancel("done")
    assert engine.state() == "cancelled"


def test_workflow_engine_checkpoint():
    """checkpoint() stores arbitrary JSON payload."""
    engine = senza.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    engine.checkpoint("phase 1 done", {"progress": 50, "status": "ok"})


def test_workflow_engine_with_task_store():
    """with_task_store() chains and returns self."""
    with tempfile.TemporaryDirectory() as d:
        engine = senza.WorkflowEngine(
            _make_workflow(), _make_provider(), "gpt-4o", _make_judge()
        ).with_task_store(d)
        assert engine is not None
        assert engine.task_id().startswith("task-")


def test_workflow_engine_with_max_steps_and_retries():
    """with_max_steps() and with_max_retries() chain correctly."""
    engine = (
        senza.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
        .with_max_steps(50)
        .with_max_retries(3)
    )
    assert engine.task_id().startswith("task-")


def test_workflow_engine_restore_classmethod():
    """restore() is accessible as a classmethod."""
    assert hasattr(senza.WorkflowEngine, "restore")
    # Calling restore on a non-existent task should raise KeyError
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(KeyError, match="workflow not found"):
            senza.WorkflowEngine.restore(
                d, "task-nonexistent", _make_provider(), "gpt-4o", _make_judge()
            )


def test_workflow_engine_restore_from_step_classmethod():
    """restore_from_step() is accessible as a classmethod."""
    assert hasattr(senza.WorkflowEngine, "restore_from_step")
    # Calling restore_from_step on a non-existent task should raise
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises((KeyError, RuntimeError)):
            senza.WorkflowEngine.restore_from_step(
                d, "task-nonexistent", "step1", _make_provider(), "gpt-4o", _make_judge()
            )


def test_workflow_engine_chained_build():
    """Full builder chain with all new methods."""
    with tempfile.TemporaryDirectory() as d:
        engine = (
            senza.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
            .with_task_store(d)
            .with_max_steps(100)
            .with_max_tokens(4096)
            .with_max_retries(5)
        )
        engine.set_context_variable("key", {"value": 42})
        engine.checkpoint("init", {"phase": "start"})
        assert engine.state() == "idle"
        assert engine.current_step() == "step1"
        assert len(engine.step_history()) == 0
        cost = engine.total_cost()
        assert cost["total_input_tokens"] == 0


# ── AgentHarness new methods ────────────────────────────────────────────────


def _make_harness():
    provider = senza.create_openai_provider(api_key="test-key")
    return (
        senza.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .system_prompt("You are helpful.")
        .build()
    )


def test_harness_usage():
    """usage() returns a cost dict."""
    harness = _make_harness()
    cost = harness.usage()
    assert cost["total_input_tokens"] == 0
    assert cost["total_output_tokens"] == 0
    assert isinstance(cost["by_model"], dict)


def test_harness_reset_usage():
    """reset_usage() can be called without error."""
    harness = _make_harness()
    harness.reset_usage()


def test_harness_set_system_prompt():
    """set_system_prompt() accepts string and None."""
    harness = _make_harness()
    harness.set_system_prompt("New prompt")
    harness.set_system_prompt(None)


def test_harness_set_max_tokens():
    """set_max_tokens() accepts an integer."""
    harness = _make_harness()
    harness.set_max_tokens(2048)


def test_harness_set_temperature():
    """set_temperature() accepts float and None."""
    harness = _make_harness()
    harness.set_temperature(0.7)
    harness.set_temperature(None)


def test_harness_set_thinking_level():
    """set_thinking_level() accepts valid level strings."""
    harness = _make_harness()
    for level in ["off", "minimal", "low", "medium", "high", "xhigh"]:
        harness.set_thinking_level(level)
    harness.set_thinking_level("budget:4096")


def test_harness_set_thinking_level_invalid():
    """set_thinking_level() raises ValueError on invalid input."""
    harness = _make_harness()
    with pytest.raises((ValueError, RuntimeError)):
        harness.set_thinking_level("invalid_level")


def test_harness_steer_and_follow_up():
    """steer() and follow_up() accept text."""
    harness = _make_harness()
    harness.steer("Please focus on X")
    harness.follow_up("Now do Y")


def test_harness_next_turn():
    """next_turn() accepts text."""
    harness = _make_harness()
    harness.next_turn("Next question")


def test_harness_set_model():
    """set_model() accepts model string with optional params."""
    harness = _make_harness()
    harness.set_model("gpt-4o-mini")
    harness.set_model("claude-3-opus", context_window=200000, max_tokens=4096)


# ── Context manager + docstrings ────────────────────────────────────────────


def test_harness_context_manager():
    """AgentHarness supports `with` statement."""
    provider = senza.create_openai_provider(api_key="test-key")
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .system_prompt("You are helpful.")
        .build()
    )
    with harness as h:
        assert h is harness
        assert h.phase() == "idle"
    # After exit, harness is still usable
    assert harness.phase() == "idle"


def test_harness_context_manager_no_suppress():
    """Context manager does not suppress exceptions."""
    provider = senza.create_openai_provider(api_key="test-key")
    harness = senza.HarnessBuilder("gpt-4o").provider("gpt-*", provider).build()
    with pytest.raises(ValueError, match="test error"):
        with harness:
            raise ValueError("test error")


def test_docstrings_present():
    """Key functions and classes have docstrings."""
    assert senza.version.__doc__ is not None
    assert senza.create_tool.__doc__ is not None
    assert senza.create_event_channel.__doc__ is not None
    assert senza.create_openai_provider.__doc__ is not None
    assert senza.WorkflowEngine.__doc__ is not None
    assert senza.WorkflowEngine.run.__doc__ is not None
    assert senza.WorkflowEngine.restore.__doc__ is not None
    assert senza.AgentHarness.__doc__ is not None
    assert senza.AgentHarness.prompt.__doc__ is not None
    assert senza.HarnessBuilder.__doc__ is not None
