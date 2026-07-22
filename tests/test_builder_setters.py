"""Smoke tests for newly exposed HarnessBuilder setters (G6)."""

import senza


def _make_provider():
    return senza.create_openai_provider(api_key="test-key")


def test_should_stop_hook():
    """should_stop_hook() accepts a Hook and chains."""
    hook = senza.create_should_stop_hook(lambda ctx: False)
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.should_stop_hook(hook)
    assert result is builder


def test_hooks():
    """hooks() accepts a list of Hooks and chains."""
    hook = senza.create_before_turn_hook(lambda ctx: None)
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.hooks([hook])
    assert result is builder


def test_retry():
    """retry() accepts max_retries and base_delay_ms."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.retry(max_retries=3, base_delay_ms=500)
    assert result is builder


def test_model_info():
    """model_info() accepts context_window and max_tokens."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.model_info(context_window=128000, max_tokens=16384)
    assert result is builder


def test_final_answer_mode():
    """final_answer_mode() accepts 'heuristic' and 'tool'."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.final_answer_mode("heuristic")
    assert result is builder
    builder2 = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    builder2.final_answer_mode("tool")


def test_final_answer_mode_invalid():
    """final_answer_mode() raises on invalid string."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    try:
        builder.final_answer_mode("bogus")
        assert False, "should have raised"
    except (ValueError, RuntimeError):
        pass


def test_stream_options():
    """stream_options() accepts timeout_ms and max_retries."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.stream_options(timeout_ms=30000, max_retries=2)
    assert result is builder


def test_stream_options_none():
    """stream_options() accepts None for both params."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.stream_options(timeout_ms=None, max_retries=None)
    assert result is builder


def test_queue_capacity():
    """queue_capacity() accepts int and None."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.queue_capacity(64)
    assert result is builder
    builder2 = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    builder2.queue_capacity(None)


def test_disable_skill_read_tool():
    """disable_skill_read_tool() chains with no args."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.disable_skill_read_tool()
    assert result is builder
