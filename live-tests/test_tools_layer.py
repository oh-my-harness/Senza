"""Tools layer live tests: fs tools, grep/glob, knowledge RAG + memory, session recall."""

import os
import tempfile

import senza
from base import assert_settled, assert_tool_called, make_harness, provider_or_skip, run_prompt


def test_fs_tools_read_write():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "note.txt"), "w") as f:
            f.write("the magic number is 42")
        h = make_harness(
            provider_or_skip(),
            lambda b: b.plugin(senza.create_fs_tools_plugin()).env(senza.create_os_env(d)),
        )
        ev = run_prompt(h, "Use the read tool to read note.txt and report the number.")
        assert_settled(ev)
        assert_tool_called(ev, "read")


def test_grep_glob():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "a.py"), "w") as f:
            f.write("def main(): pass\n")
        h = make_harness(
            provider_or_skip(),
            lambda b: b.plugin(senza.create_fs_tools_plugin()).env(senza.create_os_env(d)),
        )
        ev = run_prompt(h, "Use glob to list the *.py files in the working directory.")
        assert_settled(ev)
        assert_tool_called(ev, "glob")


def _tool_result_texts(events) -> list[str]:
    """Extract text from all tool_execution_end events.

    `tool_execution_end` carries a nested `result` dict with a `text` field
    (the flat ToolResult). This helper unwraps it.
    """
    texts = []
    for e in events:
        if e.get("type") != "tool_execution_end":
            continue
        result = e.get("result")
        if isinstance(result, dict):
            texts.append(result.get("text", ""))
        elif not e.get("ok", True):
            texts.append(e.get("error", ""))
    return texts


def test_knowledge_memory():
    """knowledge_search must succeed from Python (not return 'unauthorized').

    Regression test: before KnowledgeAccessContext injection, every
    knowledge tool call from Python returned 'unauthorized' because the
    run request carried no access extension. This test verifies the
    default trusted context is injected on every run.
    """
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "guide.md"), "w") as f:
            f.write("Senza is an agent runtime. The deployment command is `senza deploy`.")
        source = senza.knowledge.local_source(path=d, source_id="guide")
        plugin = senza.knowledge.plugin(sources=[source])
        h = make_harness(
            provider_or_skip(),
            lambda b: b.system_prompt(
                "Use the knowledge_search tool to find information, then answer."
            ).plugin(plugin),
        )
        ev = run_prompt(h, "Search the knowledge source for the deployment command.")
        assert_settled(ev)
        assert_tool_called(ev, "knowledge_search")
        # The tool must not have returned 'unauthorized' — the bug fixed by
        # KnowledgeAccessContext injection.
        tool_texts = _tool_result_texts(ev)
        joined = " ".join(tool_texts).lower()
        assert "unauthorized" not in joined, (
            f"knowledge_search returned 'unauthorized' — access context not injected: {tool_texts}"
        )


def test_knowledge_access_configurable():
    """knowledge_access(scope, principal, kind) must propagate to the run.

    Verifies that a custom access context set via HarnessBuilder does not
    break the knowledge_search path — the custom principal/scope is accepted
    by the runtime's authorization layer and the tool still succeeds.
    """
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "guide.md"), "w") as f:
            f.write("The deployment command is `senza deploy --env prod`.")
        source = senza.knowledge.local_source(path=d, source_id="guide")
        plugin = senza.knowledge.plugin(sources=[source])
        h = make_harness(
            provider_or_skip(),
            lambda b: b.system_prompt(
                "Use the knowledge_search tool to find information, then answer."
            )
            .knowledge_access(scope="myapp", principal="test-user", kind="user")
            .plugin(plugin),
        )
        ev = run_prompt(h, "Search the knowledge source for the deployment command.")
        assert_settled(ev)
        assert_tool_called(ev, "knowledge_search")
        tool_texts = _tool_result_texts(ev)
        joined = " ".join(tool_texts).lower()
        assert "unauthorized" not in joined, (
            f"knowledge_search returned 'unauthorized' with custom access context: {tool_texts}"
        )


def test_session_recall():
    repo = senza.knowledge.in_memory_session_repo()
    index = senza.knowledge.sqlite_session_recall_index(
        path=os.path.join(tempfile.mkdtemp(), "recall.db")
    )
    source = senza.knowledge.session_recall_knowledge_source(repo=repo, index=index)
    plugin = senza.knowledge.history_recall_plugin(source=source)
    h = make_harness(provider_or_skip(), lambda b: b.plugin(plugin))
    ev = run_prompt(h, "Say hello.")
    assert_settled(ev)


