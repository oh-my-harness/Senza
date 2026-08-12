"""Tests for async run and prompt methods."""

import asyncio

import pytest

import senza


def test_workflow_engine_has_run_async():
    """WorkflowEngine class has run_async method."""
    assert hasattr(senza.WorkflowEngine, "run_async")


def test_agent_harness_has_prompt_async():
    """AgentHarness class has prompt_async method."""
    assert hasattr(senza.AgentHarness, "prompt_async")


def test_run_async_does_not_block_event_loop():
    """run_async runs in a thread, allowing other coroutines to proceed."""

    counter = []

    async def concurrent_task():
        await asyncio.sleep(0.01)
        counter.append("ran")

    async def main():
        import unittest.mock

        engine = unittest.mock.MagicMock()
        engine.run = lambda: counter.append("engine_ran")

        task = asyncio.create_task(concurrent_task())
        await asyncio.to_thread(engine.run)
        await task

        assert counter == ["engine_ran", "ran"]

    asyncio.run(main())


def test_prompt_async_does_not_block_event_loop():
    """prompt_async runs in a thread, allowing other coroutines to proceed."""
    counter = []

    async def concurrent_task():
        await asyncio.sleep(0.01)
        counter.append("ran")

    async def main():
        import unittest.mock

        harness = unittest.mock.MagicMock()
        harness.prompt_and_collect = lambda text, timeout_ms=30000: counter.append("prompt_ran")

        task = asyncio.create_task(concurrent_task())
        await asyncio.to_thread(harness.prompt_and_collect, "hello")
        await task

        assert counter == ["prompt_ran", "ran"]

    asyncio.run(main())
