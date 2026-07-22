"""Tests for async streaming API (issue #11).

Verifies stream_events(), stream_prompt(), and stream_run() produce
async generators that yield event dicts.
"""

import asyncio

import senza

# ── stream_events ────────────────────────────────────────────────────────────


def test_stream_events_is_async_generator():
    """stream_events() returns an async generator."""
    agent = senza.Agent(model="mock-model")
    gen = senza.stream_events(agent, timeout_ms=100)
    assert hasattr(gen, "__aiter__")
    assert hasattr(gen, "__anext__")


def test_stream_prompt_yields_events():
    """stream_prompt() yields events from an Agent prompt."""

    async def run():
        agent = senza.Agent(model="mock-model")
        events = []
        async for event in senza.stream_prompt(agent, "hello", timeout_ms=5000):
            events.append(event)
        assert len(events) > 0
        assert "type" in events[0]

    asyncio.run(run())


def test_stream_prompt_terminates_on_agent_end():
    """stream_prompt() stops after agent_end event."""

    async def run():
        agent = senza.Agent(model="mock-model")
        types = []
        async for event in senza.stream_prompt(agent, "hello", timeout_ms=5000):
            types.append(event.get("type"))
        assert "agent_end" in types

    asyncio.run(run())


def test_stream_events_empty_iterator():
    """stream_events() on an idle agent terminates after timeout."""

    async def run():
        agent = senza.Agent(model="mock-model")
        events = []
        async for event in senza.stream_events(agent, timeout_ms=100):
            events.append(event)
        # With max_consecutive_timeouts=1, the first timeout terminates
        assert len(events) == 0

    asyncio.run(run())


# ── stream_run ───────────────────────────────────────────────────────────────


def test_stream_run_yields_workflow_events():
    """stream_run() yields events from a WorkflowEngine with an executor."""

    async def run():
        workflow = {
            "entry_step": "step1",
            "steps": [
                {"id": "step1", "name": "S", "executor": "my_exec"},
            ],
            "edges": [],
        }
        provider = senza.create_openai_provider(api_key="test-key")
        judge = senza.create_judge(lambda ctx: "abort:done")

        def my_executor(ctx):
            return {"output": "done"}

        engine = senza.WorkflowEngine(workflow, provider, "gpt-4o", judge)
        engine.with_executor("my_exec", senza.create_executor(my_executor))

        events = []
        async for event in senza.stream_run(engine, timeout_ms=10000):
            events.append(event)
        assert len(events) > 0

    asyncio.run(run())


# ── Type hints ───────────────────────────────────────────────────────────────


def test_stream_functions_have_signatures():
    """stream_* functions are introspectable (for .pyi stub verification)."""
    import inspect

    sig = inspect.signature(senza.stream_events)
    assert "obj" in sig.parameters
    assert "timeout_ms" in sig.parameters

    sig = inspect.signature(senza.stream_prompt)
    assert "text" in sig.parameters

    sig = inspect.signature(senza.stream_run)
    assert "engine" in sig.parameters
