# Senza Examples

## Agent Layer (`agent/`)

Single-LLM-call patterns using `HarnessBuilder` and `AgentHarness`.

| File | What it demonstrates |
|------|---------------------|
| `01_basic_prompt.py` | Minimal prompt → collect events → extract text |
| `02_tool_calling.py` | Register a tool, LLM discovers and calls it |
| `03_streaming.py` | Token-by-token streaming via `events()` iterator |
| `04_dynamic_config.py` | `set_model`, `set_system_prompt`, `set_temperature`, `set_thinking_level`, `usage` |
| `05_multi_provider.py` | Route different models to different providers via glob patterns |

## Runtime Layer (`runtime/`)

Multi-step workflow patterns using `WorkflowEngine`.

| File | What it demonstrates |
|------|---------------------|
| `01_linear_workflow.py` | Step A → step B, judge-based transitions, step history |
| `02_conditional_routing.py` | Declarative edge conditions (`{"op": "contains", ...}`) |
| `03_executor_steps.py` | Python executor steps, mixed with LLM steps, shared context |
| `04_crash_recovery.py` | `with_task_store` + `restore()` for crash recovery |
| `05_pause_cancel.py` | `pause()` / `cancel()` from another thread, state monitoring |
| `06_human_in_the_loop.py` | `create_event_channel` for external event injection |

## Running

```bash
# Set API key
export OPENAI_API_KEY=sk-...

# From this directory
python agent/01_basic_prompt.py
python runtime/01_linear_workflow.py
```

## Import

Examples try `import senza` first, falling back to `import llm_harness_py`.
Use whichever name your installed wheel provides.
