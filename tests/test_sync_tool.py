"""Tests for PyTool — sync Python callable wrapped as Tool trait."""

import json

import senza


def test_sync_tool_creation():
    """create_sync_tool returns a non-None Tool wrapper."""

    def echo(args, ctx):
        return {
            "content": [{"type": "text", "text": args.get("text", "")}],
            "details": {"echoed": True},
            "terminate": False,
        }

    tool = senza.create_sync_tool(
        "echo",
        "Echo text back",
        json.dumps({"type": "object", "properties": {"text": {"type": "string"}}}),
        echo,
    )
    assert tool is not None


def test_sync_tool_context_methods():
    """ToolContext exposes is_cancelled and send_update; is_cancelled is False."""
    captured = {}

    def tool_fn(args, ctx):
        captured["has_is_cancelled"] = hasattr(ctx, "is_cancelled")
        captured["has_send_update"] = hasattr(ctx, "send_update")
        captured["is_cancelled_val"] = ctx.is_cancelled()
        return {"content": [], "terminate": False}

    tool = senza.create_sync_tool(
        "check_ctx",
        "Check context",
        json.dumps({"type": "object", "properties": {}}),
        tool_fn,
    )
    assert tool is not None

    # Drive the tool end-to-end via the Rust async runtime.
    result = tool.drive({"text": "hi"})
    assert captured["has_is_cancelled"] is True
    assert captured["has_send_update"] is True
    assert captured["is_cancelled_val"] is False
    assert result["content"] == []


def test_sync_tool_echo_roundtrip():
    """A sync echo callback returns text content via Tool::execute."""

    def echo(args, ctx):
        return {
            "content": [{"type": "text", "text": args["text"]}],
            "details": {"echoed": True},
            "terminate": False,
        }

    tool = senza.create_sync_tool(
        "echo",
        "Echo text back",
        json.dumps({"type": "object", "properties": {"text": {"type": "string"}}}),
        echo,
    )

    result = tool.drive({"text": "hello"})
    assert len(result["content"]) == 1
    assert result["content"][0]["text"] == "hello"
    assert result["details"]["echoed"] is True
    assert result["terminate"] is False


def test_sync_tool_terminate_flag():
    """terminate=True propagates from the Python callback."""

    def stopper(args, ctx):
        return {"content": [], "terminate": True}

    tool = senza.create_sync_tool(
        "stop",
        "Stop the loop",
        json.dumps({"type": "object", "properties": {}}),
        stopper,
    )

    result = tool.drive({})
    assert result["terminate"] is True
