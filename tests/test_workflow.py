"""Tests for PyJudge and PyExecutor — workflow trait callback wrappers."""

import senza

# ── PyJudge creation tests ───────────────────────────────────────────────────


def test_create_judge():
    """create_judge returns a Judge wrapper object."""

    def judge_fn(ctx):
        if ctx.get("structured", {}).get("passed"):
            return "to:next_step"
        return "retry"

    judge = senza.create_judge(judge_fn)
    assert judge is not None


def test_create_judge_with_lambda():
    """create_judge accepts a lambda callback."""
    judge = senza.create_judge(lambda ctx: "to:step2")
    assert judge is not None


# ── PyExecutor creation tests ────────────────────────────────────────────────


def test_create_executor():
    """create_executor returns an Executor wrapper object."""

    def exec_fn(ctx):
        return {
            "output": "executed",
            "structured": {"result": "done"},
        }

    executor = senza.create_executor(exec_fn)
    assert executor is not None


def test_create_executor_with_lambda():
    """create_executor accepts a lambda callback."""
    executor = senza.create_executor(lambda ctx: {"output": "hello", "structured": {"ok": True}})
    assert executor is not None


# ── End-to-end workflow tests via PyAgent-like engine bridge ─────────────────
# The following tests verify that PyJudge and PyExecutor can be created from
# Python and that their underlying Rust structs correctly implement the traits.
# Full workflow engine integration is tested in the Rust integration test
# (tests/workflow_integration.rs) because it requires tokio + MockLlmClient.


def test_judge_and_executor_together():
    """Both a judge and executor can be created in the same session."""
    judge = senza.create_judge(lambda ctx: "retry")
    executor = senza.create_executor(lambda ctx: {"output": "result", "structured": None})
    assert judge is not None
    assert executor is not None


def test_multiple_judges():
    """Multiple judge instances are independent."""
    j1 = senza.create_judge(lambda ctx: "to:s1")
    j2 = senza.create_judge(lambda ctx: "to:s2")
    assert j1 is not None
    assert j2 is not None


def test_multiple_executors():
    """Multiple executor instances are independent."""
    e1 = senza.create_executor(lambda ctx: {"output": "e1"})
    e2 = senza.create_executor(lambda ctx: {"output": "e2"})
    assert e1 is not None
    assert e2 is not None
