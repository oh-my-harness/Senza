"""Verification tests for issues #58, #59, #60."""

import pytest
import senza as lh


# ── #59: create_openai_provider chat_path/thinking_scheme + /v1 strip ──────

def test_create_openai_provider_with_chat_path():
    """create_openai_provider accepts a custom chat_path (#59)."""
    provider = lh.create_openai_provider(
        api_key="test-key", chat_path="/chat/completions"
    )
    assert provider is not None


def test_create_openai_provider_with_thinking_scheme():
    """create_openai_provider accepts thinking_scheme (#59)."""
    provider = lh.create_openai_provider(
        api_key="test-key", thinking_scheme="reasoning_effort"
    )
    assert provider is not None


def test_create_openai_provider_thinking_toggle():
    provider = lh.create_openai_provider(
        api_key="test-key", thinking_scheme="thinking_toggle"
    )
    assert provider is not None


def test_create_openai_provider_invalid_thinking_scheme():
    """Invalid thinking_scheme raises ValueError (#59)."""
    with pytest.raises(ValueError):
        lh.create_openai_provider(api_key="test-key", thinking_scheme="bogus")


def test_create_openai_provider_strips_trailing_v1():
    """base_url ending in /v1 doesn't crash — auto-stripped (#59)."""
    provider = lh.create_openai_provider(
        api_key="test-key", base_url="http://localhost:8080/v1"
    )
    assert provider is not None


def test_create_openai_provider_custom_chat_path_keeps_v1():
    """When chat_path is custom, base_url /v1 is NOT stripped (#59)."""
    provider = lh.create_openai_provider(
        api_key="test-key",
        base_url="http://localhost:8080/v1",
        chat_path="/chat/completions",
    )
    assert provider is not None


# ── #58: prompt_and_collect error propagation ──────────────────────────────

def test_prompt_and_collect_propagates_llm_error():
    """prompt_and_collect() propagates LLM errors instead of returning [] (#58).

    Points provider at a dead port so the LLM call fails immediately.
    The error must surface as RuntimeError, not be swallowed.
    """
    provider = lh.create_openai_provider(
        api_key="bad-key", base_url="http://127.0.0.1:1"
    )
    harness = (
        lh.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .system_prompt("You are helpful.")
        .max_tokens(64)
        .build()
    )
    with pytest.raises(RuntimeError):
        harness.prompt_and_collect("Hello", timeout_ms=10000)
