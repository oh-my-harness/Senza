"""Tests for async callback event-loop bridging (issue #13).

Verifies that ``senza.set_event_loop(loop)`` causes ``async def`` callbacks
to be scheduled on the registered loop via ``run_coroutine_threadsafe``,
rather than ``asyncio.run()`` (which creates a throwaway loop).
"""

import asyncio
import json
import threading

import pytest
import senza


def test_set_event_loop_exists():
    """set_event_loop is exposed as a top-level function."""
    assert callable(senza.set_event_loop)


def test_async_callback_runs_on_registered_loop():
    """An async tool callback runs on the registered event loop.

    We create a loop on a background thread, register it, then call an
    async tool.  Inside the coroutine, ``asyncio.get_running_loop()``
    must return the *same* loop object — proving the coroutine was
    scheduled via ``run_coroutine_threadsafe`` rather than ``asyncio.run``.
    """
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()

    senza.set_event_loop(loop)

    captured = {}

    async def check_loop(args, ctx):
        captured["running_loop"] = asyncio.get_running_loop()
        return {"content": [], "terminate": False}

    tool = senza.create_tool(
        "check_loop",
        "Check loop",
        json.dumps({"type": "object", "properties": {}}),
        check_loop,
    )

    try:
        result = tool.drive({})
        assert result["terminate"] is False
        assert captured["running_loop"] is loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(timeout=5)
        loop.close()


def test_async_callback_falls_back_without_registered_loop():
    """Without a registered loop, async callbacks use asyncio.run().

    After clearing the registration, the callback should still execute
    successfully (via the asyncio.run fallback).
    """
    # Clear any previously registered loop from earlier tests.
    # We can't call clear_event_loop from Python, but setting a stopped
    # loop causes run_coro to fall back to asyncio.run().
    stopped = asyncio.new_event_loop()  # not running
    senza.set_event_loop(stopped)

    async def simple_cb(args, ctx):
        await asyncio.sleep(0.01)
        return {"content": [{"type": "text", "text": "ok"}], "terminate": False}

    tool = senza.create_tool(
        "simple",
        "Simple",
        json.dumps({"type": "object", "properties": {}}),
        simple_cb,
    )

    result = tool.drive({})
    assert result["content"][0]["text"] == "ok"
    stopped.close()
