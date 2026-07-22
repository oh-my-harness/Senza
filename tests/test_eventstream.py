import senza


def test_create_event_channel():
    handle, tool = senza.create_event_channel("review-task-1")
    assert type(handle).__name__ == "EventStreamHandle"
    assert type(tool).__name__ == "WaitForExternalEventTool"


def test_event_stream_handle_submit():
    handle, _tool = senza.create_event_channel("review-task-1")
    handle.submit("approved", {"passed": True, "feedback": "looks good"})


def test_wait_for_event_tool_name():
    _handle, tool = senza.create_event_channel("review-task-1")
    assert tool.name() == "wait_for_external_event"
    assert isinstance(tool.description(), str)
