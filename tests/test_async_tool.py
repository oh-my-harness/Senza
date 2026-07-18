"""Tests for async Python tool callback — verifies no deadlock."""

import asyncio
import json

import senza


def test_async_tool_creation():
    """create_tool accepts an async def callback and returns a Tool wrapper."""

    async def async_echo(args, ctx):
        await asyncio.sleep(0.01)
        return {
            "content": [{"type": "text", "text": args.get("text", "")}],
            "details": {},
            "terminate": False,
        }

    tool = senza.create_tool(
        "async_echo",
        "Async echo",
        json.dumps({"type": "object", "properties": {"text": {"type": "string"}}}),
        async_echo,
    )
    assert tool is not None


def test_async_tool_echo_roundtrip():
    """An async echo callback executes via asyncio.run on the spawn_blocking thread."""

    async def async_echo(args, ctx):
        await asyncio.sleep(0.01)
        return {
            "content": [{"type": "text", "text": args["text"]}],
            "details": {"echoed": True},
            "terminate": False,
        }

    tool = senza.create_tool(
        "async_echo",
        "Async echo",
        json.dumps({"type": "object", "properties": {"text": {"type": "string"}}}),
        async_echo,
    )

    result = tool.drive({"text": "async hello"})
    assert len(result["content"]) == 1
    assert result["content"][0]["text"] == "async hello"
    assert result["details"]["echoed"] is True
    assert result["terminate"] is False


def test_sync_tool_still_works():
    """create_tool also accepts sync callbacks (unified entry point)."""

    def sync_echo(args, ctx):
        return {
            "content": [{"type": "text", "text": args.get("text", "")}],
            "details": {},
            "terminate": False,
        }

    tool = senza.create_tool(
        "sync_echo",
        "Sync echo",
        json.dumps({"type": "object", "properties": {"text": {"type": "string"}}}),
        sync_echo,
    )

    result = tool.drive({"text": "sync hello"})
    assert result["content"][0]["text"] == "sync hello"


def test_async_tool_terminate_flag():
    """terminate=True propagates from an async callback."""

    async def async_stop(args, ctx):
        await asyncio.sleep(0.01)
        return {"content": [], "terminate": True}

    tool = senza.create_tool(
        "async_stop",
        "Async stop",
        json.dumps({"type": "object", "properties": {}}),
        async_stop,
    )

    result = tool.drive({})
    assert result["terminate"] is True
