"""Tests for Transition::Pause — judge-initiated pause (issue #42)."""

import pytest
import senza


def _make_provider():
    return senza.create_openai_provider(api_key="test-key")


def _make_workflow():
    """Two-step workflow with an edge — not a free task, so judge is called."""
    return {
        "entry_step": "step1",
        "steps": [
            {"id": "step1", "name": "S1", "executor": "my_exec"},
            {"id": "step2", "name": "S2", "executor": "my_exec"},
        ],
        "edges": [{"from": "step1", "to": "step2"}],
    }


def _make_engine(judge_fn):
    engine = senza.WorkflowEngine(
        _make_workflow(), _make_provider(), "gpt-4o", senza.create_judge(judge_fn)
    )
    engine.with_executor("my_exec", senza.create_executor(lambda ctx: {"output": "done"}))
    return engine


def test_judge_can_return_pause():
    """A judge returning 'pause:<reason>' pauses the workflow."""
    engine = _make_engine(lambda ctx: "pause:needs human review")

    with pytest.raises(RuntimeError, match="needs human review"):
        engine.run()

    assert engine.state() == "paused"


def test_paused_engine_can_resume():
    """A paused engine can be resumed via run()."""
    call_count = [0]

    def judge_fn(ctx):
        call_count[0] += 1
        if call_count[0] == 1:
            return "pause:review needed"
        return "abort:done"

    engine = _make_engine(judge_fn)

    with pytest.raises(RuntimeError, match="review needed"):
        engine.run()
    assert engine.state() == "paused"

    # Resume — second call aborts (succeeds)
    engine.run()
    assert engine.state() == "succeeded"


def test_pause_transition_in_step_history():
    """The pause transition appears in step_history with type='pause'."""
    engine = _make_engine(lambda ctx: "pause:quality gate")

    with pytest.raises(RuntimeError):
        engine.run()

    history = engine.step_history()
    assert len(history) > 0
    last = history[-1]
    assert last["transition"]["type"] == "pause"
    assert last["transition"]["reason"] == "quality gate"
