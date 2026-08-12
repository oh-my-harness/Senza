"""Tests for EventType constants."""

import senza


def test_event_type_class_exists():
    """EventType should be a class with string constants."""
    assert hasattr(senza, "EventType")


def test_event_type_constants():
    """EventType should have all expected event type constants."""
    expected = {
        "TEXT_DELTA": "text_delta",
        "TOOL_CALL_START": "tool_call_start",
        "TOOL_CALL_END": "tool_call_end",
        "TOOL_RESULT": "tool_result",
        "MESSAGE_END": "message_end",
        "THINKING_DELTA": "thinking_delta",
        "ERROR": "error",
        "AGENT_END": "agent_end",
        "SETTLED": "settled",
        "ABORTED": "aborted",
    }
    for name, value in expected.items():
        assert getattr(senza.EventType, name) == value


def test_event_type_in_all():
    """EventType should be in __all__."""
    assert "EventType" in senza.__all__
