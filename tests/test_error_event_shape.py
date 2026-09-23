"""Tests for the serialized AgentEvent::Error dict shape.

Regression for the examples 47/48 bug: the code printed
``event.get("error", "?")`` for ``type == "error"`` events, but the
serializer (``src/shared/event_stream.rs``) maps ``AgentEvent::Error`` to
``{type, message, error_type}`` — there is no ``error`` key — so the real
failure cause was always replaced by the fallback ``"?"``.

These tests pin the serializer contract: an error event carries the
human-readable message in ``message``, a variant tag in ``error_type``, and
no ``error`` key. Deterministic and offline: the failure is induced with a
connection-refused provider (same pattern as ``test_prompt_collect_lifecycle``),
so no network or API key is needed.
"""

import threading

import senza


def _dead_provider():
    # Connection-refused endpoint: any provider request fails immediately,
    # without network access.
    return senza.providers.openai(api_key="unused", base_url="http://127.0.0.1:1")


def _error_event() -> dict:
    """Prompt a harness whose provider always fails; return the error event."""
    harness = senza.HarnessBuilder("unused-model").provider("*", _dead_provider()).build()
    events = []
    it = harness.events(timeout_ms=5000)

    def do_prompt():
        try:
            harness.prompt("hello")
        except Exception:
            pass  # the error event itself is what we are asserting on

    t = threading.Thread(target=do_prompt)
    t.start()

    for event in it:
        events.append(event)
        if event.get("type") in ("agent_end", "error", "settled", "aborted"):
            break

    t.join()

    error_events = [e for e in events if e.get("type") == "error"]
    assert error_events, (
        f"expected an error event from a failing provider, got: {[e.get('type') for e in events]}"
    )
    return error_events[0]


def test_error_event_has_message_and_error_type_not_error_key():
    """type=="error" events expose {message, error_type}; never an 'error' key."""
    err = _error_event()
    assert set(err) == {"type", "message", "error_type"}, (
        f"error event must serialize to exactly {{type, message, error_type}}, "
        f"got keys {sorted(err)}"
    )
    assert "error" not in err, (
        "error events must not carry an 'error' key — "
        "consumers must read 'message' (examples 47/48 regression)"
    )
    assert isinstance(err["message"], str)
    assert len(err["message"]) > 0, "message should carry the human-readable error"
    assert isinstance(err["error_type"], str)
    assert len(err["error_type"]) > 0
    # Connection-refused provider failure is surfaced as a provider error.
    assert err["error_type"] == "provider", (
        f"expected error_type='provider' for a provider failure, "
        f"got {err['error_type']!r} (message: {err['message']})"
    )


def test_error_event_message_contains_provider_failure_detail():
    """The human-readable cause (not a placeholder) lands in `message`."""
    message = _error_event()["message"]
    # The serializer must surface the underlying error text — the pre-fix
    # symptom was consumers printing a bare "?" because the field was missing.
    assert message != "?"
    assert "error" in message.lower(), (
        f"message should contain the provider failure detail, got: {message!r}"
    )
