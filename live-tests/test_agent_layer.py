"""Agent layer live tests: basic / async streaming / tool / hooks / config / skills / branch / compaction."""

import asyncio

import senza
from base import (
    assert_no_error,
    assert_settled,
    assert_tool_called,
    event_types,
    live_model,
    make_harness,
    provider_or_skip,
    run_prompt,
    text_of,
)


def echo_tool():
    return senza.create_tool(
        name="echo",
        description="Echo a message back verbatim",
        parameters_schema='{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}',
        callback=lambda args, ctx: {
            "content": [{"type": "text", "text": args["text"]}],
            "terminate": False,
        },
    )


def test_basic_prompt():
    h = make_harness(provider_or_skip())
    ev = run_prompt(h, "Reply with the single word: hello")
    assert_settled(ev)
    assert_no_error(ev)
    assert text_of(ev).strip(), "expected non-empty reply"


def test_async_streaming():
    h = make_harness(provider_or_skip())

    async def run():
        return [e async for e in senza.stream_prompt(h, "Count 1 2 3.")]

    ev = asyncio.run(run())
    assert "text_delta" in event_types(ev) or text_of(ev), "expected streamed text"


def test_tool_calling():
    h = make_harness(provider_or_skip(), lambda b: b.tool(echo_tool()))
    ev = run_prompt(h, "Call the echo tool with text 'ping' and report its reply.")
    assert_settled(ev)
    assert_tool_called(ev, "echo")


def test_hooks_fire():
    calls = []

    def before_turn(ctx):
        calls.append("before_turn")

    h = make_harness(provider_or_skip(), lambda b: b.hooks([senza.hooks.before_turn(before_turn)]))
    ev = run_prompt(h, "Say hi.")
    assert "before_turn" in calls, f"expected before_turn hook to fire, got {calls}"
    assert_settled(ev)


def test_dynamic_config():
    h = make_harness(provider_or_skip(), lambda b: b.max_tokens(100))
    h.set_system_prompt("You are terse. Reply with one word only.")
    ev = run_prompt(h, "What is 2+2?")
    assert_settled(ev)


def test_skills_model_switch():
    h = make_harness(provider_or_skip(), lambda b: b.max_tokens(100))
    h.set_model("alternate-name")  # accepted as a string (no provider request yet)
    h.set_model(live_model())  # switch back to the real model, then run a real turn
    ev = run_prompt(h, "Say ok.")
    assert_settled(ev)


def test_session_branch():
    h = make_harness(provider_or_skip())
    run_prompt(h, "Say hello.")
    path = h.read_active_path()
    assert path, "expected at least one session entry"
    head = path[-1]["id"]
    leaf = h.fork_branch(from_entry=head, label="branch-a")
    assert leaf, "expected a branch id"
    h.navigate_tree(leaf)
    ev = run_prompt(h, "Continue.")
    assert_settled(ev)


def test_compaction_turns():
    h = make_harness(
        provider_or_skip(),
        lambda b: (
            b.model_info(context_window=800, max_tokens=256)
            .compaction_reserve_tokens(50)
            .compaction_keep_recent_tokens(100)
        ),
    )
    for _ in range(5):
        ev = run_prompt(h, "Write three full sentences about programming.")
        assert_no_error(ev)
        assert_settled(ev)


def test_agent_constructs_offline():
    """No key needed; validates every agent-layer API signature."""
    stub = senza.providers.openai(api_key="sk-test")
    h = make_harness(stub, lambda b: b.tool(echo_tool()).hooks([]).max_tokens(100).temperature(0.0))
    assert h is not None and h.phase() == "idle"
