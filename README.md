# Senza (森座)

Python SDK for [`llm-harness-runtime`](https://github.com/oh-my-harness/llm-harness-runtime) — built with PyO3.

Senza exposes two layers of the oh-my-harness Rust runtime to Python:

| Layer | Classes | Use case |
|-------|---------|----------|
| **Agent** | `HarnessBuilder`, `AgentHarness` | Single LLM prompt, tool calling, streaming, dynamic config |
| **Runtime** | `WorkflowEngine` | Multi-step workflow, conditional routing, crash recovery, pause/cancel |

---

## Install

### From wheel (recommended)

```bash
pip install senza
```

### From source (development)

```bash
# Prerequisites: Rust toolchain + Python 3.9+ + maturin
pip install maturin

# Clone the runtime repo
git clone https://github.com/oh-my-harness/llm-harness-runtime.git
cd llm-harness-runtime/crates/llm-harness-py

# Build and install into current venv
maturin develop --release

# Or build a wheel
maturin build --release
pip install target/wheels/*.whl
```

### Verify

```python
import llm_harness_py as lh
print(lh.version())  # e.g. "0.3.0"
```

---

## Quick Start

### Agent: single LLM call

```python
import llm_harness_py as lh

provider = lh.create_openai_provider(api_key="sk-...")

harness = (
    lh.HarnessBuilder("gpt-4o")
    .provider("gpt-*", provider)
    .system_prompt("You are a helpful assistant.")
    .max_tokens(512)
    .build()
)

harness.prompt("Explain closures in one sentence.")

text = ""
for event in harness.collect_until_settled():
    if event["type"] == "text_delta":
        text += event.get("text", "")
print(text)
```

### Agent: with tools

```python
import json

def get_weather(args, ctx):
    return {
        "content": [{"type": "text", "text": f"Weather in {args['city']}: sunny, 22C"}],
        "terminate": False,
    }

tool = lh.create_tool(
    "get_weather", "Get weather for a city",
    json.dumps({"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}),
    get_weather,
)

harness = (
    lh.HarnessBuilder("gpt-4o")
    .provider("gpt-*", provider)
    .tool(tool)
    .build()
)
harness.prompt("What's the weather in Tokyo?")
```

### Runtime: multi-step workflow

```python
import llm_harness_py as lh

provider = lh.create_openai_provider(api_key="sk-...")

workflow = {
    "entry_step": "writer",
    "steps": [
        {"id": "writer", "name": "Writer", "prompt": "Write a one-sentence story.", "allowed_tools": []},
        {"id": "reviewer", "name": "Reviewer", "prompt": "Rate this story 1-5.", "allowed_tools": []},
    ],
    "edges": [{"from": "writer", "to": "reviewer"}],
}

def judge(ctx):
    if ctx["step_id"] == "writer":
        return "to:reviewer"
    return "abort:done"

engine = (
    lh.WorkflowEngine(workflow, provider, "gpt-4o", lh.create_judge(judge))
    .with_max_tokens(256)
)

engine.run()

for record in engine.step_history():
    r = record.get("result")
    print(f"{record['step_id']}: {r['output'][:80] if r else '(no result)'}")
```

### Runtime: crash recovery

```python
import tempfile

with tempfile.TemporaryDirectory() as store_dir:
    # Run with persistence
    engine = (
        lh.WorkflowEngine(workflow, provider, "gpt-4o", lh.create_judge(judge))
        .with_task_store(store_dir)
    )
    task_id = engine.task_id()
    engine.run()

    # Restore after "crash"
    restored = lh.WorkflowEngine.restore(store_dir, task_id, provider, "gpt-4o", lh.create_judge(judge))
    print(restored.state(), restored.current_step())
```

---

## API Reference

### Providers

```python
lh.create_openai_provider(api_key, base_url=None, parse_reasoning_content=True, tolerant_keepalive=True)
lh.create_anthropic_provider(api_key, base_url=None)
```

### Agent layer

| Method | Description |
|--------|-------------|
| `HarnessBuilder(model)` | Start builder chain |
| `.provider(pattern, provider)` | Register LLM provider (glob match) |
| `.system_prompt(text)` | Set system prompt |
| `.max_tokens(n)` / `.temperature(t)` | LLM params |
| `.tool(tool)` / `.plugin(plugin)` | Register tools/plugins |
| `.build()` | Returns `AgentHarness` |
| `harness.prompt(text)` | Send prompt (blocking) |
| `harness.collect_until_settled(timeout_ms=30000)` | Collect events until done |
| `harness.events(timeout_ms=5000)` | Stream events (iterator) |
| `harness.set_model(model)` | Switch model at runtime |
| `harness.set_system_prompt(text)` | Change system prompt |
| `harness.set_thinking_level("high")` | "off"/"minimal"/"low"/"medium"/"high"/"xhigh"/"budget:N" |
| `harness.steer(text)` / `harness.follow_up(text)` | Inject messages mid-run |
| `harness.usage()` | Get cost stats |
| `harness.abort()` | Cancel current prompt |

### Runtime layer

| Method | Description |
|--------|-------------|
| `WorkflowEngine(workflow_dict, provider, model, judge)` | Construct engine |
| `.with_tool(tool)` / `.with_executor(name, exec)` | Register tools/executors |
| `.with_hooks([hooks])` | Register hooks |
| `.with_task_store(dir)` | Enable persistence |
| `.with_max_steps(n)` / `.with_max_retries(n)` | Limits |
| `.run()` | Execute (blocking) |
| `.state()` | "idle"/"running"/"paused"/"succeeded"/"failed"/"cancelled" |
| `.current_step()` / `.step_history()` | Progress query |
| `.pause(reason)` / `.resume()` / `.cancel(reason)` | Flow control |
| `.restore(store_dir, task_id, provider, model, judge)` | Classmethod — crash recovery |
| `.checkpoint(desc, payload)` / `.total_cost()` | Checkpoint & cost |
| `.subscribe(timeout_ms=5000)` | Event stream iterator |

### Executors

```python
lh.create_executor(callback)           # Python callback executor
lh.create_shell_executor(commands)     # Shell command executor (allowlist)
lh.create_http_executor(allowed_hosts) # HTTP call executor (host allowlist)
```

### Hooks (11 types)

```python
lh.create_before_turn_hook(cb)         # cb(ctx: dict) -> None
lh.create_after_turn_hook(cb)          # cb(ctx: dict) -> None
lh.create_should_stop_hook(cb)         # cb(ctx: dict) -> bool
lh.create_before_tool_call_hook(cb)    # cb(ctx: dict) -> str | None
lh.create_after_tool_call_hook(cb)     # cb(ctx: dict) -> str | dict
# ... and 6 more (see examples/agent/ and skills/)
```

---

## Examples

See [`examples/`](examples/) for runnable demos:

- `examples/agent/` — 5 examples (basic prompt, tools, streaming, dynamic config, multi-provider)
- `examples/runtime/` — 8 examples (linear workflow, routing, executors, crash recovery, pause/cancel, human-in-loop, shell, http)

```bash
export OPENAI_API_KEY=sk-...
python examples/agent/01_basic_prompt.py
python examples/runtime/01_linear_workflow.py
```

## Skills

See [`skills/`](skills/) for process-oriented knowledge (loaded by Codex):

- `senza-agent` — Agent layer patterns
- `senza-workflow` — Runtime layer patterns
- `senza-advanced` — Hooks, plugins, human-in-the-loop, executors

## Design doc

See [`SENZA_DESIGN.md`](SENZA_DESIGN.md) for full architecture, gap analysis, and roadmap.
