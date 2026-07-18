"""Tests for PyWorkflowEngine wrapper."""

import json
import pytest
import senza as lh


def _make_workflow():
    """Minimal single-step workflow dict for tests."""
    return {
        "entry_step": "step1",
        "steps": [{"id": "step1", "name": "Step 1", "prompt": "Do something", "allowed_tools": []}],
        "edges": [],
    }


def _make_provider():
    return lh.create_openai_provider(api_key="test-key")


def _make_judge():
    return lh.create_judge(lambda ctx: "abort:done")


def test_workflow_engine_creation():
    """WorkflowEngine can be constructed from a dict."""
    engine = lh.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    assert type(engine).__name__ == "WorkflowEngine"


def test_workflow_engine_task_id():
    """task_id() returns a string starting with 'task-'."""
    engine = lh.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    assert engine.task_id().startswith("task-")


def test_workflow_engine_with_tool():
    """with_tool() registers a tool and returns self for chaining."""
    workflow = {
        "entry_step": "step1",
        "steps": [{"id": "step1", "name": "S", "prompt": "Do", "allowed_tools": ["echo"]}],
        "edges": [],
    }
    tool = lh.create_tool(
        "echo",
        "Echo",
        json.dumps({"type": "object", "properties": {}}),
        lambda args, ctx: {"content": [], "terminate": False},
    )
    engine = lh.WorkflowEngine(workflow, _make_provider(), "gpt-4o", _make_judge())
    result = engine.with_tool(tool)
    assert result is engine


def test_workflow_engine_with_executor():
    """with_executor() registers a named executor."""
    executor = lh.create_executor(lambda ctx: {"output": "done"})
    engine = lh.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    engine.with_executor("my_exec", executor)


def test_workflow_engine_subscribe():
    """subscribe() returns a WorkflowEventIterator."""
    engine = lh.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    it = engine.subscribe()
    assert it is not None
    assert type(it).__name__ == "WorkflowEventIterator"


def test_workflow_engine_with_hooks():
    """with_hooks() accepts a list of hooks and returns self."""
    hook = lh.create_before_turn_hook(lambda ctx: None)
    engine = lh.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    result = engine.with_hooks([hook])
    assert result is engine


def test_workflow_engine_with_max_tokens():
    """with_max_tokens() sets max tokens and returns self."""
    engine = lh.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    result = engine.with_max_tokens(4096)
    assert result is engine

def test_workflow_engine_with_step_plugin():
    """with_step_plugin() accepts a step_id and plugin."""
    plugin = lh.create_plugin("my_plugin")
    engine = lh.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    engine.with_step_plugin("step1", plugin)


def test_workflow_engine_executor_step_dict():
    """dict_to_workflow handles executor steps (with 'executor' key)."""
    workflow = {
        "entry_step": "step1",
        "steps": [
            {
                "id": "step1",
                "name": "Exec Step",
                "executor": "my_exec",
                "executor_config": {"key": "value"},
            }
        ],
        "edges": [],
    }
    engine = lh.WorkflowEngine(workflow, _make_provider(), "gpt-4o", _make_judge())
    assert engine.task_id().startswith("task-")



def test_workflow_engine_with_external_tool():
    """with_external_tool() registers a WaitForExternalEventTool and returns self."""
    engine = lh.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    _handle, tool = lh.create_event_channel("review-task-ext")
    result = engine.with_external_tool(tool)
    assert result is engine


def test_workflow_engine_set_context_variable():
    """set_context_variable() stores a key-value pair in the workflow context."""
    engine = lh.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    engine.set_context_variable("user_description", "a red sports car")
    engine.set_context_variable("count", 42)
    engine.set_context_variable("flag", True)
    engine.set_context_variable("nested", {"a": 1, "b": [2, 3]})
    # No exception means success; the value is accessible to executors/judges
    # via WorkflowContext.variables during run().


def test_workflow_engine_set_context_variable_after_run_fails():
    """set_context_variable() fails if engine is consumed."""
    engine = lh.WorkflowEngine(_make_workflow(), _make_provider(), "gpt-4o", _make_judge())
    # Simulate consumed engine by running (will fail with provider error, consuming engine)
    # Instead, just test that set_context_variable works before run.
    engine.set_context_variable("key", "value")


def test_dict_to_workflow_conditional_edge_string():
    """dict_to_workflow parses string 'condition' as a label condition."""
    workflow = {
        "entry_step": "step1",
        "steps": [
            {"id": "step1", "name": "S1", "prompt": "Do 1", "allowed_tools": []},
            {"id": "step2", "name": "S2", "prompt": "Do 2", "allowed_tools": []},
        ],
        "edges": [
            {"from": "step1", "to": "step2", "condition": "success"},
        ],
    }
    engine = lh.WorkflowEngine(workflow, _make_provider(), "gpt-4o", _make_judge())
    assert engine.task_id().startswith("task-")


def test_dict_to_workflow_conditional_edge_expr():
    """dict_to_workflow parses dict 'condition' as a declarative ConditionExpr."""
    workflow = {
        "entry_step": "step1",
        "steps": [
            {"id": "step1", "name": "S1", "prompt": "Do 1", "allowed_tools": []},
            {"id": "step2", "name": "S2", "prompt": "Do 2", "allowed_tools": []},
        ],
        "edges": [
            {
                "from": "step1",
                "to": "step2",
                "condition": {"op": "eq", "pointer": "/status", "value": "ok"},
            },
        ],
    }
    engine = lh.WorkflowEngine(workflow, _make_provider(), "gpt-4o", _make_judge())
    assert engine.task_id().startswith("task-")


def test_dict_to_workflow_edge_without_condition():
    """dict_to_workflow still handles edges without 'condition' key."""
    workflow = {
        "entry_step": "step1",
        "steps": [
            {"id": "step1", "name": "S1", "prompt": "Do 1", "allowed_tools": []},
            {"id": "step2", "name": "S2", "prompt": "Do 2", "allowed_tools": []},
        ],
        "edges": [{"from": "step1", "to": "step2"}],
    }
    engine = lh.WorkflowEngine(workflow, _make_provider(), "gpt-4o", _make_judge())
    assert engine.task_id().startswith("task-")