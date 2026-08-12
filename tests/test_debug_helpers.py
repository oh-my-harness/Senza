"""Tests for debug helpers and inspect methods."""

import logging

import senza


def test_default_log_level_is_info():
    """The senza logger should default to INFO level."""
    logger = logging.getLogger("senza")
    assert logger.level <= logging.INFO


def test_enable_debug_sets_debug_level():
    """enable_debug() sets the logger to DEBUG."""
    senza.enable_debug()
    assert logging.getLogger("senza").level == logging.DEBUG


def test_disable_debug_restores_info_level():
    """disable_debug() restores INFO level."""
    senza.enable_debug()
    senza.disable_debug()
    assert logging.getLogger("senza").level == logging.INFO


def test_workflow_engine_inspect():
    """WorkflowEngine.inspect() returns a dict with expected keys."""
    provider = senza.create_openai_provider(api_key="sk-test")
    workflow = {
        "entry_step": "step1",
        "steps": [{"id": "step1", "name": "Step 1", "prompt": "test", "allowed_tools": []}],
        "edges": [],
    }

    def judge(ctx):
        return "done"

    engine = senza.WorkflowEngine(workflow, provider, "gpt-4o", senza.create_judge(judge))
    result = engine.inspect()

    assert isinstance(result, dict)
    assert "state" in result
    assert "current_step" in result
    assert "step_count" in result
    assert "total_cost" in result


def test_agent_harness_inspect():
    """AgentHarness.inspect() returns a dict with expected keys."""
    provider = senza.create_openai_provider(api_key="sk-test")
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .system_prompt("test")
        .max_tokens(256)
        .build()
    )
    result = harness.inspect()

    assert isinstance(result, dict)
    assert "message_count" in result
    assert "usage" in result
    assert "queued_messages" in result
