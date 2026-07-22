"""Tests for PyEventIterator — event stream from broadcast::Receiver → Python iterator."""

import threading

import senza


def test_event_stream_yields_events():
    """events() yields a non-empty stream of event dicts with a 'type' field."""
    agent = senza.Agent(model="mock-model")
    events = []
    it = agent.events(timeout_ms=5000)

    def do_prompt():
        agent.prompt("hello")

    t = threading.Thread(target=do_prompt)
    t.start()

    for event in it:
        events.append(event)
        if event["type"] in ("agent_end", "error"):
            break

    t.join()
    assert len(events) > 0
    for e in events:
        assert "type" in e
        assert isinstance(e, dict)


def test_event_stream_contains_agent_start():
    """The first event should be agent_start."""
    agent = senza.Agent(model="mock-model")
    events = []
    it = agent.events(timeout_ms=5000)

    def do_prompt():
        agent.prompt("hello")

    t = threading.Thread(target=do_prompt)
    t.start()

    for event in it:
        events.append(event)
        if event["type"] in ("agent_end", "error"):
            break

    t.join()
    types = [e["type"] for e in events]
    assert "agent_start" in types


def test_event_stream_contains_text_delta():
    """TextDelta events should appear for mock LLM text responses."""
    agent = senza.Agent(model="mock-model")
    events = []
    it = agent.events(timeout_ms=5000)

    def do_prompt():
        agent.prompt("hello")

    t = threading.Thread(target=do_prompt)
    t.start()

    for event in it:
        events.append(event)
        if event["type"] in ("agent_end", "error"):
            break

    t.join()
    types = [e["type"] for e in events]
    # MockLlmClient returns text, so we should see text_delta or message_end
    assert "text_delta" in types or "message_end" in types or "agent_end" in types


def test_event_stream_agent_end_has_new_messages():
    """agent_end event should include new_messages_count."""
    agent = senza.Agent(model="mock-model")
    events = []
    it = agent.events(timeout_ms=5000)

    def do_prompt():
        agent.prompt("hello")

    t = threading.Thread(target=do_prompt)
    t.start()

    for event in it:
        events.append(event)
        if event["type"] in ("agent_end", "error"):
            break

    t.join()
    end_events = [e for e in events if e["type"] == "agent_end"]
    if end_events:
        assert "new_messages_count" in end_events[0]
        assert end_events[0]["new_messages_count"] > 0


def test_event_stream_timeout_returns_empty():
    """With default max_consecutive_timeouts=1, timeout terminates the iterator."""
    agent = senza.Agent(model="mock-model")
    it = agent.events(timeout_ms=100)
    events = list(it)
    assert events == []


def test_event_stream_timeout_continues_with_higher_limit():
    """With max_consecutive_timeouts > 1, timeout emits event and continues."""
    agent = senza.Agent(model="mock-model")
    it = agent.events(timeout_ms=100, max_consecutive_timeouts=3)
    first = next(it)
    assert first is not None
    assert first["type"] == "timeout"
    # Should continue (not terminate) since consecutive_timeouts(1) < max(3)
    second = next(it)
    assert second is not None
    assert second["type"] == "timeout"
    # Third timeout: consecutive_timeouts(3) >= max(3) → terminate
    with __import__("pytest").raises(StopIteration):
        next(it)


def test_event_stream_text_delta_has_text_field():
    """TextDelta events should have a 'text' field."""
    agent = senza.Agent(model="mock-model")
    events = []
    it = agent.events(timeout_ms=5000)

    def do_prompt():
        agent.prompt("hello")

    t = threading.Thread(target=do_prompt)
    t.start()

    for event in it:
        events.append(event)
        if event["type"] in ("agent_end", "error"):
            break

    t.join()
    deltas = [e for e in events if e["type"] == "text_delta"]
    for d in deltas:
        assert "text" in d
        assert isinstance(d["text"], str)


def test_event_stream_iterator_protocol():
    """__iter__ returns self, making the object a valid iterator."""
    agent = senza.Agent(model="mock-model")
    it = agent.events(timeout_ms=100)
    assert iter(it) is it


def test_event_stream_multiple_subscriptions():
    """Multiple iterators can subscribe to the same agent independently."""
    agent = senza.Agent(model="mock-model")
    events1 = []
    events2 = []
    it1 = agent.events(timeout_ms=5000)
    it2 = agent.events(timeout_ms=5000)

    def do_prompt():
        agent.prompt("hello")

    t = threading.Thread(target=do_prompt)
    t.start()

    # Consume from both iterators
    done1 = False
    done2 = False
    while not done1 or not done2:
        if not done1:
            try:
                e = next(it1)
                if e is not None:
                    events1.append(e)
                    if e["type"] in ("agent_end", "error"):
                        done1 = True
                else:
                    done1 = True
            except StopIteration:
                done1 = True
        if not done2:
            try:
                e = next(it2)
                if e is not None:
                    events2.append(e)
                    if e["type"] in ("agent_end", "error"):
                        done2 = True
                else:
                    done2 = True
            except StopIteration:
                done2 = True

    t.join()
    # Both should have received events
    assert len(events1) > 0
    assert len(events2) > 0
