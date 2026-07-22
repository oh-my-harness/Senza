---
name: senza-workflow
description: >-
  Design and run multi-step LLM workflows with Senza's WorkflowEngine.
  Use when the user wants to: (1) build a multi-step pipeline with LLM and
  deterministic steps, (2) use conditional routing between steps,
  (3) share data between steps via context variables, (4) write custom
  judge or executor callbacks, (5) use declarative edge conditions,
  (6) mix LLM steps with executor steps, or (7) run a workflow end-to-end.
  Trigger phrases: "workflow", "multi-step", "pipeline", "conditional routing",
  "judge", "executor", "WorkflowEngine", "workflow dict", "edge condition".
---

# Senza Workflow — Multi-Step Orchestration

> SDK: `import senza`

## Core Pattern

```python
import senza

# 1. Define workflow as a dict
workflow = {
    "entry_step": "analyze",
    "steps": [
        {"id": "analyze", "name": "分析", "prompt": "分析数据并返回JSON", "allowed_tools": []},
        {"id": "transform", "name": "转换", "executor": "transform"},
    ],
    "edges": [
        {"from": "analyze", "to": "transform"},
    ],
}

# 2. Create provider, judge, executor
provider = senza.create_openai_provider(api_key="sk-...")
judge = senza.create_judge(lambda ctx: "to:transform" if ctx.get("structured", {}).get("ok") else "retry")
executor = senza.create_executor(lambda ctx: {"output": "done", "structured": {"status": "ok"}})

# 3. Build engine (fluent chain)
engine = (
    senza.WorkflowEngine(workflow, provider, "gpt-4o", judge)
    .with_executor("transform", executor)
)

# 4. Run
engine.run()
```

## Workflow Dict Schema

```python
{
    "entry_step": "step1",       # must be in steps
    "steps": [...],               # list of step dicts
    "edges": [...],               # list of edge dicts
}
```

### Step Types

The engine auto-detects step type: **has `"executor"` key → Executor step; otherwise → LLM step.**

**LLM step** — engine builds an AgentHarness, runs `prompt`:
```python
{"id": "step1", "name": "分析", "prompt": "请分析...", "allowed_tools": ["search"]}
```

**Executor step** — calls a registered deterministic executor:
```python
{"id": "step2", "name": "转换", "executor": "transform", "executor_config": {"fields": {"result": "/output"}}}
```

| Field | LLM | Executor | Type |
|-------|:---:|:--------:|------|
| `id` | ✅ | ✅ | str (unique) |
| `name` | ✅ | ✅ | str |
| `prompt` | ✅ | — | str |
| `allowed_tools` | ✅ | — | str[] (empty = no tools) |
| `executor` | — | ✅ | str (registry key) |
| `executor_config` | — | ✅ | dict (optional) |

### Edges

```python
{"from": "step1", "to": "step2"}                                           # unconditional
{"from": "step1", "to": "step2", "condition": "pass"}                      # label (judge interprets)
{"from": "step1", "to": "step2", "condition": {"op": "eq", "pointer": "/status", "value": "ok"}}  # declarative
```

### Declarative ConditionExpr

| op | params | semantics |
|----|--------|-----------|
| `exists` | `pointer` | path exists in structured |
| `missing` | `pointer` | path does not exist |
| `eq` | `pointer`, `value` | equals |
| `ne` | `pointer`, `value` | not equals |
| `gt` / `gte` / `lt` / `lte` | `pointer`, `value`(float) | numeric comparison |

`pointer` uses RFC 6901 JSON Pointer (e.g. `/status`, `/data/0/score`).

**Auto-enable**: if any edge has an `Expr` condition and judge is NoopJudge, engine auto-switches to built-in `EdgeConditionJudge`. No custom judge needed.

## Judge Callback

```python
def my_judge(ctx: dict) -> str:
    structured = ctx.get("structured") or {}
    if structured.get("status") == "ok":
        return "to:next_step"
    elif structured.get("retry_needed"):
        return "retry"
    else:
        return "fail:quality gate failed"

judge = senza.create_judge(my_judge)
```

`ctx` dict contains: `step_id`, `output`, `structured` (or None), `step_count`.

Return value encoding:
- `"to:<step_id>"` — jump to step
- `"retry"` — rerun current step
- `"fail:<reason>"` — mark workflow failed
- `"abort:<reason>"` — end workflow (success)

## Executor Callback

