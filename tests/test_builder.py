"""Tests for HarnessBuilder wrapper."""

import json

import pytest
import senza


def test_builder_creation():
    """HarnessBuilder can be created with a model string."""
    builder = senza.HarnessBuilder("claude-3-5-sonnet")
    assert builder is not None


def test_builder_system_prompt():
    """system_prompt method returns self for chaining."""
    builder = senza.HarnessBuilder("claude-3-5-sonnet")
    result = builder.system_prompt("You are helpful")
    assert result is builder


def test_builder_max_tokens():
    """max_tokens method returns self for chaining."""
    builder = senza.HarnessBuilder("claude-3-5-sonnet")
    result = builder.max_tokens(4096)
    assert result is builder


def test_builder_temperature():
    """temperature method returns self for chaining."""
    builder = senza.HarnessBuilder("claude-3-5-sonnet")
    result = builder.temperature(0.7)
    assert result is builder
    # None should also be accepted (resets to default).
    result2 = builder.temperature(None)
    assert result2 is builder


def test_builder_with_tool():
    """tool method accepts a Tool and returns self."""

    def echo(args, ctx):
        return {"content": [], "terminate": False}

    tool = senza.create_tool("echo", "Echo", json.dumps({"type": "object"}), echo)
    builder = senza.HarnessBuilder("claude-3-5-sonnet")
    result = builder.tool(tool)
    assert result is builder


def test_builder_with_plugin():
    """plugin method accepts a Plugin and returns self."""
    plugin = senza.create_plugin("test-plugin")
    builder = senza.HarnessBuilder("claude-3-5-sonnet")
    result = builder.plugin(plugin)
    assert result is builder


def test_builder_chaining():
    """All fluent methods chain together."""

    def echo(args, ctx):
        return {"content": [], "terminate": False}

    tool = senza.create_tool("echo", "Echo", json.dumps({"type": "object"}), echo)
    plugin = senza.create_plugin("p1", tools=[tool])

    builder = (
        senza.HarnessBuilder("claude-3-5-sonnet")
        .system_prompt("You are helpful")
        .max_tokens(2048)
        .temperature(0.5)
        .tool(tool)
        .plugin(plugin)
    )
    assert builder is not None


def test_builder_build_without_provider_raises():
    """build() without a provider raises RuntimeError."""
    builder = senza.HarnessBuilder("claude-3-5-sonnet")
    with pytest.raises(RuntimeError):
        builder.build()
