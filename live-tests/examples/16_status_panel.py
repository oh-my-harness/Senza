"""16 — Status Panel: status_panel() plugin (todo_write + tool counter).

Mirrors runtime `16_status_panel.rs`. The `StatusPanelPlugin` registers, in one
install: a `todo_write` tool backed by an in-memory `TodoStore`, a
`StatusBarHook` that injects an `<agent_status>` XML block at the end of the
LLM context each turn (rendering the todo list + environment + per-tool call
counts), and a `ToolCallCounterHook` that counts every tool execution.

Demonstrates:
  - Part 1: attach `senza.strategy.status_panel()` via `builder.plugin(p)` and
    prompt the LLM to use `todo_write` to create a 3-item todo list.
  - Part 2: prompt the LLM to update/complete two todos with `todo_write`.
  - Part 3: run a conversation with multiple `echo` calls and show the
    `ToolCallCounter` tracks per-tool counts inside the rendered status bar.

Feature gap: in Rust the example inspects the plugin's stores directly
(`plugin.todo_store().clone()` / `.tool_counter().clone()`). Senza's Python
surface exposes the plugin as an opaque `Plugin` returned by
`senza.strategy.status_panel()` (no `todo_store()` / `tool_counter()`
accessor). The nearest analog is to read the same data the LLM sees: the
`<agent_status>` block the `StatusBarHook` injects into the context each turn,
which is persisted in the harness message log and reachable via
`harness.get_messages()`. We parse `<todo_list>` / `<tool_calls>` from the most
recent status message.

Run:
  source ~/.omp_llm_env && python live-tests/examples/16_status_panel.py
"""

import json
import re

import senza
from _common import make_example_harness, require_provider, run_prompt


def _echo(args, ctx):
    return {
        "content": [{"type": "text", "text": args.get("message", "(no message)")}],
        "terminate": False,
    }


def _status_texts(harness):
    """Return the text of every injected `<agent_status>` user message."""
    texts = []
    for msg in harness.get_messages():
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if text.lstrip().startswith("<agent_status>"):
                    texts.append(text)
    return texts


def _todos(harness):
    """Collected `<todo_list>` items: [(id, status, content)] from the latest status."""
    texts = _status_texts(harness)
    if not texts:
        return []
    return [
        (item_id, status, content)
        for (item_id, status, content) in re.findall(
            r'<item id="([^"]*)" status="([^"]*)">(.*?)</item>', texts[-1]
        )
    ]


def _tool_counts(harness):
    """Per-tool call counts from the latest status `<tool_calls>` block."""
    texts = _status_texts(harness)
    if not texts:
        return {}
    return {
        name: int(count)
        for (name, count) in re.findall(r'<call tool="([^"]*)" count="(\d+)"/>', texts[-1])
    }


def _tool_called(events, name):
    return any(
        e.get("type") in ("tool_call_start", "tool_execution_start") and e.get("tool_name") == name
        for e in events
    )


def _print_todos(label, todos):
    print(f"{label} ({len(todos)} items):")
    for item_id, status, content in todos:
        print(f"  [{item_id}] {content} — {status}")


def _build(plugin, system_prompt=None, tools=()):
    def customize(b):
        b = b.plugin(plugin)
        for t in tools:
            b = b.tool(t)
        if system_prompt:
            b = b.system_prompt(system_prompt)
        return b

    return make_example_harness(customize)


def part1_todo_create():
    print("--- Part 1: status_panel() + todo_write (create) ---\n")
    harness = _build(
        senza.strategy.status_panel(),
        system_prompt="You have a todo_write tool. Use it to manage a 3-item todo list in action 'rewrite'.",
    )
    prompt = (
        "Use the todo_write tool with action 'rewrite' to create a todo list "
        "with exactly 3 items, each with a unique id and status 'pending': "
        "id '1' = 'Write tests', id '2' = 'Run tests', id '3' = 'Deploy'. "
        "Then reply 'done'."
    )
    print(f"LLM prompt: {prompt}\n")
    events = run_prompt(harness, prompt, timeout_ms=60_000)

    todos = _todos(harness)
    called = _tool_called(events, "todo_write")
    print("\nTodos collected from <agent_status>:")
    _print_todos("TodoStore", todos)
    print("\nObservation:")
    print(f"  todo_write called: {called}")
    print("  status bar renders <todo_list> from the store each turn")


def part2_todo_update():
    print("\n--- Part 2: todo_write (update/complete) ---\n")
    harness = _build(
        senza.strategy.status_panel(),
        system_prompt="You have a todo_write tool. Use action 'rewrite' to create todos and 'update' to change a single item's status.",
    )
    create = (
        "Use todo_write with action 'rewrite' to create 3 pending items: "
        "id '1' = 'Write tests', id '2' = 'Run tests', id '3' = 'Deploy'. "
        "Then reply 'created'."
    )
    run_prompt(harness, create, timeout_ms=60_000)
    print(f"LLM prompt 1: {create}\n")
    _print_todos("After create", _todos(harness))

    update = (
        "Now use todo_write with action 'update' to mark item id '1' as "
        "'completed' and item id '2' as 'in_progress'. Keep item '3' as "
        "'pending'. Then reply 'updated'."
    )
    print(f"\nLLM prompt 2: {update}\n")
    events = run_prompt(harness, update, timeout_ms=60_000)

    todos = _todos(harness)
    by_id = {item_id: status for (item_id, status, _content) in todos}
    print("\nTodos collected after update:")
    _print_todos("TodoStore", todos)
    print("\nObservation:")
    print(f"  todo_write called (update): {_tool_called(events, 'todo_write')}")
    print(f"  item 1 status: {by_id.get('1')}")
    print(f"  item 2 status: {by_id.get('2')}")


def part3_tool_counter():
    print("\n--- Part 3: ToolCallCounter (multiple echo calls) ---\n")
    echo_tool = senza.create_tool(
        name="echo",
        description="Echo back the provided message verbatim.",
        parameters_schema=json.dumps(
            {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            }
        ),
        callback=_echo,
    )
    harness = _build(
        senza.strategy.status_panel(),
        system_prompt="You have an echo tool. Call it once per message.",
        tools=(echo_tool,),
    )
    prompt = (
        "Use the echo tool exactly three times with the messages 'first', "
        "'second', and 'third' — call the tool once for each message. "
        "Then reply 'done'."
    )
    print(f"LLM prompt: {prompt}\n")
    events = run_prompt(harness, prompt, timeout_ms=60_000)

    counts = _tool_counts(harness)
    echo_events = sum(
        1
        for e in events
        if e.get("type") in ("tool_call_start", "tool_execution_start")
        and e.get("tool_name") == "echo"
    )
    print("\nToolCallCounter (from <tool_calls> in status bar):")
    for name, count in sorted(counts.items()):
        print(f"  {name} — {count} call(s)")
    print("\nObservation:")
    print(f"  echo calls (events):   {echo_events}")
    print(f"  echo calls (counter):  {counts.get('echo', 0)}")
    print("  counter tracks every tool execution in the status bar")


def main() -> None:
    print("=== 16: Status Panel (status_panel() plugin) ===\n")
    require_provider()
    part1_todo_create()
    part2_todo_update()
    part3_tool_counter()
    print("\n--- Summary ---")
    print("Part 1: todo_write creates todos in the shared store")
    print("Part 2: todo_write updates todo statuses")
    print("Part 3: ToolCallCounter tracks per-tool call counts in <tool_calls>")


if __name__ == "__main__":
    main()
