"""Tests for compaction_prompt / compaction_query builder methods."""

import pytest
import senza


def _make_provider():
    return senza.providers.openai(api_key="test-key")


# ── compaction_prompt ────────────────────────────────────────────────────────


def test_compaction_prompt_chains():
    """compaction_prompt(system_prompt, user_template) chains and returns self."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.compaction_prompt(
        system_prompt="You are a summarizer.",
        user_template="Summarize: {conversation}",
    )
    assert result is builder


def test_compaction_prompt_none_clears():
    """compaction_prompt(None) clears the prompt."""
    builder = (
        senza.HarnessBuilder("gpt-4o")
        .provider("gpt-*", _make_provider())
        .compaction_prompt(
            system_prompt="You are a summarizer.",
            user_template="Summarize: {conversation}",
        )
        .compaction_prompt(None)
    )
    assert builder is not None


def test_compaction_prompt_missing_conversation_placeholder():
    """user_template without {conversation} raises RuntimeError."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    with pytest.raises(RuntimeError):
        builder.compaction_prompt(
            system_prompt="You are a summarizer.",
            user_template="No placeholder here.",
        )


def test_compaction_prompt_unknown_placeholder():
    """user_template with unknown placeholder raises RuntimeError."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    with pytest.raises(RuntimeError):
        builder.compaction_prompt(
            system_prompt="You are a summarizer.",
            user_template="Summarize: {conversation} and {unknown_thing}",
        )


def test_compaction_prompt_mixed_args_system_only():
    """Providing only system_prompt (no user_template) raises RuntimeError."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    with pytest.raises(RuntimeError):
        builder.compaction_prompt(system_prompt="only system")


def test_compaction_prompt_mixed_args_template_only():
    """Providing only user_template (no system_prompt) raises RuntimeError."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    with pytest.raises(RuntimeError):
        builder.compaction_prompt(user_template="Summarize: {conversation}")


# ── compaction_query ─────────────────────────────────────────────────────────


def test_compaction_query_chains():
    """compaction_query() chains and returns self."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.compaction_query("What was discussed?")
    assert result is builder


def test_compaction_query_none():
    """compaction_query(None) clears the query."""
    builder = (
        senza.HarnessBuilder("gpt-4o")
        .provider("gpt-*", _make_provider())
        .compaction_query("What was discussed?")
        .compaction_query(None)
    )
    assert builder is not None
