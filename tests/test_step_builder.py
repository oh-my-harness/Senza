"""Tests for WorkflowEngine.with_step_builder (#10).

Verifies the per-step builder customizer is exposed to Python and that
the callback fires when the engine builds the harness for that step.
Rust-side behavioral correctness (per-step overrides shared customize)
is covered by the runtime crate's `per_step_builder_overrides_shared_max_tokens`
test; here we validate the Python binding surface and callback invocation.
"""

import threading

import senza


def _llm_workflow():
    return {
        "entry_step": "rtl_tx",
        "steps": [
            {
                "id": "rtl_tx",
                "name": "RTL",
                "prompt": "Generate RTL",
                "allowed_tools": [],
            }
        ],
        "edges": [],
    }


def _provider():
    # Point at an unreachable port so the LLM call fails fast, but only
    # *after* the engine has constructed the per-step harness — which is
    # when the with_step_builder callback runs.
    return senza.create_openai_provider(
        api_key="test-key",
        base_url="http://127.0.0.1:1",
    )


def _judge():
    return senza.create_judge(lambda ctx: "abort:done")


def test_with_step_builder_returns_self():
    """with_step_builder chains and returns the engine."""
    engine = senza.WorkflowEngine(_llm_workflow(), _provider(), "gpt-4o", _judge())
    result = engine.with_step_builder("rtl_tx", lambda b: b.system_prompt("RTL"))
    assert result is engine


def test_with_step_builder_has_docstring():
    """with_step_builder is documented."""
    assert senza.WorkflowEngine.with_step_builder.__doc__ is not None


def test_with_step_builder_callback_invoked():
    """The per-step callback runs when the engine builds that step's harness."""
    invoked = {"count": 0, "step_id": None}

    def customize(builder):
        invoked["count"] += 1
        return builder.system_prompt("RTL_SYSTEM_PROMPT")

    engine = senza.WorkflowEngine(_llm_workflow(), _provider(), "gpt-4o", _judge())
    engine.with_step_builder("rtl_tx", customize)

    # Run in a thread so we can observe the callback (run() blocks).
    it = engine.subscribe()
    err = {}

    def run():
        try:
            engine.run()
        except Exception as e:
            err["exc"] = e

    t = threading.Thread(target=run)
    t.start()

    # Drain events until the workflow terminates.
    for event in it:
        if event.get("type") in ("workflow_ended", "error", "step_failed"):
            break

    t.join(timeout=30)

    # The provider is unreachable, so the workflow fails — but the
    # per-step builder callback must have fired before the request.
    assert invoked["count"] >= 1, "with_step_builder callback was not invoked"
