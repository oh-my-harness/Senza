"""Tests that create_tool accepts a dict for parameters_schema."""

import json

import pytest

import senza


def test_create_tool_with_dict_schema():
    """create_tool accepts a dict directly, no json.dumps needed."""

    def echo(args, ctx):
        return {"content": [{"type": "text", "text": args["text"]}], "terminate": False}

    tool = senza.create_tool(
        "echo",
        "Echo text back",
        {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        echo,
    )
    assert tool is not None
    assert tool.name == "echo"
    assert tool.description == "Echo text back"


def test_create_tool_with_str_schema_still_works():
    """create_tool still accepts a JSON string (backward compat)."""

    def echo(args, ctx):
        return {"content": [], "terminate": False}

    tool = senza.create_tool(
        "echo",
        "Echo",
        json.dumps({"type": "object", "properties": {}}),
        echo,
    )
    assert tool is not None


def test_create_tool_with_invalid_dict_raises():
    """Passing a non-serializable dict raises ValueError."""

    class NotSerializable:
        pass

    def cb(args, ctx):
        return {"content": [], "terminate": False}

    with pytest.raises((ValueError, TypeError)):
        senza.create_tool("bad", "bad", {"key": NotSerializable()}, cb)
