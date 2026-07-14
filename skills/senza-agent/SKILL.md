---
name: senza-agent
description: >-
  Build single-agent LLM applications with Senza (llm_harness_py PyO3 SDK).
  Use when the user wants to: (1) send a prompt to an LLM and get a response,
  (2) register tools for the LLM to call, (3) stream LLM output token-by-token,
  (4) set system prompts, (5) use OpenAI or Anthropic providers,
  (6) build a HarnessBuilder chain, or (7) abort an in-progress prompt.
  Trigger phrases: "how to use Harness", "single LLM call", "register a tool",
  "stream LLM output", "create provider", "HarnessBuilder".
---

# Senza Agent — Single-Agent LLM Calls

> SDK: `llm_harness_py` (PyO3, built from `llm-harness-runtime/crates/llm-harness-py`)
> Import as: `import llm_harness_py as L` (or `import senza as L` after rename)

## Core Pattern

```python
import llm_harness_py as L

# 1. Create provider
provider = L.create_openai_provider(api_key="sk-...")

# 2. Build harness (fluent chain)
harness = (
    L.HarnessBuilder("gpt-4o")
    .provider("gpt-*", provider)
    .system_prompt("You are a helpful assistant.")
    .max_tokens(1024)
    .build()
)

# 3. Prompt + collect events
harness.prompt("Hello!")
events = harness.collect_until_settled(timeout_ms=30000)

# 4. Extract text
text = ""
for e in events:
    if e["type"] == "text_delta":
        text += e.get("text", "")
```

## Provider Creation

| Function | Use case |
|----------|----------|
| `L.create_openai_provider(api_key, base_url=None, parse_reasoning_content=True, tolerant_keepalive=True)` | OpenAI, DeepSeek, local models |
| `L.create_anthropic_provider(api_key, base_url=None)` | Anthropic Claude |

- `base_url`: omit or pass empty string for default endpoint.
- `parse_reasoning_content`: set `True` for DeepSeek R-series reasoning parsing.
- `tolerant_keepalive`: set `True` for DeepSeek keepalive compatibility.

## HarnessBuilder Chain

All methods return `self` for chaining. Call `.build()` last.

| Method | Signature | Notes |
|--------|-----------|-------|
| `.provider(pattern, provider)` | `str, Provider → self` | `pattern` is a glob (e.g. `"gpt-*"`, `"claude-*"`) |
| `.system_prompt(text)` | `str → self` | Overwrites on repeat call |
| `.max_tokens(n)` | `int → self` | Default 8192; raise for reasoning models |
| `.temperature(t)` | `float? → self` | `None` = provider default |
| `.tool(tool)` | `Tool → self` | From `create_tool()` |
| `.plugin(plugin)` | `Plugin → self` | From `create_plugin()` |

`.build()` returns `AgentHarness`. Raises `RuntimeError` if no provider registered.

## Tool Creation

```python
import json

tool = L.create_tool(
    name="search",
    description="Search the web",
    parameters_schema=json.dumps({
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }),
    callback=lambda args, ctx: {
        "content": [{"type": "text", "text": f"Results for {args['query']}"}],
        "terminate": False,
    },
)
```

- `parameters_schema`: JSON Schema string (not dict — `json.dumps` it).
- `callback`: `(args: dict, ctx: ToolContext) -> dict`. The `ctx` arg is optional — if the function accepts 2 params it gets `ctx`, if 1 param it gets only `args`.
- Return dict: `{"content": [ContentBlock...], "terminate": bool}`. `terminate=True` stops the agent loop.
- **Async tools**: pass an `async def` callback. It runs via `asyncio.run()` on a blocking thread.

`L.create_sync_tool(...)` is an alias — same behavior, explicit sync.

## AgentHarness Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `.prompt(text)` | `None` | Synchronous, blocks until done |
| `.events(timeout_ms=5000)` | Iterator[dict] | Event stream, `None` on timeout |
| `.collect_until_settled(timeout_ms=30000)` | list[dict] | Collect until settled/aborted |
| `.message_count()` | `int` | Current message count |
| `.phase()` | `str` | `"idle"` / `"turning"` / `"compacting"` / `"branching"` |
| `.abort()` | `None` | Cancel current prompt (non-blocking) |

## Event Types

Terminal: `settled`, `aborted`, `error`.
Streaming: `text_delta` (has `.text`), `message_end`, `tool_call_start`, `tool_call_end`, `tool_execution_start`, `tool_execution_end`, `thinking_delta`.
Harness: `phase_change`, `compaction_start`, `compaction_end`, `tools_update`.

## Common Patterns

### Streaming output token-by-token

```python
harness.prompt("Write a poem")
for event in harness.events(timeout_ms=5000):
    if event["type"] == "text_delta":
        print(event["text"], end="", flush=True)
    elif event["type"] in ("settled", "aborted"):
        break
```

### Multiple providers (model routing)

```python
openai = L.create_openai_provider(api_key="sk-...")
anthropic = L.create_anthropic_provider(api_key="sk-ant-...")

harness = (
    L.HarnessBuilder("gpt-4o")
    .provider("gpt-*", openai)
    .provider("claude-*", anthropic)
    .build()
)
```

### Error handling

```python
try:
    harness.prompt("Hello!")
    events = harness.collect_until_settled()
except RuntimeError as e:
    print(f"Agent error: {e}")
```
