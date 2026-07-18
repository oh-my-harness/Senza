"""Tests for Plugin wrapper."""

import json
import senza


def test_create_plugin_minimal():
    """create_plugin with name only returns a non-None Plugin."""
    plugin = senza.create_plugin("my-plugin")
    assert plugin is not None


def test_create_plugin_with_tools_and_hooks():
    """create_plugin accepts tools and hooks lists."""

    def echo(args, ctx):
        return {"content": [], "terminate": False}

    def my_hook(ctx):
        pass

    tool = senza.create_tool(
        "echo", "Echo", json.dumps({"type": "object"}), echo
    )
    hook = senza.create_before_turn_hook(my_hook)

    plugin = senza.create_plugin("full-plugin", tools=[tool], hooks=[hook])
    assert plugin is not None


def test_plugin_name_attribute():
    """Plugin exposes its name."""
    plugin = senza.create_plugin("named-plugin")
    assert plugin.name == "named-plugin"


def test_create_plugin_empty_lists():
    """create_plugin accepts empty tools and hooks lists."""
    plugin = senza.create_plugin("empty-lists", tools=[], hooks=[])
    assert plugin is not None


def test_create_plugin_multiple_hook_types():
    """create_plugin accepts multiple different hook types in one list."""

    def before_turn_cb(ctx):
        pass

    def after_turn_cb(ctx):
        pass

    def should_stop_cb(ctx):
        return False

    h1 = senza.create_before_turn_hook(before_turn_cb)
    h2 = senza.create_after_turn_hook(after_turn_cb)
    h3 = senza.create_should_stop_hook(should_stop_cb)

    plugin = senza.create_plugin(
        "multi-hooks", tools=None, hooks=[h1, h2, h3]
    )
    assert plugin is not None


def test_create_plugin_multiple_tools():
    """create_plugin accepts multiple tools."""

    def tool_a(args, ctx):
        return {"content": [], "terminate": False}

    def tool_b(args, ctx):
        return {"content": [], "terminate": False}

    t1 = senza.create_tool("a", "Tool A", json.dumps({"type": "object"}), tool_a)
    t2 = senza.create_tool("b", "Tool B", json.dumps({"type": "object"}), tool_b)

    plugin = senza.create_plugin("multi-tools", tools=[t1, t2])
    assert plugin is not None
