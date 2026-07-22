"""10 — Plugins: bundle tools and hooks into a reusable unit.

Demonstrates:
  - ``create_plugin(name, tools, hooks)`` — package tools + hooks together
  - ``HarnessBuilder.plugin()`` — install a plugin on an agent
  - ``WorkflowEngine.with_step_plugin()`` — install a plugin scoped to one
    workflow step (the plugin's tools/hooks only activate for that step)
  - ``create_sync_tool()`` — explicit alias for ``create_tool()`` (auto-
    detects ``async def`` callbacks); shown alongside an async tool to
    illustrate both patterns

A Plugin is a bundle: when installed, its tools are added to the tool
registry and its hooks are distributed to the matching hook vectors.
This is cleaner than registering each tool and hook individually,
especially when the same tool+hook combination is reused across agents
or workflow steps.

Scenario: a ``db-safety`` plugin that bundles a ``run_query`` tool with
a ``before_tool_call`` hook that logs every query and blocks destructive
operations (DROP / DELETE without WHERE). The same plugin is then scoped
to a single workflow step via ``with_step_plugin``.

Prerequisites:
  - Set OPENAI_API_KEY env var

Run:
  python 10_plugins.py
"""
import json
import os
import re
import sys

import senza


# ── Plugin definition ────────────────────────────────────────────────────────

# A sync tool (create_sync_tool is an explicit alias for create_tool;
# create_tool auto-detects async def callbacks — use whichever reads best).
def run_query(args, ctx):
    sql = args.get("sql", "")
    return {
        "content": [{"type": "text", "text": f"Executed: {sql}\n(rows affected: 42)"}],
        "terminate": False,
    }


query_tool = senza.create_sync_tool(
    name="run_query",
    description="Execute a read-only SQL query against the database.",
    parameters_schema=json.dumps({
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "SQL statement to execute"},
        },
        "required": ["sql"],
    }),
    callback=run_query,
)


# An async tool — create_tool detects the coroutine and runs it via
# asyncio.run on a blocking thread, so no extra event loop is needed.
async def check_status(args, ctx):
    return {
        "content": [{"type": "text", "text": "Database status: healthy, 5 connections active."}],
        "terminate": False,
    }


status_tool = senza.create_tool(
    name="check_db_status",
    description="Check the health and connection count of the database (async).",
    parameters_schema=json.dumps({
        "type": "object",
        "properties": {},
    }),
    callback=check_status,
)


def query_guard(ctx):
    """BeforeToolCall hook: log queries and block destructive SQL."""
    tool_name = ctx.get("tool_name", "?")
    args = ctx.get("args", {})
    sql = args.get("sql", "")

    print(f"  [plugin hook] {tool_name} called with sql={sql!r}")

    if tool_name == "run_query":
        upper = sql.upper().strip()
        # Block DROP / TRUNCATE / DELETE without WHERE
        if re.search(r"\b(DROP|TRUNCATE)\b", upper):
            print(f"  [plugin hook] BLOCKED destructive statement")
            return {
                "action": "deny",
                "result": {
                    "content": [{"type": "text", "text": "Destructive operations are blocked."}],
                    "terminate": False,
                },
            }
        if re.search(r"\bDELETE\b", upper) and "WHERE" not in upper:
            print(f"  [plugin hook] BLOCKED DELETE without WHERE")
            return {
                "action": "deny",
                "result": {
                    "content": [{"type": "text", "text": "DELETE without WHERE is blocked."}],
                    "terminate": False,
                },
            }

    return "allow"


guard_hook = senza.create_before_tool_call_hook(query_guard)


def make_db_safety_plugin() -> "senza.Plugin":
    """Create the reusable db-safety plugin (tools + hooks bundled)."""
    return senza.create_plugin(
        name="db-safety",
        tools=[query_tool, status_tool],
        hooks=[guard_hook],
    )


# ── Agent-layer usage ────────────────────────────────────────────────────────

def demo_agent_layer(provider, model):
    print("=" * 60)
    print("Agent layer: HarnessBuilder.plugin()")
    print("=" * 60)

    harness = (
        senza.HarnessBuilder(model)
        .provider("*", provider)
        .system_prompt(
            "You are a database assistant. Use run_query for SQL and "
            "check_db_status for health checks."
        )
        .plugin(make_db_safety_plugin())
        .max_tokens(512)
        .build()
    )

    print(f"\nPlugin name: {make_db_safety_plugin().name}")

    print("\nAsking the model to check DB status (async tool)...")
    events = harness.prompt_and_collect(
        "Check the database status for me.", timeout_ms=30000
    )
    _print_events(events)


# ── Workflow-layer usage ─────────────────────────────────────────────────────

def demo_workflow_layer(provider, model):
    print("\n" + "=" * 60)
    print("Workflow layer: WorkflowEngine.with_step_plugin()")
    print("=" * 60)

    workflow = {
        "entry_step": "query",
        "steps": [
            {
                "id": "query",
                "name": "查询",
                "prompt": "Run this query: SELECT * FROM users LIMIT 5",
                "allowed_tools": [],
            },
            {
                "id": "done",
                "name": "总结",
                "prompt": "Summarize the query results in one sentence.",
                "allowed_tools": [],
            },
        ],
        "edges": [{"from": "query", "to": "done"}],
    }

    judge = senza.create_judge(lambda ctx: "to:done" if ctx.get("step_id") == "query" else "done")

    engine = (
        senza.WorkflowEngine(
            workflow_dict=workflow,
            provider=provider,
            model=model,
            judge=judge,
        )
        .with_step_plugin("query", make_db_safety_plugin())
        .with_max_steps(10)
    )

    print("\nRunning workflow (plugin scoped to 'query' step)...")
    engine.run()

    history = engine.step_history()
    print(f"\nSteps executed: {len(history)}")
    for step in history:
        print(f"  - {step.get('step_id', '?')}: {step.get('state', '?')}")


def _print_events(events):
    text = ""
    for event in events:
        t = event["type"]
        if t == "text_delta":
            text += event.get("text", "")
        elif t == "error":
            print(f"\n[error] {event.get('message', event)}", file=sys.stderr)
            sys.exit(1)
    print(f"Response:\n{text}")


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)
    model = os.environ.get("SENZA_MODEL", "gpt-4o")

    demo_agent_layer(provider, model)
    demo_workflow_layer(provider, model)


if __name__ == "__main__":
    main()
