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

> SDK: `import senza`
> Prerequisites: read `senza-agent` and `senza-workflow` skills first.

## Sub-Agent Spawning (5 Main-Side Tools Mounted by Default)

When an LLM step's `allowed_tools` includes `"spawn_agent"`, the engine registers a MessageBus and **5 management tools on the main agent**. The runtime protocol also defines 2 child-side reverse-communication tools, but Senza's current child factory returns `NoopPlugin`, so it does not mount those tools by default and it prevents recursive spawn.

```python
workflow = {
    "entry_step": "orchestrator",
    "steps": [
        {
            "id": "orchestrator",
            "name": "编排者",
            "prompt": "分析任务，派发 sub-agent 并行处理，汇总结果",
            "allowed_tools": ["spawn_agent"],  # ← mounts the 5 main-side tools
        }
    ],
    "edges": [],
}
```

### The 7 Protocol Tool Types (Only the Main 5 Are Mounted by Default)

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
- **AsyncSpawnHook** (AfterTurn hook): drains sub-agent events into the main agent's conversation.
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

## Hooks (12 Types)

Hooks intercept the agent loop at specific points. Create with `senza.hooks.*()`, register with `engine.with_hooks([h1, h2, ...])` or `builder.plugin(plugin_with_hooks)`.

### Available Hooks

| Function | When | Callback | Return |
|----------|------|----------|--------|
| `senza.hooks.before_turn(cb)` | Before each LLM turn | `ctx: dict` | `None` |
| `senza.hooks.after_turn(cb)` | After each LLM turn | `ctx: dict` | `None` |
| `senza.hooks.before_run(cb)` | Before agent loop starts | `ctx: dict` | `None` |
| `senza.hooks.after_provider_response(cb)` | After LLM response | `ctx: dict` | `None` |
| `senza.hooks.before_provider_request(cb)` | Before LLM request | `ctx: dict` | `None` |
| `senza.hooks.before_tool_call(cb)` | Before tool execution | `ctx: dict` | `str \| None` (block reason) |
| `senza.hooks.after_tool_call(cb)` | After tool execution | `ctx: dict` | `str \| dict` (patch result) |
| `senza.hooks.should_stop(cb)` | Check if loop should stop | `ctx: dict` | `bool` |
| `senza.hooks.before_compact(cb)` | Before context compaction | `ctx: dict` | `str \| dict` (proceed/skip/override) |
| `senza.hooks.transform_context(cb)` | Transform messages before LLM | `ctx: dict` | `dict` (new system_prompt + messages) |
| `senza.hooks.prepare_next_turn(cb)` | Before each turn setup | `ctx: dict` | `dict \| None` (model/thinking_level/temperature/active_tools) |
| `senza.hooks.final_answer_validator(cb)` | Before final answer is returned | `ctx: dict` | `None \| str \| dict` (reject/override) |

All hooks support `async def` callbacks.

### Pattern: block dangerous tools

```python
def guard(ctx):
    tool_name = ctx.get("tool_name", "")
    if tool_name in ("rm", "format"):
        return f"blocked: {tool_name} not allowed"
    return None  # allow


hook = senza.hooks.before_tool_call(guard)
engine = senza.WorkflowEngine(workflow, provider, "gpt-4o", judge).with_hooks([hook])
```

### Pattern: force stop after N turns

```python
turn_count = [0]


def stop_after_5(ctx):
    turn_count[0] += 1
    return turn_count[0] >= 5


hook = senza.hooks.should_stop(stop_after_5)
```

## Human-in-the-Loop (Event Channel)

```python
# 1. Create channel
handle, wait_tool = senza.create_event_channel("review-task-001")

# 2. Register the wait tool — LLM can call it to pause for human input
engine = senza.WorkflowEngine(workflow, provider, "gpt-4o", judge).with_external_tool(wait_tool)

# 3. In another thread/coroutine, push events
handle.submit("审核通过", {"approved": True, "reviewer": "alice"})
handle.submit("需要修改", {"approved": False, "feedback": "fix section 3"})
```

The LLM calls `wait_for_external_event` tool → blocks until `handle.submit()` is called → receives the submitted content as tool result.

## Plugins (Bundled Tools + Hooks)

```python
# Create tools
tool1 = senza.create_tool("search", "Search", schema_json, search_callback)
tool2 = senza.create_tool("write", "Write file", schema_json, write_callback)

# Create hooks
guard_hook = senza.hooks.before_tool_call(guard_fn)

# Bundle into a plugin
plugin = senza.create_plugin(
    name="my_plugin",
    tools=[tool1, tool2],
    hooks=[guard_hook],
)

# Register with engine or builder
engine = senza.WorkflowEngine(workflow, provider, "gpt-4o", judge)
engine.with_step_plugin("step1", plugin)  # per-step
# or
harness = senza.HarnessBuilder("gpt-4o").provider("gpt-*", provider).plugin(plugin).build()
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


## Strategy Plugins

`senza.strategy` exposes 10 Plugin factories plus 2 helpers. Only values returned by the Plugin factories are installed with `.plugin(...)`; the helpers return an event-stream pair or a compaction prompt pair.

| Kind | Function | Description |
|------|----------|-------------|
| SafetyDefaults | `senza.strategy.safety_defaults()` | Bash blacklist + path traversal guard |
| LoopSafety | `senza.strategy.loop_safety(config=None)` | Death-spiral / repetition / failure circuit breaker |
| StatusPanel | `senza.strategy.status_panel()` | Status bar + `todo_write` tool |
| MemoryDefense | `senza.strategy.memory_defense()` | Persistent memory injection defense |
| MemoryDefense (builder) | `MemoryDefensePluginBuilder().extra_file(name).build()` | Custom-file memory defense |
| InjectionFilter | `senza.strategy.injection_filter(patterns=None)` | Prompt injection detection |
| SourceTag | `senza.strategy.source_tag(entries)` | External content `<source>` wrapping |
| ProjectInstruction | `senza.strategy.project_instruction(env, config=None)` | Auto-inject CLAUDE.md etc |
| Audit | `senza.strategy.audit(sink_path, trace_id=None, task_id=None)` | Tool call audit log (JSONL) |
| Notify | `senza.strategy.notify()` | LLM proactively notifies user |
| ToolOutputGuard | `senza.strategy.tool_output_guard(env, config=None)` | Output truncation safety net |
| Helper | `senza.strategy.webhook_stream(buffer)` | Returns an external-event channel/stream pair; not a Plugin |
| Helper | `senza.strategy.context_aware_compaction_prompt()` | Returns a context-aware compaction prompt pair; not a Plugin |

**Production safety pattern** — combine SafetyDefaults + LoopSafety + Audit:

```python
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(senza.strategy.safety_defaults())
    .plugin(senza.strategy.loop_safety())
    .plugin(senza.strategy.audit("/tmp/audit.jsonl"))
    .build()
)
```

See `senza-strategy` skill for detailed usage and config examples.
