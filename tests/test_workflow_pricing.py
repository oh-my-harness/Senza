"""Tests for WorkflowEngine.with_pricing (#20).

Binding-surface tests only — behavioral propagation (total_cost != 0)
is covered by the runtime crate's customize_builder tests. Senza does
not expose a mock LLM provider to Python for WorkflowEngine (see spec).
"""

import senza


def _make_workflow():
    return {
        "entry_step": "step1",
        "steps": [{"id": "step1", "name": "S1", "prompt": "p", "allowed_tools": []}],
        "edges": [],
    }


def _make_provider():
    return senza.create_openai_provider(api_key="test-key")


def _make_judge():
    return senza.create_judge(lambda ctx: "abort:done")


def _make_pricing():
    return senza.create_pricing_provider(
        {
            "gpt-4o": {
                "input_per_mtok": 2.5,
                "output_per_mtok": 10.0,
                "cache_read_per_mtok": 1.25,
                "cache_write_per_mtok": 2.5,
            },
        }
    )


def test_with_pricing_returns_self():
    """with_pricing() chains and returns self."""
    engine = senza.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    result = engine.with_pricing(_make_pricing())
    assert result is engine


def test_with_pricing_has_docstring():
    """with_pricing is documented."""
    assert senza.WorkflowEngine.with_pricing.__doc__ is not None


def test_with_pricing_chains_with_other_with_methods():
    """with_pricing composes with with_max_tokens on the shared customize chain."""
    engine = (
        senza.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
        .with_max_tokens(4096)
        .with_pricing(_make_pricing())
    )
    assert engine is not None
