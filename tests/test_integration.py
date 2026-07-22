"""Integration test: full SDK flow."""

import json

import senza


def test_workflow_engine_full_construction():
    """End-to-end: build engine, add tools/hooks/executor, verify wiring."""
    provider = senza.create_openai_provider(api_key="test-key")
    workflow = {
        "entry_step": "run",
        "steps": [{"id": "run", "name": "Run", "prompt": "Call echo", "allowed_tools": ["echo"]}],
        "edges": [],
    }
    judge = senza.create_judge(lambda ctx: "abort:done")
    engine = senza.WorkflowEngine(workflow, provider, "gpt-4o", judge)

    tool = senza.create_tool(
        "echo",
        "Echo",
        json.dumps({"type": "object", "properties": {}}),
        lambda args, ctx: {"content": [], "terminate": False},
    )
    engine.with_tool(tool)

    executor = senza.create_executor(lambda ctx: {"output": "done"})
    engine.with_executor("my_exec", executor)

    assert engine.task_id().startswith("task-")
    it = engine.subscribe()
    assert it is not None


def test_harness_full_build():
    provider = senza.create_openai_provider(api_key="test-key")
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .system_prompt("You are helpful.")
        .max_tokens(1024)
        .build()
    )
    assert hasattr(harness, "prompt")
    assert hasattr(harness, "events")


def test_event_channel_for_human_in_loop():
    handle, tool = senza.create_event_channel("task-123")
    assert tool.name() == "wait_for_external_event"
    handle.submit("approved", {"passed": True, "feedback": "good"})
