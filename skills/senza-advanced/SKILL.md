---
name: senza-advanced
description: >-
  Advanced Senza patterns: sub-agent spawning, human-in-the-loop, hooks,
  event streaming, and crash recovery. Use when the user wants to:
  (1) spawn sub-agents from an LLM step for parallel work,
  (2) pause/resume or cancel a running workflow,
  (3) inject human review via event channels,
  (4) add hooks (before_tool_call, should_stop, before_compact, etc.),
  (5) stream workflow events for monitoring,
  (6) build plugins that bundle tools + hooks,
  (7) use spawn_agent + message_subagent + await_subagent_reply for
  multi-agent orchestration.
  Trigger phrases: "sub-agent", "spawn_agent", "human in the loop",
  "hooks", "pause resume", "event streaming", "plugin", "MessageBus",
  "multi-agent", "crash recovery".
---

# Senza Advanced — Sub-Agents, Hooks, Human-in-the-Loop

> SDK: `import llm_harness_py as L`
> Prerequisites: read `senza-agent` and `senza-workflow` skills first.

## Sub-Agent Spawning (7 LLM Tools)

When an LLM step's `allowed_tools` includes `"spawn_agent"`, the engine auto-registers **7 tools** + a MessageBus for main↔sub async communication. No extra setup needed.

```python
workflow = {
    "entry_step": "orchestrator",
    "steps": [{
        "id": "orchestrator",
        "name": "编排者",
        "prompt": "分析任务，派发 sub-agent 并行处理，汇总结果",
        "allowed_tools": ["spawn_agent"],  # ← triggers 7-tool registration
    }],
    "edges": [],
}
```

### The 7 Tools

| Tool | Direction | Params | Description |
|------|-----------|--------|-------------|
| `spawn_agent` | main→sub | `prompt`(req), `context`?, `provider`? | Async spawn, returns `agent_id` immediately |
| `message_subagent` | main→sub | `to`(req), `message`(req) | Fire-and-forget message to sub-agent |
| `await_subagent_reply` | main waits | `from`?, `timeout`?(120s) | Block until sub-agent message/completion |
| `query_subagent` | main→bus | `agent_id`? | Query status (running/done/aborted) |
| `abort_subagent` | main→sub | `agent_id`(req) | Cancel a sub-agent |
| `message_main` | sub→main | `message`(req) | Sub-agent reports to main |
| `await_main_message` | sub waits | `timeout`?(120s) | Sub-agent waits for main instruction |

### Key Mechanisms

- **MessageBus**: unified event channel. `register`/`send`/`wait`/`query_status`/`abort_agent`.
- **AsyncSpawnHook** (ShouldStop hook): sub-agent completion events injected into main agent's conversation.
- **IdleWatcher**: when bus has no in-flight events, triggers `harness.continue_run()`.
- **AbortCascadeHook**: step abort cascades to cancel all sub-agents.
- Spawn is **asynchronous** — `spawn_agent` returns immediately with `agent_id`. Results arrive via `await_subagent_reply`.

### Pattern: parallel sub-agent fan-out

```python
# LLM prompt instructs the model to:
# 1. Call spawn_agent twice with different prompts
# 2. Call await_subagent_reply to collect results
# 3. Synthesize final answer

prompt = """
You have 2 sub-tasks. For each:
1. Call spawn_agent with the task prompt
2. After spawning both, call await_subagent_reply (no `from` arg) twice
3. Combine results into final answer
"""
```

## Hooks (11 Types)

Hooks intercept the agent loop at specific points. Create with `create_*_hook()`, register with `engine.with_hooks([h1, h2, ...])` or `builder.plugin(plugin_with_hooks)`.

### Available Hooks