def test_tools_constructs_offline():
    """No key needed; validates fs-tools + knowledge construction."""
    stub = senza.providers.openai(api_key="sk-test")
    src = senza.knowledge.local_source(path=".", source_id="x")
    plugin = senza.knowledge.plugin(sources=[src])
    env_h = make_harness(
        stub, lambda b: b.plugin(senza.create_fs_tools_plugin()).env(senza.create_os_env("."))
    )
    k_h = make_harness(stub, lambda b: b.plugin(plugin))
    assert env_h is not None and k_h is not None and env_h.phase() == "idle"


# ── Event stream tests (mirrors runtime tools_layer/event_stream.rs) ──────
# All 4 are skipped: GLM streaming bug — WaitForExternalEventTool has empty
# properties schema, LLM won't emit tool_call chunk. Same as runtime #[ignore].

import pytest


@pytest.mark.skip(reason="GLM streaming bug: empty properties schema")
def test_timer_stream():
    """TimerStream::once fires after delay; LLM calls wait_for_external_event."""
    provider = provider_or_skip()
    (tool,) = senza.create_timer_stream(delay_ms=2000, label="test-timer", task_id="task1")
    h = make_harness(provider, lambda b: b.tool(tool))
    ev = run_prompt(
        h,
        "Use the wait_for_external_event tool to wait for a scheduled timer event. "
        "After the tool returns, tell me what happened.",
        timeout_ms=120_000,
    )
    assert_settled(ev)
    assert_tool_called(ev, "wait_for_external_event")


@pytest.mark.skip(reason="GLM streaming bug: empty properties schema")
def test_webhook_stream():
    """WebhookStream receives externally-pushed payload."""
    import threading
    import time

    provider = provider_or_skip()
    handle, tool = senza.create_event_channel(task_id="task1")

    def push_later():
        time.sleep(1)
        handle.submit("test-event", {"event": "test"})

    threading.Thread(target=push_later, daemon=True).start()
    h = make_harness(provider, lambda b: b.tool(tool))
    ev = run_prompt(
        h,
        "Use the wait_for_external_event tool to wait for an external event. "
        "After the tool returns, tell me what happened.",
        timeout_ms=120_000,
    )
    assert_settled(ev)
    assert_tool_called(ev, "wait_for_external_event")


@pytest.mark.skip(reason="GLM streaming bug: empty properties schema")
def test_heartbeat_stream():
    """HeartbeatStream fires when tick() is never called."""
    provider = provider_or_skip()
    handle, tool = senza.create_heartbeat_stream(
        timeout_ms=3000, label="test-heartbeat", task_id="task1"
    )
    h = make_harness(provider, lambda b: b.tool(tool))
    ev = run_prompt(
        h,
        "Use the wait_for_external_event tool to wait for a heartbeat event. "
        "After the tool returns, tell me what happened.",
        timeout_ms=120_000,
    )
    assert_settled(ev)
    assert_tool_called(ev, "wait_for_external_event")


@pytest.mark.skip(reason="GLM streaming bug: empty properties schema")
def test_shell_monitor_stream():
    """ShellMonitorStream captures stdout from a shell command."""
    provider = provider_or_skip()
    handle, tool = senza.create_shell_monitor_stream(
        command="echo hello-from-shell",
        cwd=None,
        label="test-shell",
        task_id="task1",
    )
    h = make_harness(provider, lambda b: b.tool(tool))
    ev = run_prompt(
        h,
        "Use the wait_for_external_event tool to wait for shell output. "
        "After the tool returns, tell me what happened.",
        timeout_ms=120_000,
    )
    assert_settled(ev)
    assert_tool_called(ev, "wait_for_external_event")


@pytest.mark.skip(reason="requires MCP server (npx @modelcontextprotocol/server-everything)")
def test_mcp_tool_discovery():
    """MCP tools are discovered from a stdio MCP server."""
    manager = senza.McpManager()
    config = senza.McpServerConfig.stdio(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-everything"],
    )
    manager.add_server("everything", config)
    # Wait for server initialization
    import time

    time.sleep(3)
    tools = manager.list_tools()
    assert len(tools) >= 1, f"expected >=1 MCP tool, got {len(tools)}"
    for tool_name in tools:
        assert tool_name, f"empty tool name: {tool_name}"
    manager.disconnect_all()
