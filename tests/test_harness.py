"""Tests for PyAgentHarness wrapper and builder.provider()."""

import pytest
import senza as lh


def test_builder_with_provider_returns_harness():
    """build() with a provider returns an AgentHarness, not an Agent."""
    provider = lh.create_openai_provider(api_key="test-key")
    harness = (
        lh.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .system_prompt("You are helpful.")
        .max_tokens(1024)
        .build()
    )
    assert type(harness).__name__ == "AgentHarness"


def test_harness_has_prompt_method():
    """AgentHarness exposes a prompt() method."""
    provider = lh.create_openai_provider(api_key="test-key")
    harness = lh.HarnessBuilder("gpt-4o").provider("gpt-*", provider).build()
    assert hasattr(harness, "prompt")


def test_harness_has_events_method():
    """AgentHarness exposes an events() method."""
    provider = lh.create_openai_provider(api_key="test-key")
    harness = lh.HarnessBuilder("gpt-4o").provider("gpt-*", provider).build()
    assert hasattr(harness, "events")


def test_harness_has_message_count():
    """AgentHarness exposes message_count()."""
    provider = lh.create_openai_provider(api_key="test-key")
    harness = lh.HarnessBuilder("gpt-4o").provider("gpt-*", provider).build()
    assert hasattr(harness, "message_count")
    assert harness.message_count() == 0


def test_harness_has_phase():
    """AgentHarness exposes phase()."""
    provider = lh.create_openai_provider(api_key="test-key")
    harness = lh.HarnessBuilder("gpt-4o").provider("gpt-*", provider).build()
    assert hasattr(harness, "phase")
    assert harness.phase() == "idle"


def test_build_without_provider_raises():
    """build() without a provider raises RuntimeError."""
    builder = lh.HarnessBuilder("gpt-4o")
    with pytest.raises(RuntimeError):
        builder.build()


def test_build_consumed_builder_raises():
    """Calling build() twice raises RuntimeError."""
    provider = lh.create_openai_provider(api_key="test-key")
    builder = lh.HarnessBuilder("gpt-4o").provider("gpt-*", provider)
    builder.build()
    with pytest.raises(RuntimeError):
        builder.build()


def test_provider_chaining_returns_builder():
    """provider() returns self for chaining."""
    provider = lh.create_openai_provider(api_key="test-key")
    builder = lh.HarnessBuilder("gpt-4o")
    result = builder.provider("gpt-*", provider)
    assert result is builder
