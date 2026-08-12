"""Tests for typed exception hierarchy."""

import pytest

import senza


def test_exception_hierarchy():
    """All Senza exceptions inherit from SenzaError, which inherits from RuntimeError."""
    assert issubclass(senza.SenzaError, RuntimeError)
    assert issubclass(senza.ProviderError, senza.SenzaError)
    assert issubclass(senza.RateLimitError, senza.ProviderError)
    assert issubclass(senza.ProviderTimeoutError, senza.ProviderError)
    assert issubclass(senza.ToolError, senza.SenzaError)
    assert issubclass(senza.ToolArgumentError, senza.ToolError)
    assert issubclass(senza.ToolAbortedError, senza.ToolError)
    assert issubclass(senza.ToolExecutionError, senza.ToolError)
    assert issubclass(senza.BudgetExceededError, senza.SenzaError)
    assert issubclass(senza.WorkflowError, senza.SenzaError)
    assert issubclass(senza.StepTimeoutError, senza.WorkflowError)
    assert issubclass(senza.StepFailedError, senza.WorkflowError)
    assert issubclass(senza.WorkflowPausedError, senza.WorkflowError)
    assert issubclass(senza.ValidationError, ValueError)
    assert issubclass(senza.HarnessStateError, senza.SenzaError)
    assert issubclass(senza.CompactionError, senza.SenzaError)
    assert issubclass(senza.StreamIdleTimeoutError, senza.SenzaError)
    assert issubclass(senza.RustPanicError, RuntimeError)


def test_catch_as_runtime_error():
    """All Senza exceptions are catchable as RuntimeError (backward compat)."""
    try:
        raise senza.ProviderError("provider failed")
    except RuntimeError as e:
        assert "provider failed" in str(e)


def test_catch_as_senza_error():
    """Subclasses catch their parents."""
    try:
        raise senza.RateLimitError("rate limited")
    except senza.ProviderError:
        pass
    except RuntimeError:
        pytest.fail("Should have caught as ProviderError")


def test_workflow_validation_error_is_value_error():
    """Invalid workflow raises ValidationError (subclass of ValueError)."""
    provider = senza.providers.openai(api_key="sk-test")

    bad_workflow = {
        "entry_step": "nonexistent",
        "steps": [{"id": "step1", "name": "Step 1", "prompt": "test", "allowed_tools": []}],
        "edges": [],
    }

    def judge(ctx):
        return "done"

    with pytest.raises(ValueError):
        engine = senza.WorkflowEngine(
            bad_workflow, provider, "gpt-4o", senza.create_judge(judge)
        )
        engine.run()
