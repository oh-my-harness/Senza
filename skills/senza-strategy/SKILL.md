---
name: senza-strategy
description: >-
  Strategy plugins for Senza: safety guards, loop circuit breakers, status
  panels, memory defense, injection filtering, audit logging, and more.
  Use when the user wants to: (1) protect an agent from dangerous tool calls,
  (2) detect prompt injection or persistent memory injection, (3) break
  death-spiral / repetition loops, (4) show a status panel or todo list,
  (5) audit tool calls to a JSONL file, (6) wrap external content with source
  tags, (7) auto-inject project instructions (CLAUDE.md etc), (8) truncate
  oversized tool output, (9) trigger the agent from external webhooks,
  (10) use context-aware compaction prompts.
  Trigger phrases: "safety defaults", "loop safety", "death spiral",
  "prompt injection", "memory defense", "audit log", "status panel",
  "source tag", "project instruction", "tool output guard", "webhook",
  "context-aware compaction", "strategy plugin".
---

# Senza Strategy — Safety, Audit, and Control Plugins

> SDK: `import senza`
> Prerequisites: read `senza-agent` skill first.

## Core Pattern

All strategy plugins are created via `create_*` functions and installed on a
`HarnessBuilder` or `WorkflowEngine` like any other plugin:

```python
import senza

provider = senza.create_openai_provider(api_key="sk-...")

harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(senza.create_safety_defaults_plugin())
    .plugin(senza.create_loop_safety_plugin())
    .plugin(senza.create_audit_plugin("/tmp/audit.jsonl"))
    .build()
)
```

## Plugin Reference (12 + 2 helpers)

### SafetyDefaultsPlugin

```python
senza.create_safety_defaults_plugin() -> Plugin
```

Bundles two `BeforeToolCallHook` guards:
- **Bash blacklist** — blocks `rm -rf /`, `mkfs`, `dd`, `:(){:|:&};:`, and similar destructive shell commands.
- **Path traversal** — blocks tool args containing `../` sequences that escape the working directory.

No configuration needed — install and go.

### LoopSafetyPlugin

```python
senza.create_loop_safety_plugin(config: Optional[dict] = None) -> Plugin
```

A `ShouldStopHook` circuit breaker that detects three death-spiral patterns:

| Pattern | Default threshold | Config key |
|---------|-------------------|------------|
| Repetition (same tool call repeated) | 3 consecutive identical calls | `"max_repeated_tool_calls"` |
| Failure loop (tool errors in a row) | 5 consecutive failures | `"max_consecutive_failures"` |
| Turn budget (total turns) | 50 | `"max_turns"` |

```python
plugin = senza.create_loop_safety_plugin({
    "max_repeated_tool_calls": 3,
    "max_consecutive_failures": 5,
    "max_turns": 30,
})
```

### StatusPanelPlugin

```python
senza.create_status_panel_plugin() -> Plugin
```

Registers a `todo_write` tool the LLM can call to report task progress.
Also emits `status_update` events visible in the event stream. Useful for
long-running agents that should narrate their plan.

### MemoryDefensePlugin + Builder

```python
senza.create_memory_defense_plugin() -> Plugin

# Fluent builder for custom file sets:
senza.MemoryDefensePluginBuilder()
    .extra_file(".cursorrules")
    .extra_files(["CLAUDE.md", ".github/copilot-instructions.md"])
    .build()  # -> Plugin
```

Protects against **persistent memory injection** — adversarial instructions
planted in project config files (CLAUDE.md, .cursorrules, etc.) that try to
hijack the agent across sessions. The plugin scans registered instruction
files and neutralizes injection patterns before they reach the system prompt.

By default it guards common agent-instruction filenames. Use the builder to
add custom files:

```python
plugin = (
    senza.MemoryDefensePluginBuilder()
    .extra_file("TEAM_RULES.md")
    .extra_files(["docs/security-policy.md"])
    .build()
)
```

### InjectionFilterPlugin

```python
senza.create_injection_filter_plugin(patterns: Optional[list[str]] = None) -> Plugin
```

Detects prompt-injection attempts in tool output and user messages.
Default patterns catch common attacks (`"ignore previous instructions"`,
`"system:"`, `"you are now"`, etc.). Pass custom regex patterns to extend:

```python
plugin = senza.create_injection_filter_plugin([
    r"(?i)disregard\s+(all|previous)",
    r"(?i)reveal\s+your\s+system\s+prompt",
])
```

### SourceTagPlugin

```python
senza.create_source_tag_plugin(entries: list[dict]) -> Plugin
```

Wraps external content (tool output, RAG chunks, web fetches) with
`<source>` tags so the LLM can distinguish trusted vs. untrusted context.
Each entry describes a source:

```python
plugin = senza.create_source_tag_plugin([
    {"tool": "web_fetch", "tag": "web", "trusted": False},
    {"tool": "knowledge_read", "tag": "kb", "trusted": True},
])
```

### ProjectInstructionPlugin

```python
senza.create_project_instruction_plugin(
    env: ExecutionEnv, config: Optional[dict] = None,
) -> Plugin
```

