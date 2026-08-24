"""32 — Plugins: bundle tools and hooks into a reusable unit.

Mirrors runtime `examples/agent/10_plugins.py`. Demonstrates:
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

Scenario: a ``db-safety`` plugin that bundles a ``run_query`` tool with a
``before_tool_call`` hook that makes all three supported decisions:
``"allow"`` for unrelated safe tools, ``{"action": "modify"}`` to add a row
limit to an unbounded SELECT, and ``{"action": "deny"}`` to prevent non-SELECT
SQL from reaching the executor. The SQL check is deliberately small and
illustrative; production policy should use a real parser or database controls.

Run:
  source ~/.omp_llm_env && python live-tests/examples/32_plugins.py
"""

import json
import re
import sys

import senza
from _common import live_model, make_example_harness, require_provider

# ── Plugin definition ────────────────────────────────────────────────────────

executed_queries: list[str] = []
guard_decisions: list[tuple[str, str]] = []


# A sync tool (create_sync_tool is an explicit alias for create_tool;
# create_tool auto-detects async def callbacks — use whichever reads best).
def run_query(args, ctx):
    sql = args.get("sql", "")
    executed_queries.append(sql)
    return {
        "content": [{"type": "text", "text": f"Executed: {sql}\n(rows affected: 42)"}],
        "terminate": False,
    }


query_tool = senza.create_sync_tool(
    name="run_query",
    description="Execute a read-only SQL query against the database.",
    parameters_schema=json.dumps(
        {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL statement to execute"},
            },
            "required": ["sql"],
        }
    ),
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
    parameters_schema=json.dumps({"type": "object", "properties": {}}),
    callback=check_status,
)


def query_guard(ctx):
    """BeforeToolCall hook: allow, modify, or deny before execution."""
    tool_name = ctx.get("tool_name", "?")
    args = ctx.get("args", {})
    sql = args.get("sql", "")

    print(f"  [plugin hook] {tool_name} called with sql={sql!r}")

    if tool_name != "run_query":
        guard_decisions.append((tool_name, "allow"))
        print("  [plugin hook] ALLOW non-query tool")
        return "allow"

    if not re.match(r"^\s*SELECT\b", sql, flags=re.IGNORECASE):
        guard_decisions.append((tool_name, "deny"))
        print("  [plugin hook] DENY non-read-only SQL")
        return {
            "action": "deny",
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "Query denied by db-safety: only SELECT is permitted.",
                    }
                ],
                "details": {"reason": "non_read_only_sql", "sql": sql},
            },
        }

    if not re.search(r"\bLIMIT\s+\d+\b", sql, flags=re.IGNORECASE):
        limited_sql = f"{sql.rstrip().rstrip(';')} LIMIT 100"
        modified_args = dict(args)
        modified_args["sql"] = limited_sql
        guard_decisions.append((tool_name, "modify"))
        print(f"  [plugin hook] MODIFY query to {limited_sql!r}")
        return {"action": "modify", "args": modified_args}

    guard_decisions.append((tool_name, "allow"))
    print("  [plugin hook] ALLOW bounded SELECT")
    return "allow"


guard_hook = senza.hooks.before_tool_call(query_guard)


def make_db_safety_plugin() -> "senza.Plugin":
    """Create the reusable db-safety plugin (tools + hooks bundled)."""
    return senza.create_plugin(
        name="db-safety",
        tools=[query_tool, status_tool],
        hooks=[guard_hook],
    )


# ── Agent-layer usage ────────────────────────────────────────────────────────


def demo_agent_layer():
    print("=" * 60)
    print("Agent layer: HarnessBuilder.plugin()")
    print("=" * 60)

    harness = make_example_harness(
        lambda b: (
            b.system_prompt(
                "You are a database assistant. Use run_query for SQL and "
                "check_db_status for health checks. For this safety demo, pass "
                "the user's requested SQL to run_query exactly as written; the "
                "installed plugin is solely responsible for policy enforcement."
            )
            .plugin(make_db_safety_plugin())
            .max_tokens(512)
        )
    )

    print(f"\nPlugin name: {make_db_safety_plugin().name}")

    print("\nAsking the model to check DB status (async tool)...")
    events = harness.prompt_and_collect("Check the database status for me.", timeout_ms=60_000)
    _print_events(events)

    print("\nAsking for an unbounded SELECT (hook should modify it)...")
    events = harness.prompt_and_collect(
        "Call run_query exactly once with this SQL: SELECT * FROM users",
        timeout_ms=60_000,
    )
    _print_events(events)
    print(f"Executor received: {executed_queries[-1] if executed_queries else '<nothing>'}")

    print("\nAsking for a DROP (hook should deny before execution)...")
    executed_before = len(executed_queries)
    events = harness.prompt_and_collect(
        "Call run_query exactly once with this SQL: DROP TABLE users",
        timeout_ms=60_000,
    )
    _print_events(events)
    print(f"Executor ran denied query: {len(executed_queries) != executed_before}")
    print(f"Hook decisions observed: {guard_decisions}")


# ── Workflow-layer usage ─────────────────────────────────────────────────────


def demo_workflow_layer(provider):
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

    def judge(ctx):
        step = ctx.get("step_id", "")
        return "to:done" if step == "query" else "done"

    engine = (
        senza.WorkflowEngine(
            workflow,
            provider,
            live_model(),
            senza.create_judge(judge),
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


def main() -> None:
    provider = require_provider()
    demo_agent_layer()
    demo_workflow_layer(provider)


if __name__ == "__main__":
    main()
