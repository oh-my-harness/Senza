"""Verify WorkflowEngine.run() still works after runtime v0.5.0 upgrade.

Runtime v0.5.0 introduced ``WorkflowRunRequest``. ``WorkflowEngine::run()``
internally forwards to ``run_with_request(WorkflowRunRequest::default())``
(see llm-harness-runtime engine/runner.rs). Senza's PyWorkflowEngine.run()
calls ``engine.run().await``, so the ``run_with_request`` path is exercised
on every workflow execution.

This is a smoke test: we don't actually run the workflow (that needs a real
API key). We verify the engine constructs, accepts a basic workflow dict,
and reports the correct initial state — proving the v0.5.0 runtime upgrade
did not break the construction path.
"""

import senza


def test_workflow_engine_constructs_with_basic_workflow():
    """WorkflowEngine constructs and reports idle state before run()."""
    provider = senza.providers.openai(api_key="sk-test")

    workflow = {
        "entry_step": "step1",
        "steps": [
            {"id": "step1", "name": "Test", "prompt": "Say hello.", "allowed_tools": []},
        ],
        "edges": [],
    }

    def judge(ctx):
        return "done"

    engine = senza.WorkflowEngine(
        workflow, provider, "gpt-4o", senza.create_judge(judge)
    ).with_max_tokens(64)

    # Don't actually run (needs API key) — just verify construction + state.
    assert engine is not None
    # Initial status is WorkflowStatus::Idle → "idle" (not "pending";
    # Senza has no Pending variant in WorkflowStatus).
    assert engine.state() == "idle"
    # task_id is assigned at construction time (format: task-<uuid>).
    assert engine.task_id().startswith("task-")


def test_workflow_engine_accepts_rich_workflow_dict():
    """A workflow dict with edges and multiple steps is accepted."""
    provider = senza.providers.openai(api_key="sk-test")

    workflow = {
        "entry_step": "step1",
        "steps": [
            {"id": "step1", "name": "First", "prompt": "Do thing one.", "allowed_tools": []},
            {"id": "step2", "name": "Second", "prompt": "Do thing two.", "allowed_tools": []},
        ],
        "edges": [{"from": "step1", "to": "step2"}],
    }

    def judge(ctx):
        return "done"

    engine = senza.WorkflowEngine(workflow, provider, "gpt-4o", senza.create_judge(judge))

    assert engine is not None
    assert engine.state() == "idle"


def test_workflow_engine_invalid_dict_raises():
    """An invalid workflow dict (missing entry_step) raises ValueError."""
    provider = senza.providers.openai(api_key="sk-test")

    workflow = {
        # entry_step intentionally omitted
        "steps": [],
        "edges": [],
    }

    def judge(ctx):
        return "done"

    import pytest

    with pytest.raises((ValueError, KeyError, RuntimeError)):
        senza.WorkflowEngine(workflow, provider, "gpt-4o", senza.create_judge(judge))
