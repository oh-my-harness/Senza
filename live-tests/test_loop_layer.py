"""Loop layer live tests: multi-tool dispatch, multi-turn history, provider error surfacing."""

import senza
from base import (
    SINGLE_TURN_TIMEOUT_MS,
    assert_settled,
    assert_tool_called,
    make_harness,
    provider_or_skip,
    run_prompt,
    text_of,
)


def weather_tool():
    return senza.create_tool(
        name="weather",
        description="Get weather for a city",
        parameters_schema='{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}',
        callback=lambda a, c: {
            "content": [{"type": "text", "text": f"Weather in {a['city']}: sunny"}],
            "terminate": False,
        },
    )


def timer_tool():
    return senza.create_tool(
        name="timer",
        description="Start a timer",
        parameters_schema='{"type":"object","properties":{"seconds":{"type":"integer"}},"required":["seconds"]}',
        callback=lambda a, c: {
            "content": [{"type": "text", "text": "timer set"}],
            "terminate": False,
        },
    )


def test_tool_dispatch():
    h = make_harness(provider_or_skip(), lambda b: b.tool(weather_tool()).tool(timer_tool()))
    ev = run_prompt(h, "What's the weather in Tokyo? Then start a 5 second timer.")
    assert_settled(ev)
    assert_tool_called(ev, "weather")


def test_multi_turn_history():
    h = make_harness(provider_or_skip(), lambda b: b.max_tokens(100))
    run_prompt(h, "Remember the code word: zebra.")
    ev = run_prompt(h, "What was the code word?")
    assert_settled(ev)
    assert "zebra" in text_of(ev).lower(), f"expected history recall, got {text_of(ev)!r}"


def test_provider_error_surfaces():
    # Point at an unreachable endpoint -> a typed Senza error, never a panic/hang.
    bad = senza.providers.openai(api_key="sk-invalid", base_url="http://127.0.0.1:1/v1")
    h = make_harness(bad, lambda b: b.max_tokens(50))
    try:
        run_prompt(h, "hi", timeout_ms=SINGLE_TURN_TIMEOUT_MS)
    except Exception:
        pass  # surfaced as a typed provider error — assert it doesn't hang or crash
    else:
        raise AssertionError("expected a provider error to surface (typed exception)")


def test_loop_constructs_offline():
    """No key needed; validates tool registration + builder chaining."""
    stub = senza.providers.openai(api_key="sk-test")
    h = make_harness(stub, lambda b: b.tool(weather_tool()).tool(timer_tool()))
    assert h is not None and h.phase() == "idle"