```python
def my_executor(ctx: dict) -> dict:
    return {
        "output": "处理完成",
        "structured": {"status": "ok", "result": 42},
    }

executor = senza.create_executor(my_executor)
```

`ctx` dict contains: `step_id`, `step_name`, `config`, `prev_output`, `context` (dict of shared variables).

Return dict must have `"output"` (str). `"structured"` is optional.

## WorkflowEngine Methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `__new__` | `(workflow_dict, provider, model, judge, session_base_dir="sessions")` | `WorkflowEngine` |
| `.with_tool(tool)` | `Tool → self` | Register extra tool |
| `.with_executor(name, executor)` | `str, Executor → self` | Register named executor |
| `.with_hooks(hooks_list)` | `list[Hook] → self` | Inject hooks |
| `.with_step_plugin(step_id, plugin)` | `str, Plugin → self` | Per-step plugin |
| `.with_max_tokens(tokens)` | `int? → self` | Max output tokens per LLM step |
| `.set_context_variable(key, value)` | `str, Any → None` | Set shared context var (before run) |
| `.run()` | `→ None` | Run to completion (blocking) |
| `.task_id()` | `→ str` | Task ID ("task-<uuid>") |
| `.subscribe(timeout_ms=5000)` | `→ WorkflowEventIterator` | Event stream |

## Shared Context

```python
# Set before run
engine.set_context_variable("user_input", "hello")
engine.set_context_variable("count", 42)

# Executor reads context
def my_executor(ctx):
    user_input = ctx["context"]["user_input"]  # dict of shared vars
    return {"output": f"Processed: {user_input}"}
```

## WorkflowEvent Types (subscribe)

| type | fields |
|------|--------|
| `step_started` | `step_id`, `step_name` |
| `step_finished` | `step_id`, `output`, `structured`, `tool_calls_count` |
| `paused` | `reason` |
| `resumed` | — |
| `cancelled` | `reason` |
| `failed` | `error` |

## Common Patterns

### Conditional routing with retry loop

```python
workflow = {
    "entry_step": "check",
    "steps": [
        {"id": "check", "name": "质检", "prompt": "检查质量", "allowed_tools": []},
        {"id": "fix", "name": "修复", "prompt": "修复问题", "allowed_tools": []},
    ],
    "edges": [
        {"from": "check", "to": "fix", "condition": {"op": "eq", "pointer": "/status", "value": "fail"}},
        {"from": "fix", "to": "check"},  # retry loop
    ],
}
# No custom judge needed — EdgeConditionJudge auto-enabled
judge = senza.create_judge(lambda ctx: "abort:done")  # NoopJudge fallback
```

### Mixing LLM and executor steps

```python
workflow = {
    "entry_step": "llm_analyze",
    "steps": [
        {"id": "llm_analyze", "name": "LLM分析", "prompt": "分析并返回JSON", "allowed_tools": []},
        {"id": "data_transform", "name": "数据转换", "executor": "json_transform", "executor_config": {"fields": {"result": "/output"}}},
        {"id": "llm_report", "name": "生成报告", "prompt": "根据转换结果写报告", "allowed_tools": []},
    ],
    "edges": [
        {"from": "llm_analyze", "to": "data_transform"},
        {"from": "data_transform", "to": "llm_report"},
    ],
}
```

### Event monitoring during run

```python
engine = senza.WorkflowEngine(workflow, provider, "gpt-4o", judge)

# Subscribe before run
event_iter = engine.subscribe(timeout_ms=5000)

# Run in main thread (blocking)
engine.run()

# Or poll events in a separate thread while run() executes
# for event in event_iter:
#     print(event["type"], event.get("step_id", ""))
```


## Builtin Executor Factories (newly exposed)

| Function | Description |
|----------|-------------|
| `create_shell_executor(commands, default_timeout_ms=30000, max_output_bytes=1048576)` | ShellExecutor with command allowlist |
| `create_http_executor(allowed_hosts, allowed_schemes=None, max_timeout_ms=30000, allow_private_ip_targets=False)` | HttpCallExecutor with host policy |

Both are **NOT auto-registered** (security by design). Register explicitly:

```python
shell_exec = senza.create_shell_executor(["echo", "cat", "python"])
http_exec = senza.create_http_executor(["api.example.com"], allowed_schemes=["https"])

engine = (
    senza.WorkflowEngine(workflow, provider, "gpt-4o", judge)
    .with_executor("shell", shell_exec)
    .with_executor("http", http_exec)
)
```