| Function | When | Callback | Return |
|----------|------|----------|--------|
| `create_before_turn_hook(cb)` | Before each LLM turn | `ctx: dict` | `None` |
| `create_after_turn_hook(cb)` | After each LLM turn | `ctx: dict` | `None` |
| `create_before_run_hook(cb)` | Before agent loop starts | `ctx: dict` | `None` |
| `create_after_provider_response_hook(cb)` | After LLM response | `ctx: dict` | `None` |
| `create_before_provider_request_hook(cb)` | Before LLM request | `ctx: dict` | `None` |
| `create_before_tool_call_hook(cb)` | Before tool execution | `ctx: dict` | `str \| None` (block reason) |
| `create_after_tool_call_hook(cb)` | After tool execution | `ctx: dict` | `str \| dict` (patch result) |
| `create_should_stop_hook(cb)` | Check if loop should stop | `ctx: dict` | `bool` |
| `create_before_compact_hook(cb)` | Before context compaction | `ctx: dict` | `str \| dict` (proceed/skip/override) |
| `create_transform_context_hook(cb)` | Transform messages before LLM | `ctx: dict` | `dict` (new system_prompt + messages) |
| `create_prepare_next_turn_hook(cb)` | Before each turn setup | `ctx: dict` | `dict \| None` (model/thinking_level/temperature/active_tools) |

All hooks support `async def` callbacks.

### Pattern: block dangerous tools

```python
def guard(ctx):
    tool_name = ctx.get("tool_name", "")
    if tool_name in ("rm", "format"):
        return f"blocked: {tool_name} not allowed"
    return None  # allow

hook = L.create_before_tool_call_hook(guard)
engine = L.WorkflowEngine(workflow, provider, "gpt-4o", judge).with_hooks([hook])
```

### Pattern: force stop after N turns

```python
turn_count = [0]
def stop_after_5(ctx):
    turn_count[0] += 1
    return turn_count[0] >= 5

hook = L.create_should_stop_hook(stop_after_5)
```

## Human-in-the-Loop (Event Channel)

```python
# 1. Create channel
handle, wait_tool = L.create_event_channel("review-task-001")

# 2. Register the wait tool — LLM can call it to pause for human input
engine = (
    L.WorkflowEngine(workflow, provider, "gpt-4o", judge)
    .with_external_tool(wait_tool)
)

# 3. In another thread/coroutine, push events
handle.submit("审核通过", {"approved": True, "reviewer": "alice"})
handle.submit("需要修改", {"approved": False, "feedback": "fix section 3"})
```

The LLM calls `wait_for_external_event` tool → blocks until `handle.submit()` is called → receives the submitted content as tool result.

## Plugins (Bundled Tools + Hooks)

```python
# Create tools
tool1 = L.create_tool("search", "Search", schema_json, search_callback)
tool2 = L.create_tool("write", "Write file", schema_json, write_callback)

# Create hooks
guard_hook = L.create_before_tool_call_hook(guard_fn)

# Bundle into a plugin
plugin = L.create_plugin(
    name="my_plugin",
    tools=[tool1, tool2],
    hooks=[guard_hook],
)

# Register with engine or builder
engine = L.WorkflowEngine(workflow, provider, "gpt-4o", judge)
engine.with_step_plugin("step1", plugin)  # per-step
# or
harness = L.HarnessBuilder("gpt-4o").provider("gpt-*", provider).plugin(plugin).build()
```

## Event Streaming

### Agent-level events (HarnessBuilder)

```python
harness.prompt("Analyze this")
for event in harness.events(timeout_ms=5000):
    t = event["type"]
    if t == "text_delta":
        print(event["text"], end="")
    elif t == "tool_call_start":
        print(f"\n[tool: {event.get('tool_name')}]")
    elif t == "settled":
        break
```

### Workflow-level events (WorkflowEngine)

```python
event_iter = engine.subscribe(timeout_ms=5000)
# In a monitoring thread:
for event in event_iter:
    t = event["type"]
    if t == "step_started":
        print(f"→ {event['step_name']}")
    elif t == "step_finished":
        print(f"✓ {event['step_id']}: {event['output'][:80]}")
    elif t == "failed":
        print(f"✗ {event['error']}")
```

