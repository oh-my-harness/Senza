"""Tests for senza.extract_text helper."""


def test_extract_text_single_event():
    import senza
    events = [{"type": "text_delta", "text": "hello"}]
    assert senza.extract_text(events) == "hello"


def test_extract_text_multiple_events():
    import senza
    events = [
        {"type": "text_delta", "text": "hello "},
        {"type": "text_delta", "text": "world"},
    ]
    assert senza.extract_text(events) == "hello world"


def test_extract_text_filters_non_text():
    import senza
    events = [
        {"type": "tool_call_start", "tool_name": "search"},
        {"type": "text_delta", "text": "result"},
        {"type": "settled"},
    ]
    assert senza.extract_text(events) == "result"


def test_extract_text_empty():
    import senza
    assert senza.extract_text([]) == ""


def test_extract_text_missing_text_field():
    import senza
    events = [{"type": "text_delta"}]
    assert senza.extract_text(events) == ""
