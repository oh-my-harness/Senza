"""Tests for AgentHarness.chat() convenience method."""

import senza


def test_chat_method_exists():
    """AgentHarness should have a chat method."""
    assert hasattr(senza.AgentHarness, "chat")


def test_chat_async_method_exists():
    """AgentHarness should have a chat_async method."""
    assert hasattr(senza.AgentHarness, "chat_async")
