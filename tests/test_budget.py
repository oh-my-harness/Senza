"""Smoke tests for Budget control exposure (G1)."""

import senza


def _make_provider():
    return senza.create_openai_provider(api_key="test-key")


def test_create_budget_exceeded_hook():
    """create_budget_exceeded_hook accepts a callback."""
    hook = senza.create_budget_exceeded_hook(lambda cost, limit: False)
    assert hook is not None
    assert type(hook).__name__ == "BudgetExceededHook"


def test_create_budget_exceeded_hook_async():
    """create_budget_exceeded_hook accepts an async callback."""

    async def on_exceed(cost, limit):
        return True

    hook = senza.create_budget_exceeded_hook(on_exceed)
    assert hook is not None


def test_builder_budget_surveillance():
    """builder.budget(limit) with no hook chains (surveillance mode)."""
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.budget(5.0)
    assert result is builder


def test_builder_budget_with_hook():
    """builder.budget(limit, hook) chains."""
    hook = senza.create_budget_exceeded_hook(lambda cost, limit: False)
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.budget(5.0, hook)
    assert result is builder


def test_builder_budget_then_build():
    """builder with budget set can build successfully."""
    hook = senza.create_budget_exceeded_hook(lambda cost, limit: False)
    harness = (
        senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider()).budget(5.0, hook).build()
    )
    assert harness is not None


def test_builder_budget_surveillance_build():
    """builder with surveillance budget (no hook) can build."""
    harness = senza.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider()).budget(5.0).build()
    assert harness is not None
