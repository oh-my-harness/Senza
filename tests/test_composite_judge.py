"""Tests for CompositeJudge — per-step routing handler dispatch."""

import senza


def test_composite_judge_creation():
    judge = senza.create_composite_judge()
    assert judge is not None
    assert "CompositeJudge" in repr(judge)
    assert "handlers=0" in repr(judge)


def test_composite_judge_on_registers_handler():
    judge = senza.create_composite_judge()
    judge.on("step1", lambda ctx: "to:step2")
    assert "handlers=1" in repr(judge)


def test_composite_judge_fallback():
    judge = senza.create_composite_judge()
    judge.fallback(lambda ctx: "abort:done")
    # No exception means success


def test_composite_judge_accepted_by_workflow_engine():
    """WorkflowEngine.__new__ should accept CompositeJudge as judge param."""
    provider = senza.create_openai_provider(api_key="sk-test")

    workflow = {
        "entry_step": "s1",
        "steps": [
            {"id": "s1", "name": "Step 1", "prompt": "do 1", "allowed_tools": []},
            {"id": "s2", "name": "Step 2", "prompt": "do 2", "allowed_tools": []},
        ],
        "edges": [{"from": "s1", "to": "s2"}],
    }

    judge = senza.create_composite_judge()
    judge.on("s1", lambda ctx: "to:s2")
    judge.on("s2", lambda ctx: "abort:done")

    engine = senza.WorkflowEngine(workflow, provider, "gpt-4o", judge)
    assert engine is not None
    assert "WorkflowEngine" in repr(engine)


def test_composite_judge_with_edge_fallback():
    """Steps without .on() handler should fall back to declarative Expr edges."""
    provider = senza.create_openai_provider(api_key="sk-test")

    workflow = {
        "entry_step": "custom",
        "steps": [
            {"id": "custom", "name": "Custom", "prompt": "do", "allowed_tools": []},
            {"id": "auto", "name": "Auto", "prompt": "do", "allowed_tools": []},
            {"id": "done", "name": "Done", "prompt": "do", "allowed_tools": []},
        ],
        "edges": [
            {"from": "custom", "to": "auto"},
            {
                "from": "auto",
                "to": "done",
                "condition": {"op": "eq", "pointer": "/status", "value": "ok"},
            },
            {
                "from": "auto",
                "to": "custom",
                "condition": {"op": "ne", "pointer": "/status", "value": "ok"},
            },
        ],
    }

    judge = senza.create_composite_judge()
    # Only register handler for "custom"; "auto" should use Expr edges
    judge.on("custom", lambda ctx: "to:auto")

    engine = senza.WorkflowEngine(workflow, provider, "gpt-4o", judge)
    assert engine is not None


def test_mixed_judge_and_composite_judge():
    """Both create_judge and create_composite_judge should work with WorkflowEngine."""
    provider = senza.create_openai_provider(api_key="sk-test")

    workflow = {
        "entry_step": "s1",
        "steps": [
            {"id": "s1", "name": "S1", "prompt": "do", "allowed_tools": []},
        ],
        "edges": [],
    }

    # Regular judge
    j1 = senza.create_judge(lambda ctx: "abort:done")
    e1 = senza.WorkflowEngine(workflow, provider, "gpt-4o", j1)
    assert e1 is not None

    # Composite judge
    j2 = senza.create_composite_judge()
    j2.on("s1", lambda ctx: "abort:done")
    e2 = senza.WorkflowEngine(workflow, provider, "gpt-4o", j2)
    assert e2 is not None
