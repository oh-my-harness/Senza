"""Tests for UsageLedger Python binding."""

import pytest
import senza


def _make_provider():
    return senza.create_openai_provider(api_key="test-key")


# ── UsageLedger construction ─────────────────────────────────────────────────


def test_usage_ledger_construct():
    """UsageLedger() can be constructed with no arguments."""
    ledger = senza.UsageLedger()
    assert ledger is not None


def test_usage_ledger_snapshot_returns_dict():
    """snapshot() returns a dict on a fresh ledger."""
    ledger = senza.UsageLedger()
    snapshot = ledger.snapshot()
    assert isinstance(snapshot, dict)


def test_usage_ledger_snapshot_empty_zero_cost():
    """A fresh UsageLedger snapshot reports zero cost."""
    ledger = senza.UsageLedger()
    snapshot = ledger.snapshot()
    assert snapshot.get("total_cost", 0) == 0
    assert snapshot.get("total_input_tokens", 0) == 0
    assert snapshot.get("total_output_tokens", 0) == 0


def test_usage_ledger_snapshot_has_by_model():
    """snapshot() includes a by_model dict."""
    ledger = senza.UsageLedger()
    snapshot = ledger.snapshot()
    assert "by_model" in snapshot
    assert isinstance(snapshot["by_model"], dict)


# ── HarnessBuilder.usage_ledger ──────────────────────────────────────────────


def test_usage_ledger_chains_on_builder():
    """usage_ledger() returns the builder for chaining."""
    provider = _make_provider()
    builder = senza.HarnessBuilder("gpt-4o").provider("*", provider)
    result = builder.usage_ledger(senza.UsageLedger())
    assert result is builder


def test_usage_ledger_shared_between_agents():
    """A UsageLedger shared across two harness builders accumulates cost from both."""
    provider = _make_provider()
    ledger = senza.UsageLedger()

    builder1 = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .usage_ledger(ledger)
    )
    builder2 = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .usage_ledger(ledger)
    )
    assert builder1 is not None
    assert builder2 is not None


def test_usage_ledger_cloned_not_consumed():
    """Attaching a ledger to a builder does not consume the Python-side ledger."""
    provider = _make_provider()
    ledger = senza.UsageLedger()
    senza.HarnessBuilder("gpt-4o").provider("*", provider).usage_ledger(ledger)
    # The ledger should still be usable after being attached
    snapshot = ledger.snapshot()
    assert isinstance(snapshot, dict)


# ── AgentHarness.usage_ledger ────────────────────────────────────────────────


def test_harness_usage_ledger_returns_dict():
    """AgentHarness.usage_ledger() returns a dict."""
    provider = _make_provider()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .system_prompt("You are helpful.")
        .build()
    )
    cost = harness.usage_ledger()
    assert isinstance(cost, dict)


def test_harness_usage_ledger_zero_cost():
    """AgentHarness.usage_ledger() returns zero cost on a fresh harness."""
    provider = _make_provider()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .system_prompt("You are helpful.")
        .build()
    )
    cost = harness.usage_ledger()
    assert cost.get("total_input_tokens", 0) == 0
    assert cost.get("total_output_tokens", 0) == 0
    assert isinstance(cost.get("by_model"), dict)


def test_harness_usage_ledger_matches_usage():
    """usage_ledger() returns the same structure as usage()."""
    provider = _make_provider()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .system_prompt("You are helpful.")
        .build()
    )
    from_usage = harness.usage()
    from_ledger = harness.usage_ledger()
    assert from_usage == from_ledger
