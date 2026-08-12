"""Tests for create_tool Python wrapper (parameters alias + callback fix)."""

import json

import pytest
import senza


def test_create_tool_with_parameters_kwarg():
    """create_tool should accept parameters= as the canonical kwarg."""

    def cb(args, ctx):
        return {"content": [], "terminate": False}

    tool = senza.create_tool(
        name="test",
        description="test",
        parameters={"type": "object", "properties": {}},
        callback=cb,
    )
    assert tool.name == "test"


def test_create_tool_with_parameters_schema_backward_compat():
    """create_tool should still accept parameters_schema= for backward compat."""

    def cb(args, ctx):
        return {"content": [], "terminate": False}

    tool = senza.create_tool(
        name="test",
        description="test",
        parameters_schema=json.dumps({"type": "object", "properties": {}}),
        callback=cb,
    )
    assert tool.name == "test"


def test_create_tool_single_arg_callback():
    """create_tool should accept a single-argument callback (args only)."""

    def single_arg_cb(args):
        return {"content": [{"type": "text", "text": args["x"]}], "terminate": False}

    tool = senza.create_tool(
        name="test",
        description="test",
        parameters={"type": "object", "properties": {"x": {"type": "string"}}},
        callback=single_arg_cb,
    )
    assert tool.name == "test"


def test_create_tool_missing_parameters_raises():
    """create_tool should raise if neither parameters nor parameters_schema is given."""

    def cb(args, ctx):
        return {"content": [], "terminate": False}

    with pytest.raises(TypeError):
        senza.create_tool("test", "test", callback=cb)