Auto-injects project-level instruction files (`CLAUDE.md`, `AGENTS.md`,
`.cursorrules`, etc.) into the system prompt at the start of each run.
Requires an `ExecutionEnv` (from `create_os_env(...)`) to locate the
working directory.

```python
env = senza.create_os_env("/path/to/project")
plugin = senza.create_project_instruction_plugin(env)
```

### AuditPlugin

```python
senza.create_audit_plugin(
    sink_path: str,
    trace_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> Plugin
```

Logs every tool call (name, args, result, timestamp) to a JSONL file.
`trace_id` and `task_id` are included in each record for correlation.

```python
plugin = senza.create_audit_plugin(
    "/var/log/senza/audit.jsonl",
    trace_id="trace-abc123",
    task_id="task-001",
)
```

### NotifyPlugin

```python
senza.create_notify_plugin() -> Plugin
```

Registers a `notify_user` tool the LLM can call proactively when it
discovers something worth the user's attention (e.g. a critical error,
a completed milestone). Emits a `notification` event in the stream.

### ToolOutputGuardPlugin

```python
senza.create_tool_output_guard_plugin(
    env: ExecutionEnv, config: Optional[dict] = None,
) -> Plugin
```

Safety net for oversized tool output — truncates results that exceed the
configurable byte limit before they flood the context window.

```python
env = senza.create_os_env(".")
plugin = senza.create_tool_output_guard_plugin(env, {
    "max_bytes": 50000,
    "truncation_message": "[output truncated by guard]",
})
```

### WebhookStream

```python
senza.create_webhook_stream(buffer: int) -> tuple[WebhookChannel, EventStream]
```

Creates an external event trigger: push payloads from outside the agent
loop and they appear as events the agent can react to. `buffer` sets the
channel capacity.

```python
channel, stream = senza.create_webhook_stream(buffer=64)

# External trigger (another thread / HTTP handler):
channel.push({"event": "deploy_complete", "service": "api"})

# The stream can be consumed via senza.stream_events(stream) or
# registered as an event source on the harness/engine.
```

### context_aware_compaction_prompt

```python
senza.create_context_aware_compaction_prompt() -> tuple[str, str]
```

Returns `(system_prompt, user_template)` — a compaction prompt pair that
preserves task-critical context (active goals, key decisions, open
questions) rather than blindly summarizing all messages. Use with
`HarnessBuilder.compaction_prompt(system_prompt, user_template)`.

```python
sys_p, user_t = senza.create_context_aware_compaction_prompt()
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .compaction_prompt(sys_p, user_t)
    .build()
)
```

## Plugin Combination Patterns

### Production safety stack

```python
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(senza.create_safety_defaults_plugin())     # bash + path guards
    .plugin(senza.create_loop_safety_plugin())          # death-spiral breaker
    .plugin(senza.create_audit_plugin("/tmp/audit.jsonl"))
    .build()
)
```

### Full defense (injection + memory defense)

```python
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(senza.create_safety_defaults_plugin())
    .plugin(senza.create_injection_filter_plugin())
    .plugin(senza.create_memory_defense_plugin())
    .plugin(senza.create_source_tag_plugin([
        {"tool": "web_fetch", "tag": "web", "trusted": False},
    ]))
    .build()
)
```

### Observability stack

```python
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(senza.create_status_panel_plugin())
    .plugin(senza.create_audit_plugin("/tmp/audit.jsonl", trace_id="t1"))
    .plugin(senza.create_notify_plugin())
    .build()
)
```

### External trigger (webhook)

```python
channel, stream = senza.create_webhook_stream(buffer=32)

harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(senza.create_safety_defaults_plugin())
    .build()
)
# Feed stream events into harness via senza.stream_events(stream)
```

## All `create_*` Functions at a Glance

| Function | Returns | One-liner |
|----------|---------|-----------|
| `create_safety_defaults_plugin()` | `Plugin` | Bash blacklist + path traversal guard |
| `create_loop_safety_plugin(config=None)` | `Plugin` | Death-spiral / repetition / failure circuit breaker |
| `create_status_panel_plugin()` | `Plugin` | Status bar + `todo_write` tool |
| `create_memory_defense_plugin()` | `Plugin` | Persistent memory injection defense (default files) |
| `MemoryDefensePluginBuilder().extra_file(name).build()` | `Plugin` | Custom-file memory defense |
| `create_injection_filter_plugin(patterns=None)` | `Plugin` | Prompt injection detection |
| `create_source_tag_plugin(entries)` | `Plugin` | External content `<source>` wrapping |
| `create_project_instruction_plugin(env, config=None)` | `Plugin` | Auto-inject CLAUDE.md etc |
| `create_audit_plugin(sink_path, trace_id=None, task_id=None)` | `Plugin` | Tool call audit log (JSONL) |
| `create_notify_plugin()` | `Plugin` | LLM proactively notifies user |
| `create_tool_output_guard_plugin(env, config=None)` | `Plugin` | Output truncation safety net |
| `create_webhook_stream(buffer)` | `(WebhookChannel, EventStream)` | External event trigger |
| `create_context_aware_compaction_prompt()` | `tuple[str, str]` | Context-aware compaction prompt pair |
