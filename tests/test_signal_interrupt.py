"""Tests for Ctrl+C / SIGINT interruption of long-blocking calls (issue #14)."""

import os
import signal
import threading
import time

import pytest
import senza as lh


def _raise_sigint_after(delay: float):
    """Start a daemon thread that sends SIGINT to the process after `delay` seconds."""

    def _target():
        time.sleep(delay)
        os.kill(os.getpid(), signal.SIGINT)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return t


def _make_provider():
    return lh.create_openai_provider(api_key="test-key")


def _make_judge():
    return lh.create_judge(lambda ctx: "abort:done")


def test_workflow_run_interrupted_by_sigint():
    """SIGINT interrupts workflow run() and raises KeyboardInterrupt.

    Uses a Python executor that sleeps to create a long-running workflow
    that exercises the ``block_on_with_signal_check`` path.
    """
    workflow = {
        "entry_step": "step1",
        "steps": [
            {"id": "step1", "name": "Slow Step", "executor": "slow_exec"},
        ],
        "edges": [],
    }

    def slow_executor(ctx):
        time.sleep(10)
        return {"output": "done"}

    engine = lh.WorkflowEngine(workflow, _make_provider(), "gpt-4o", _make_judge())
    engine.with_executor("slow_exec", lh.create_executor(slow_executor))

    t = _raise_sigint_after(0.5)

    with pytest.raises(KeyboardInterrupt):
        engine.run()

    t.join(timeout=5)


def test_collect_until_settled_interrupted_by_sigint():
    """SIGINT interrupts collect_until_settled() and raises KeyboardInterrupt.

    On an idle harness with no running prompt, collect_until_settled blocks
    waiting for events.  The ``recv_event_with_signal_check`` helper should
    catch the signal within ~200 ms.
    """
    harness = lh.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider()).build()

    t = _raise_sigint_after(0.5)

    with pytest.raises(KeyboardInterrupt):
        harness.collect_until_settled(timeout_ms=30000)

    t.join(timeout=5)
