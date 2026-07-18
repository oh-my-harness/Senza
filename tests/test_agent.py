"""Tests for PyAgent — verifies Agent wrapping + tokio runtime + GIL interaction."""

import senza


def test_agent_prompt_returns_response():
    """prompt() returns the mock LLM response text."""
    agent = senza.Agent(model="mock-model")
    response = agent.prompt("hello")
    assert isinstance(response, str)
    assert len(response) > 0
    assert "hello from mock" in response


def test_agent_multiple_instances():
    """Multiple Agent instances can be created and prompted independently."""
    a1 = senza.Agent()
    a2 = senza.Agent()
    r1 = a1.prompt("test1")
    r2 = a2.prompt("test2")
    assert isinstance(r1, str)
    assert isinstance(r2, str)
    assert "hello from mock" in r1
    assert "hello from mock" in r2


def test_agent_message_count_after_prompt():
    """After prompt, the transcript contains user + assistant messages."""
    agent = senza.Agent()
    assert agent.message_count() == 0
    agent.prompt("hello")
    # At least user message + assistant message
    assert agent.message_count() >= 2


def test_agent_phase_is_idle():
    """Agent phase is idle before and after prompt."""
    agent = senza.Agent()
    assert agent.phase() == "idle"
    agent.prompt("hello")
    assert agent.phase() == "idle"


def test_agent_repeated_prompts():
    """The same agent can handle multiple sequential prompts."""
    agent = senza.Agent()
    r1 = agent.prompt("first")
    r2 = agent.prompt("second")
    assert "hello from mock" in r1
    assert "hello from mock" in r2
    # After two prompts, transcript should have 4+ messages
    assert agent.message_count() >= 4
