"""Tests for flexible tool return values."""

import json

import senza


def _make_tool(callback):
    return senza.create_tool(
        "test_tool",
        "Test tool",
        {"type": "object", "properties": {}},
        callback,
    )


def test_str_return():
    """Plain string return is wrapped as text content."""

    def cb(args, ctx):
        return "hello world"

    tool = _make_tool(cb)
    result = tool.drive({})
    assert len(result["content"]) == 1
    assert result["content"][0]["text"] == "hello world"
    assert result["terminate"] is False


def test_dict_with_content_return():
    """Dict with content key is passed through (existing behavior)."""

    def cb(args, ctx):
        return {"content": [{"type": "text", "text": "structured"}], "terminate": True}

    tool = _make_tool(cb)
    result = tool.drive({})
    assert result["content"][0]["text"] == "structured"
    assert result["terminate"] is True


def test_dict_without_content_return():
    """Dict without content key is wrapped as text content (JSON-serialized)."""

    def cb(args, ctx):
        return {"status": "ok", "count": 42}

    tool = _make_tool(cb)
    result = tool.drive({})
    assert len(result["content"]) == 1
    parsed = json.loads(result["content"][0]["text"])
    assert parsed["status"] == "ok"
    assert parsed["count"] == 42
    assert result["terminate"] is False


def test_dict_without_content_with_terminate():
    """Dict without content but with terminate key respects terminate."""

    def cb(args, ctx):
        return {"status": "done", "terminate": True}

    tool = _make_tool(cb)
    result = tool.drive({})
    assert result["terminate"] is True
