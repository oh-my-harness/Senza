# Senza SDK DX Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix documentation drift, add API ergonomics (chat, EventType, __all__, unified parameters), and expose session persistence + FinalAnswerValidator from Rust runtime.

**Architecture:** Three layers delivered sequentially: P0 pure-docs fixes, P1 Python-layer ergonomics in `__init__.py`/`__init__.pyi` with two small Rust additions (`tools()` method, `__text_signature__`), P2 two Rust binding additions (JsonlSessionRepo + FinalAnswerValidator wrapper).

**Tech Stack:** Rust (PyO3 0.29), Python 3.9+, maturin, pytest

## Global Constraints

- Python events remain dict at runtime — no breaking changes to event shape
- `parameters_schema` stays as backward-compatible alias; `parameters` is the new canonical name
- `HarnessBuilder.hooks` field is private — hook injection goes through `HarnessBuilder::hooks()` method (push semantics)
- `PyHookWrapper` is an enum (`HookKind`) — new hook types require adding a variant + `push_into` arm + `kind_name` arm
- `create_tool` Rust function already accepts dict schema (no Python wrapper needed for that)
- All new Python API goes in `senza-pkg/senza/__init__.py` (runtime) and `senza-pkg/senza/__init__.pyi` (stubs)
- `scripts/check_stubs.py` must pass after stub changes
- `cargo fmt` before commits

---

## File Structure

| File | Responsibility | Changes |
|------|---------------|---------|
| `README.md` | Main documentation | P0: replace all `create_*` → submodule API; add API structure section; add `@senza.tool` docs |
| `docs/api-reference.md` | API reference | P0: same replacements; fix `parameters_schema` doc |
| `docs/providers.md` | Provider docs | P0: replace `create_openai_provider`/`create_anthropic_provider` |
| `SENZA_DESIGN.md` | Design doc | P0: §4 API reference old API sync |
| `senza-pkg/senza/__init__.py` | Python runtime layer | P1: `chat()`, `EventType`, `TypedDict`, `__all__`, `__doc__`, `create_tool` wrapper, `_wrap_tool_callback`, `_hooks.final_answer_validator` |
| `senza-pkg/senza/__init__.pyi` | Type stubs | P1: all new API signatures |
| `src/core/pybuilder.rs` | HarnessBuilder PyO3 wrapper | P1: `tools()`, `__text_signature__`; P2: `session_repo()`, `final_answer_validator()`, build() branching |
| `src/core/pyhooks.rs` | Hook wrappers | P2: `PyFinalAnswerValidatorWrapper`, `HookKind::FinalAnswerValidator` variant |
| `src/knowledge/pysessionrecall.rs` | Session recall bindings | P2: `create_jsonl_session_repo()` |
| `src/lib.rs` | PyO3 module entry | P2: register `create_jsonl_session_repo`, `create_final_answer_validator` |
| `src/runtime/pyworkflow.rs` | WorkflowEngine wrapper | P1: `__text_signature__` on `#[new]` |

---

## Task 1: P0 — Fix README.md API references

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing
- Produces: README with correct submodule API

- [ ] **Step 1: Identify all old API references**

Run: `grep -n "create_openai_provider\|create_anthropic_provider\|create_before_turn_hook\|create_after_turn_hook\|create_before_run_hook\|create_after_provider_response_hook\|create_before_provider_request_hook\|create_before_tool_call_hook\|create_after_tool_call_hook\|create_should_stop_hook\|create_before_compact_hook\|create_transform_context_hook\|create_prepare_next_turn_hook\|create_safety_defaults_plugin\|create_loop_safety_plugin\|create_status_panel_plugin\|create_memory_defense_plugin\|create_injection_filter_plugin\|create_source_tag_plugin\|create_project_instruction_plugin\|create_audit_plugin\|create_notify_plugin\|create_tool_output_guard_plugin\|create_webhook_stream\|create_context_aware_compaction_prompt\|create_local_knowledge_source\|create_knowledge_plugin\|create_in_memory_store\|create_memory_plugin\|create_secure_write_policy\|create_allow_all_gate\|create_in_memory_session_recall_index\|create_sqlite_session_recall_index\|create_in_memory_session_repo\|create_session_recall_knowledge_source\|create_history_recall_plugin\|create_rule_chain\|create_contains_predicate\|create_regex_field_predicate\|create_number_range_predicate\|create_rate_limit_predicate\|create_rule_approval_hook\|create_jsonl_audit_sink\|create_seatbelt_sandbox\|create_bwrap_sandbox" README.md`

Note all line numbers.

- [ ] **Step 2: Replace all old API calls with submodule API**

Apply these replacements throughout README.md:

| Old | New |
|-----|-----|
| `senza.create_openai_provider(` | `senza.providers.openai(` |
| `senza.create_anthropic_provider(` | `senza.providers.anthropic(` |
| `senza.create_before_turn_hook(` | `senza.hooks.before_turn(` |
| `senza.create_after_turn_hook(` | `senza.hooks.after_turn(` |
| `senza.create_before_run_hook(` | `senza.hooks.before_run(` |
| `senza.create_after_provider_response_hook(` | `senza.hooks.after_provider_response(` |
| `senza.create_before_provider_request_hook(` | `senza.hooks.before_provider_request(` |
| `senza.create_before_tool_call_hook(` | `senza.hooks.before_tool_call(` |
| `senza.create_after_tool_call_hook(` | `senza.hooks.after_tool_call(` |
| `senza.create_should_stop_hook(` | `senza.hooks.should_stop(` |
| `senza.create_before_compact_hook(` | `senza.hooks.before_compact(` |
| `senza.create_transform_context_hook(` | `senza.hooks.transform_context(` |
| `senza.create_prepare_next_turn_hook(` | `senza.hooks.prepare_next_turn(` |
| `senza.create_safety_defaults_plugin(` | `senza.strategy.safety_defaults(` |
| `senza.create_loop_safety_plugin(` | `senza.strategy.loop_safety(` |
| `senza.create_status_panel_plugin(` | `senza.strategy.status_panel(` |
| `senza.create_memory_defense_plugin(` | `senza.strategy.memory_defense(` |
| `senza.create_injection_filter_plugin(` | `senza.strategy.injection_filter(` |
| `senza.create_source_tag_plugin(` | `senza.strategy.source_tag(` |
| `senza.create_project_instruction_plugin(` | `senza.strategy.project_instruction(` |
| `senza.create_audit_plugin(` | `senza.strategy.audit(` |
| `senza.create_notify_plugin(` | `senza.strategy.notify(` |
| `senza.create_tool_output_guard_plugin(` | `senza.strategy.tool_output_guard(` |
| `senza.create_webhook_stream(` | `senza.strategy.webhook_stream(` |
| `senza.create_context_aware_compaction_prompt(` | `senza.strategy.context_aware_compaction_prompt(` |
| `senza.create_local_knowledge_source(` | `senza.knowledge.local_source(` |
| `senza.create_knowledge_plugin(` | `senza.knowledge.plugin(` |
| `senza.create_in_memory_store(` | `senza.knowledge.memory_store(` |
| `senza.create_memory_plugin(` | `senza.knowledge.memory_plugin(` |
| `senza.create_secure_write_policy(` | `senza.knowledge.secure_write_policy(` |
| `senza.create_allow_all_gate(` | `senza.knowledge.allow_all_gate(` |
| `senza.create_in_memory_session_recall_index(` | `senza.knowledge.in_memory_session_recall_index(` |
| `senza.create_sqlite_session_recall_index(` | `senza.knowledge.sqlite_session_recall_index(` |
| `senza.create_in_memory_session_repo(` | `senza.knowledge.in_memory_session_repo(` |
| `senza.create_session_recall_knowledge_source(` | `senza.knowledge.session_recall_knowledge_source(` |
| `senza.create_history_recall_plugin(` | `senza.knowledge.history_recall_plugin(` |
| `senza.create_rule_chain(` | `senza.rules.chain(` |
| `senza.create_contains_predicate(` | `senza.rules.contains(` |
| `senza.create_regex_field_predicate(` | `senza.rules.regex_field(` |
| `senza.create_number_range_predicate(` | `senza.rules.number_range(` |
| `senza.create_rate_limit_predicate(` | `senza.rules.rate_limit(` |
| `senza.create_rule_approval_hook(` | `senza.rules.approval_hook(` |
| `senza.create_jsonl_audit_sink` | `senza.infra.jsonl_audit_sink` |
| `senza.create_seatbelt_sandbox(` | `senza.infra.seatbelt_sandbox(` |
| `senza.create_bwrap_sandbox(` | `senza.infra.bwrap_sandbox(` |

- [ ] **Step 3: Add "API Structure" section**

Add a new section after the installation/quickstart section:

```markdown
## API Structure

Senza's public API has two layers:

- **Top-level high-frequency**: `HarnessBuilder`, `create_tool`, `create_judge`,
  `create_plugin`, `create_fs_tools_plugin`, `create_os_env`, etc. — functions
  every agent may need.
- **Submodule groups**: lower-frequency APIs organized by domain:
  - `senza.providers` — LLM provider factories (`openai`, `anthropic`)
  - `senza.hooks` — 11 lifecycle hook factories
  - `senza.strategy` — 12 strategy plugin factories
  - `senza.knowledge` — knowledge source, memory, and session-recall factories
  - `senza.rules` — rule chain and predicate factories
  - `senza.infra` — audit sink, trace exporter, sandbox factories
```

- [ ] **Step 4: Add `@senza.tool` decorator documentation**

Add a section before or within the Tools section:

```markdown
### Creating Tools with `@senza.tool`

The recommended way to create tools is the `@senza.tool` decorator, which
derives the JSON Schema automatically from type hints:

```python
import senza

@senza.tool
def search(query: str) -> str:
    """Search the web for information."""
    # implementation...
    return results
```

The function name becomes the tool name, the docstring becomes the description,
and the type annotations define the parameters schema. Both sync and async
functions are supported.
```

- [ ] **Step 5: Verify no old API references remain**

Run: `grep -n "create_openai_provider\|create_anthropic_provider\|create_before_turn_hook\|create_safety_defaults_plugin\|create_local_knowledge_source\|create_rule_chain\|create_jsonl_audit_sink\|create_seatbelt_sandbox" README.md`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: sync README to submodule API, add API structure and @senza.tool docs"
```

---

## Task 2: P0 — Fix docs/api-reference.md and docs/providers.md

**Files:**
- Modify: `docs/api-reference.md`
- Modify: `docs/providers.md`

- [ ] **Step 1: Replace all old API in docs/api-reference.md**

Apply the same replacement table from Task 1 to `docs/api-reference.md`.

Additionally, fix the `parameters_schema` documentation around line 97: change
"must be a JSON string" to "accepts a dict or a JSON string".

- [ ] **Step 2: Replace all old API in docs/providers.md**

Apply provider replacements:
- `senza.create_openai_provider(` → `senza.providers.openai(`
- `senza.create_anthropic_provider(` → `senza.providers.anthropic(`

- [ ] **Step 3: Fix SENZA_DESIGN.md §4**

Run: `grep -n "create_openai_provider\|create_anthropic_provider\|create_before_turn_hook\|create_safety_defaults_plugin\|create_local_knowledge_source\|create_rule_chain\|create_jsonl_audit_sink\|create_seatbelt_sandbox" SENZA_DESIGN.md`

Replace any old API references found.

- [ ] **Step 4: Verify**

Run: `grep -rn "create_openai_provider\|create_anthropic_provider\|create_before_turn_hook\|create_safety_defaults_plugin\|create_local_knowledge_source\|create_knowledge_plugin\|create_in_memory_store\|create_memory_plugin\|create_rule_chain\|create_contains_predicate\|create_jsonl_audit_sink\|create_seatbelt_sandbox" README.md docs/ SENZA_DESIGN.md`
Expected: no output

- [ ] **Step 5: Commit**

```bash
git add docs/api-reference.md docs/providers.md SENZA_DESIGN.md
git commit -m "docs: sync api-reference, providers, and design doc to submodule API"
```

---

## Task 3: P1 — Add `__all__` and `__doc__` to senza module

**Files:**
- Modify: `senza-pkg/senza/__init__.py:1-535`
- Modify: `senza-pkg/senza/__init__.pyi:1-3`
- Test: `tests/test_module_meta.py`

**Interfaces:**
- Consumes: nothing
- Produces: `senza.__doc__` (str), `senza.__all__` (list[str])

- [ ] **Step 1: Write the failing test**

Create `tests/test_module_meta.py`:

```python
"""Tests for senza module metadata (__doc__, __all__)."""

import senza


def test_module_has_docstring():
    """senza.__doc__ should be a non-empty string."""
    assert isinstance(senza.__doc__, str)
    assert len(senza.__doc__) > 0


def test_module_has_all():
    """senza.__all__ should be a non-empty list of strings."""
    assert isinstance(senza.__all__, list)
    assert len(senza.__all__) > 0
    for name in senza.__all__:
        assert isinstance(name, str)


def test_all_entries_exist_in_module():
    """Every name in __all__ must be an attribute of senza."""
    for name in senza.__all__:
        assert hasattr(senza, name), f"senza.__all__ contains '{name}' but it's not an attribute"


def test_key_apis_in_all():
    """Core public APIs must be in __all__."""
    expected = {
        "HarnessBuilder",
        "AgentHarness",
        "WorkflowEngine",
        "create_tool",
        "create_judge",
        "create_plugin",
        "tool",
        "extract_text",
        "providers",
        "hooks",
        "strategy",
        "knowledge",
        "infra",
        "rules",
    }
    assert expected.issubset(set(senza.__all__))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_module_meta.py -v`
Expected: FAIL — `senza.__doc__` is None, `senza.__all__` not defined

- [ ] **Step 3: Add `__doc__` and `__all__` to `__init__.py`**

At the very top of `senza-pkg/senza/__init__.py`, before `from .senza import *`, add:

```python
"""Senza — Python SDK for llm-harness runtime."""
```

At the end of the file (after `rules = _rules`), add:

```python
# ── Public API whitelist ─────────────────────────────────────────────
__all__ = [
    # Classes
    "HarnessBuilder", "AgentHarness", "WorkflowEngine",
    "UsageLedger", "Provider", "Tool", "ToolContext",
    "Plugin", "Judge", "CompositeJudge", "Executor", "ExecutionEnv",
    "ResponseFormat", "Skill", "Hook",
    "KnowledgeSource", "MemoryStore", "MemoryWritePolicy",
    "MemoryMutationGate", "SessionRepo", "SessionRecallIndex",
    "SessionRecallKnowledgeSource",
    "JsonlAuditSink", "InMemoryTraceExporter", "Sandbox",
    "PricingProvider", "BudgetExceededHook",
    "Predicate", "RuleChain", "RuleChainBuilder",
    "McpServerConfig", "McpManager",
    "WebhookChannel", "EventStream",
    "HeartbeatHandle", "ShellMonitorHandle",
    "EventStreamHandle", "WaitForExternalEventTool",
    "HarnessEventIterator", "WorkflowEventIterator", "EventIterator",
    # Factory functions (top-level)
    "create_tool", "create_sync_tool", "create_judge", "create_composite_judge",
    "create_plugin", "create_fs_tools_plugin",
    "create_os_env", "create_event_channel",
    "create_executor", "create_shell_executor", "create_http_executor",
    "create_pricing_provider", "create_pricing_provider_callback",
    "create_budget_exceeded_hook",
    "create_json_object_format", "create_json_schema_format",
    "create_timer_stream", "create_heartbeat_stream", "create_shell_monitor_stream",
    "load_skills",
    # Submodules
    "providers", "hooks", "strategy", "knowledge", "infra", "rules",
    # Decorators and helpers
    "tool", "extract_text",
    "stream_events", "stream_prompt", "stream_run",
    # Debug / utilities
    "enable_debug", "disable_debug", "version", "set_event_loop",
    "to_json", "from_json",
    # Exceptions
    "SenzaError", "ProviderError", "RateLimitError", "ProviderTimeoutError",
    "InvalidRequestError", "UnauthorizedError", "ForbiddenError",
    "OverloadedError", "ServerError", "StreamError", "StreamIncompleteError",
    "NetworkError", "DecodeError", "ProviderCodeError",
    "ToolError", "ToolArgumentError", "ToolAbortedError", "ToolExecutionError",
    "BudgetExceededError", "WorkflowError", "StepTimeoutError",
    "StepFailedError", "WorkflowPausedError", "ValidationError",
    "HarnessStateError", "CompactionError", "StreamIdleTimeoutError",
    "RustPanicError",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_module_meta.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add senza-pkg/senza/__init__.py tests/test_module_meta.py
git commit -m "feat: add __doc__ and __all__ to senza module"
```

---

## Task 4: P1 — Add `harness.chat()` convenience method

**Files:**
- Modify: `senza-pkg/senza/__init__.py` (add after `_harness_prompt_async`)
- Modify: `senza-pkg/senza/__init__.pyi` (add to `AgentHarness` class)
- Test: `tests/test_chat_method.py`

**Interfaces:**
- Consumes: `AgentHarness.prompt_and_collect()`, `extract_text()`
- Produces: `AgentHarness.chat(text: str, timeout_ms: int = 30000) -> str`, `AgentHarness.chat_async(text: str, timeout_ms: int = 30000) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_chat_method.py`:

```python
"""Tests for AgentHarness.chat() convenience method."""

import senza


def test_chat_method_exists():
    """AgentHarness should have a chat method."""
    assert hasattr(senza.AgentHarness, "chat")


def test_chat_async_method_exists():
    """AgentHarness should have a chat_async method."""
    assert hasattr(senza.AgentHarness, "chat_async")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_chat_method.py -v`
Expected: FAIL — `chat` not found on `AgentHarness`

- [ ] **Step 3: Implement `chat` and `chat_async`**

In `senza-pkg/senza/__init__.py`, after the `_harness_prompt_async` definition (around line 324), add:

```python
def _harness_chat(self, text: str, timeout_ms: int = 30000) -> str:
    """Send a prompt and return the concatenated text response.

    Convenience wrapper around ``extract_text(prompt_and_collect(text))``.
    For streaming or event-level access, use ``prompt_and_collect()`` or
    ``stream_prompt()`` instead.
    """
    events = self.prompt_and_collect(text, timeout_ms)
    return extract_text(events)


async def _harness_chat_async(self, text: str, timeout_ms: int = 30000) -> str:
    """Async version of chat(). Does not block the event loop."""
    events = await _asyncio.to_thread(self.prompt_and_collect, text, timeout_ms)
    return extract_text(events)


AgentHarness.chat = _harness_chat
AgentHarness.chat_async = _harness_chat_async
```

- [ ] **Step 4: Add stubs to `__init__.pyi`**

In the `AgentHarness` class, after `prompt_async` (line 627), add:

```python
    def chat(self, text: str, timeout_ms: int = 30000) -> str: ...
    async def chat_async(self, text: str, timeout_ms: int = 30000) -> str: ...
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_chat_method.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add senza-pkg/senza/__init__.py senza-pkg/senza/__init__.pyi tests/test_chat_method.py
git commit -m "feat: add harness.chat() convenience method"
```

---

## Task 5: P1 — Add `EventType` constants and `SenzaEvent` TypedDict

**Files:**
- Modify: `senza-pkg/senza/__init__.py`
- Modify: `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_event_type.py`

**Interfaces:**
- Consumes: nothing
- Produces: `senza.EventType` (class with str constants), `senza.SenzaEvent` (TypedDict union)

- [ ] **Step 1: Write the failing test**

Create `tests/test_event_type.py`:

```python
"""Tests for EventType constants."""

import senza


def test_event_type_class_exists():
    """EventType should be a class with string constants."""
    assert hasattr(senza, "EventType")


def test_event_type_constants():
    """EventType should have all expected event type constants."""
    expected = {
        "TEXT_DELTA": "text_delta",
        "TOOL_CALL_START": "tool_call_start",
        "TOOL_CALL_END": "tool_call_end",
        "TOOL_RESULT": "tool_result",
        "MESSAGE_END": "message_end",
        "THINKING_DELTA": "thinking_delta",
        "ERROR": "error",
        "AGENT_END": "agent_end",
        "SETTLED": "settled",
        "ABORTED": "aborted",
    }
    for name, value in expected.items():
        assert getattr(senza.EventType, name) == value


def test_event_type_in_all():
    """EventType should be in __all__."""
    assert "EventType" in senza.__all__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_event_type.py -v`
Expected: FAIL — `senza.EventType` not found

- [ ] **Step 3: Implement EventType and TypedDicts**

In `senza-pkg/senza/__init__.py`, after the `extract_text` helper section (around line 180), add:

```python
# ── Event type constants ─────────────────────────────────────────────


class EventType:
    """String constants for event types.

    Use these instead of raw strings to avoid typos:

        if event["type"] == senza.EventType.TEXT_DELTA:
            text += event["text"]
    """

    TEXT_DELTA = "text_delta"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    TOOL_RESULT = "tool_result"
    MESSAGE_END = "message_end"
    THINKING_DELTA = "thinking_delta"
    ERROR = "error"
    AGENT_END = "agent_end"
    SETTLED = "settled"
    ABORTED = "aborted"
    WORKFLOW_DONE = "workflow_done"
    WORKFLOW_FAILED = "workflow_failed"
```

- [ ] **Step 4: Add to `__all__`**

Add `"EventType"` to the `__all__` list (in the "Decorators and helpers" section).

- [ ] **Step 5: Add TypedDicts to `__init__.pyi`**

In `senza-pkg/senza/__init__.pyi`, after the `extract_text` declaration (around line 125), add:

```python
# ── Event types ──────────────────────────────────────────────────────────────

class EventType:
    TEXT_DELTA: str
    TOOL_CALL_START: str
    TOOL_CALL_END: str
    TOOL_RESULT: str
    MESSAGE_END: str
    THINKING_DELTA: str
    ERROR: str
    AGENT_END: str
    SETTLED: str
    ABORTED: str
    WORKFLOW_DONE: str
    WORKFLOW_FAILED: str
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_event_type.py -v`
Expected: PASS

- [ ] **Step 7: Verify stubs**

Run: `python scripts/check_stubs.py`
Expected: zero discrepancies

- [ ] **Step 8: Commit**

```bash
git add senza-pkg/senza/__init__.py senza-pkg/senza/__init__.pyi tests/test_event_type.py
git commit -m "feat: add EventType constants for typed event handling"
```

---

## Task 6: P1 — Unify `parameters` naming and fix `create_tool` callback signature

**Files:**
- Modify: `senza-pkg/senza/__init__.py`
- Modify: `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_create_tool_wrapper.py`

**Interfaces:**
- Consumes: Rust `create_tool` (already accepts dict schema)
- Produces: Python `create_tool(name, description, parameters=None, parameters_schema=None, callback=None)` wrapper with `parameters` as canonical name and single-arg callback support

- [ ] **Step 1: Write the failing test**

Create `tests/test_create_tool_wrapper.py`:

```python
"""Tests for create_tool Python wrapper (parameters alias + callback fix)."""

import json

import pytest
import senza


def test_create_tool_with_parameters_kwarg():
    """create_tool should accept parameters= as the canonical kwarg."""
    def cb(args, ctx):
        return {"content": [], "terminate": False}

    tool = senza.create_tool(
        name="test",
        description="test",
        parameters={"type": "object", "properties": {}},
        callback=cb,
    )
    assert tool.name == "test"


def test_create_tool_with_parameters_schema_backward_compat():
    """create_tool should still accept parameters_schema= for backward compat."""
    def cb(args, ctx):
        return {"content": [], "terminate": False}

    tool = senza.create_tool(
        name="test",
        description="test",
        parameters_schema=json.dumps({"type": "object", "properties": {}}),
        callback=cb,
    )
    assert tool.name == "test"


def test_create_tool_single_arg_callback():
    """create_tool should accept a single-argument callback (args only)."""
    def single_arg_cb(args):
        return {"content": [{"type": "text", "text": args["x"]}], "terminate": False}

    tool = senza.create_tool(
        name="test",
        description="test",
        parameters={"type": "object", "properties": {"x": {"type": "string"}}},
        callback=single_arg_cb,
    )
    assert tool.name == "test"


def test_create_tool_missing_parameters_raises():
    """create_tool should raise if neither parameters nor parameters_schema is given."""
    def cb(args, ctx):
        return {"content": [], "terminate": False}

    with pytest.raises(TypeError):
        senza.create_tool("test", "test", callback=cb)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_create_tool_wrapper.py -v`
Expected: FAIL — `create_tool` doesn't accept `parameters=` kwarg; single-arg callback may fail

- [ ] **Step 3: Implement Python wrapper**

In `senza-pkg/senza/__init__.py`, before the `@senza.tool` decorator section (around line 182), add:

```python
# ── create_tool Python wrapper ───────────────────────────────────────
# Rust-layer create_tool already accepts dict schema, but we add a Python
# wrapper to: (1) accept `parameters` as canonical name (alias for
# parameters_schema), and (2) allow single-argument callbacks.

import inspect as _inspect_for_tool


def _wrap_tool_callback(callback):
    """Wrap a tool callback to allow single-argument (args-only) signatures.

    Rust always calls cb(args, ctx). If the user's callback only accepts
    one argument, we wrap it to ignore ctx.
    """
    try:
        sig = _inspect_for_tool.signature(callback)
        params = [
            p for p in sig.parameters.values()
            if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
        ]
        if len(params) <= 1:
            return lambda args, ctx: callback(args)
    except (ValueError, TypeError):
        pass
    return callback


# Save the Rust-level create_tool before shadowing it.
_create_tool_rust = create_tool


def create_tool(name, description, parameters=None, parameters_schema=None, callback=None):
    """Create a Tool from a callback.

    Args:
        name: Tool name.
        description: Tool description.
        parameters: JSON Schema as dict or JSON string (canonical name).
        parameters_schema: Alias for ``parameters`` (backward compat).
        callback: Callable with signature ``(args, ctx)`` or ``(args)``.
            Async callables are supported.
    """
    schema = parameters if parameters is not None else parameters_schema
    if schema is None:
        raise TypeError(
            "create_tool() missing required argument: 'parameters'"
        )
    if callback is None:
        raise TypeError("create_tool() missing required argument: 'callback'")
    wrapped = _wrap_tool_callback(callback)
    return _create_tool_rust(name, description, schema, wrapped)
```

- [ ] **Step 4: Update `__init__.pyi`**

Replace the existing `create_tool` declaration (around line 256) with:

```python
def create_tool(
    name: str,
    description: str,
    parameters: Optional[Union[dict, str]] = ...,
    *,
    parameters_schema: Optional[Union[dict, str]] = ...,
    callback: Callable[..., Any],
) -> Tool: ...
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_create_tool_wrapper.py tests/test_dict_schema.py -v`
Expected: PASS (both new and existing dict schema tests)

- [ ] **Step 6: Verify stubs**

Run: `python scripts/check_stubs.py`
Expected: zero discrepancies

- [ ] **Step 7: Commit**

```bash
git add senza-pkg/senza/__init__.py senza-pkg/senza/__init__.pyi tests/test_create_tool_wrapper.py
git commit -m "feat: unify parameters naming and support single-arg callbacks in create_tool"
```

---

## Task 7: P1 — Add `HarnessBuilder.tools()` plural method + `__text_signature__` fixes

**Files:**
- Modify: `src/core/pybuilder.rs:42-74` (struct + new), `src/core/pybuilder.rs:191-256` (add tools method)
- Modify: `src/runtime/pyworkflow.rs:1136-1154` (WorkflowEngine __text_signature__)
- Modify: `senza-pkg/senza/__init__.pyi:557-604` (add tools stub)
- Test: `tests/test_tools_method.py`

**Interfaces:**
- Consumes: `PyToolWrapper` from `crate::core::pytool`
- Produces: `HarnessBuilder.tools(list[Tool]) -> HarnessBuilder`, fixed `help(HarnessBuilder.__init__)` output

- [ ] **Step 1: Write the failing test**

Create `tests/test_tools_method.py`:

```python
"""Tests for HarnessBuilder.tools() plural method."""

import senza


def test_tools_method_exists():
    """HarnessBuilder should have a tools() method accepting a list."""
    assert hasattr(senza.HarnessBuilder, "tools")


def test_tools_accepts_list():
    """tools() should accept a list of tools."""
    tool1 = senza.create_tool("t1", "test", {"type": "object", "properties": {}}, lambda a, c: None)
    tool2 = senza.create_tool("t2", "test", {"type": "object", "properties": {}}, lambda a, c: None)
    builder = senza.HarnessBuilder("gpt-4o").tools([tool1, tool2])
    assert builder is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tools_method.py -v`
Expected: FAIL — `tools` method not found

- [ ] **Step 3: Add `tools()` method to `PyHarnessBuilder`**

In `src/core/pybuilder.rs`, in the `#[pymethods]` impl block, after the existing `tool` method, add:

```rust
    /// Register multiple tools without wrapping them in a Plugin.
    ///
    /// Equivalent to calling `.tool(t)` for each t in the list.
    #[pyo3(text_signature = "($self, tools)")]
    fn tools<'a>(
        mut slf: PyRefMut<'a, Self>,
        tools: Vec<Bound<'_, crate::core::pytool::PyToolWrapper>>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            for wrapper in &tools {
                let tool_arc: Arc<dyn Tool> = wrapper.borrow().tool.clone();
                b = b.tool(tool_arc);
            }
            slf.builder = Some(b);
        }
        slf
    }
```

- [ ] **Step 4: Fix `__text_signature__` on `HarnessBuilder::new`**

In `src/core/pybuilder.rs`, change the `#[new]` annotation:

```rust
    #[new]
    #[pyo3(text_signature = "(model)")]
    fn new(model: &str) -> Self {
```

- [ ] **Step 5: Fix `__text_signature__` on `WorkflowEngine::new`**

In `src/runtime/pyworkflow.rs`, add `text_signature` to the `#[new]` attribute:

```rust
    #[new]
    #[pyo3(signature = (workflow_dict, provider, model, judge, session_base_dir="sessions", env=None), text_signature = "(workflow_dict, provider, model, judge, session_base_dir=\"sessions\", env=None)")]
    fn new(
```

- [ ] **Step 6: Add `tools` stub to `__init__.pyi`**

In the `HarnessBuilder` class, after `def tool(self, tool: Tool) -> HarnessBuilder: ...` (line 568), add:

```python
    def tools(self, tools: list[Tool]) -> HarnessBuilder: ...
```

- [ ] **Step 7: Build and run tests**

Run: `maturin develop && python -m pytest tests/test_tools_method.py -v`
Expected: PASS

- [ ] **Step 8: Verify `help()` output**

Run: `python -c "import senza; help(senza.HarnessBuilder.__init__)"`
Expected: shows `(model)` not `(*args, **kwargs)`

- [ ] **Step 9: Verify stubs**

Run: `python scripts/check_stubs.py`
Expected: zero discrepancies

- [ ] **Step 10: Commit**

```bash
git add src/core/pybuilder.rs src/runtime/pyworkflow.rs senza-pkg/senza/__init__.pyi tests/test_tools_method.py
git commit -m "feat: add HarnessBuilder.tools() plural method and fix __text_signature__"
```

---

## Task 8: P2 — Expose `JsonlSessionRepo` and `session_repo()` builder method

**Files:**
- Modify: `src/knowledge/pysessionrecall.rs` (add `create_jsonl_session_repo`)
- Modify: `src/core/pybuilder.rs` (add `session_repo` field + method + build branching)
- Modify: `src/lib.rs` (register function)
- Modify: `senza-pkg/senza/__init__.py` (add to knowledge submodule)
- Modify: `senza-pkg/senza/__init__.pyi` (add stub)
- Test: `tests/test_session_persistence.py`

**Interfaces:**
- Consumes: `llm_harness_agent::JsonlSessionRepo`, `llm_harness_agent::SessionRepo`, `llm_harness_agent::Session`, `llm_harness_agent::CreateSessionOptions`, `HarnessBuilder::build_with_session`
- Produces: `senza.knowledge.jsonl_session_repo(root_dir) -> SessionRepo`, `HarnessBuilder.session_repo(repo, session_id=None) -> HarnessBuilder`

- [ ] **Step 1: Write the failing test**

Create `tests/test_session_persistence.py`:

```python
"""Tests for JsonlSessionRepo exposure and session_repo builder method."""

import tempfile
import os

import pytest
import senza


def test_jsonl_session_repo_exists():
    """senza.knowledge.jsonl_session_repo should be callable."""
    assert hasattr(senza.knowledge, "jsonl_session_repo")


def test_jsonl_session_repo_creates_repo():
    """jsonl_session_repo should return a SessionRepo object."""
    with tempfile.TemporaryDirectory() as d:
        repo = senza.knowledge.jsonl_session_repo(d)
        assert repo is not None


def test_session_repo_builder_method_exists():
    """HarnessBuilder should have a session_repo method."""
    assert hasattr(senza.HarnessBuilder, "session_repo")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_session_persistence.py -v`
Expected: FAIL — `jsonl_session_repo` not found, `session_repo` not found

- [ ] **Step 3: Add `create_jsonl_session_repo` to `pysessionrecall.rs`**

In `src/knowledge/pysessionrecall.rs`, after the existing `create_in_memory_session_repo` function (around line 73), add:

```rust
/// Create a file-system-backed `JsonlSessionRepo`.
///
/// Each session is stored in its own subdirectory: `{root_dir}/{session_id}/`.
/// Sessions persist across process restarts and can be loaded with
/// `HarnessBuilder.session_repo(repo, session_id=...)`.
#[pyfunction]
#[pyo3(text_signature = "(root_dir)")]
pub fn create_jsonl_session_repo<'py>(
    py: Python<'py>,
    root_dir: &str,
) -> PyResult<Bound<'py, PySessionRepo>> {
    let repo: Arc<dyn llm_harness_agent::SessionRepo> =
        Arc::new(llm_harness_agent::JsonlSessionRepo::new(root_dir));
    Ok(Py::new(py, PySessionRepo { repo })?.into_bound(py))
}
```

- [ ] **Step 4: Register in `lib.rs`**

In `src/lib.rs`, after the `create_in_memory_session_repo` registration (around line 289), add:

```rust
    m.add_function(wrap_pyfunction!(
        knowledge::pysessionrecall::create_jsonl_session_repo,
        m
    )?)?;
```

- [ ] **Step 5: Add `session_repo` field and method to `PyHarnessBuilder`**

In `src/core/pybuilder.rs`:

1. Add fields to the struct (after `spawn_config`):

```rust
    /// Optional session repo for persistent sessions.
    session_repo: Option<Arc<dyn llm_harness_agent::SessionRepo>>,
    /// Optional session ID to restore an existing session.
    session_id: Option<String>,
```

2. Initialize them in `new()`:

```rust
            spawn_config: None,
            session_repo: None,
            session_id: None,
```

3. Also initialize in `from_builder()`:

```rust
            spawn_config: None,
            session_repo: None,
            session_id: None,
```

4. Add the method (in `#[pymethods]` impl, before `build()`):

```rust
    /// Set a session repo for persistent (JSONL-backed) sessions.
    ///
    /// If `session_id` is given, opens an existing session; otherwise creates
    /// a new one. When set, `build()` uses `build_with_session()` instead of
    /// the default in-memory session.
    #[pyo3(text_signature = "($self, repo, session_id=None)")]
    #[pyo3(signature = (repo, session_id=None))]
    fn session_repo<'a>(
        mut slf: PyRefMut<'a, Self>,
        repo: &Bound<'_, crate::knowledge::pysessionrecall::PySessionRepo>,
        session_id: Option<String>,
    ) -> PyRefMut<'a, Self> {
        slf.session_repo = Some(repo.borrow().repo.clone());
        slf.session_id = session_id;
        slf
    }
```

- [ ] **Step 6: Add session repo branching to `build()`**

In `src/core/pybuilder.rs`, in the `build()` method, before the `if has_mcp` block, add session repo handling. Replace the existing `build()` logic to branch on `session_repo`:

```rust
    fn build(&mut self, py: Python<'_>) -> PyResult<Py<PyAgentHarness>> {
        let builder = self.builder.take().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("build() already consumed this builder")
        })?;

        let env: Arc<dyn ExecutionEnv> = self
            .env
            .take()
            .unwrap_or_else(|| Arc::new(UnsupportedEnv::new()));
        let rt = runtime(py);

        let has_mcp = !self.mcp_servers.is_empty()
            || !self.mcp_config_files.is_empty()
            || self.mcp_manager.is_some();

        let spawn_config = self.spawn_config.take();
        let session_repo = self.session_repo.take();
        let session_id = self.session_id.take();

        // If a session repo is set, load/create a session and use
        // build_with_session() instead of the default in-memory build.
        if let Some(repo) = session_repo {
            let storage = if let Some(id) = session_id {
                crate::shared::pyerror::detach_catch_panic_result(py, move || {
                    rt.block_on(async move { repo.open(&id).await })
                })?
            } else {
                crate::shared::pyerror::detach_catch_panic_result(py, move || {
                    rt.block_on(async move {
                        repo.create(llm_harness_agent::CreateSessionOptions::default())
                            .await
                    })
                })?
            };
            let session = llm_harness_agent::Session::new(storage);

            // MCP + session_repo combo: build MCP harness, then set session.
            // build_with_session is on the base HarnessBuilder; MCP variant
            // needs separate handling if both are set. For now, if both MCP
            // and session_repo are set, we use the base builder path (no MCP).
            let (builder, spawn_wiring) = match spawn_config {
                Some(cfg) => wire_spawn(builder, cfg),
                None => (builder, None),
            };

            let harness = crate::shared::pyerror::detach_catch_panic_result(py, move || {
                builder.build_with_session(env, session)
            })?;
            let harness = Arc::new(harness);

            if let Some(wiring) = spawn_wiring {
                wiring.post_build(&harness);
            }

            return Py::new(py, PyAgentHarness::new_base(harness));
        }

        // --- existing build() logic (MCP / spawn / base) unchanged ---
        if has_mcp {
            // ... (existing MCP path)
```

**Important:** Keep the existing MCP and base build paths after the session_repo early return. Only the session_repo path is new.

- [ ] **Step 7: Add to `__init__.py` knowledge submodule**

In `senza-pkg/senza/__init__.py`, in the `_knowledge` SimpleNamespace (around line 444), add:

```python
    jsonl_session_repo=create_jsonl_session_repo,
```

Also add `del create_jsonl_session_repo` in the cleanup section (after the existing `del create_in_memory_session_repo`).

- [ ] **Step 8: Add stubs to `__init__.pyi`**

In the `knowledge` class (around line 288), add:

```python
    def jsonl_session_repo(root_dir: str) -> SessionRepo: ...
```

In the `HarnessBuilder` class, after `enable_spawn` (line 603), add:

```python
    def session_repo(
        self, repo: SessionRepo, session_id: Optional[str] = ...
    ) -> HarnessBuilder: ...
```

- [ ] **Step 9: Build and run tests**

Run: `maturin develop && python -m pytest tests/test_session_persistence.py -v`
Expected: PASS

- [ ] **Step 10: Verify stubs**

Run: `python scripts/check_stubs.py`
Expected: zero discrepancies

- [ ] **Step 11: Commit**

```bash
git add src/knowledge/pysessionrecall.rs src/core/pybuilder.rs src/lib.rs senza-pkg/senza/__init__.py senza-pkg/senza/__init__.pyi tests/test_session_persistence.py
git commit -m "feat: expose JsonlSessionRepo and session_repo() builder method"
```

---

## Task 9: P2 — Expose `FinalAnswerValidator`

**Files:**
- Modify: `src/core/pyhooks.rs` (add `PyFinalAnswerValidatorWrapper` + `HookKind` variant)
- Modify: `src/core/pybuilder.rs` (add `final_answer_validator()` method)
- Modify: `src/lib.rs` (register `create_final_answer_validator`)
- Modify: `senza-pkg/senza/__init__.py` (add to hooks submodule)
- Modify: `senza-pkg/senza/__init__.pyi` (add stubs)
- Test: `tests/test_final_answer_validator.py`

**Interfaces:**
- Consumes: `llm_harness_types::{FinalAnswerValidationCtx, FinalAnswerValidationError, FinalAnswerValidator}`, `AssistantMessage` (Serialize), `HarnessBuilder::hooks()`
- Produces: `senza.hooks.final_answer_validator(callback) -> Hook`, `HarnessBuilder.final_answer_validator(validator) -> HarnessBuilder`

- [ ] **Step 1: Write the failing test**

Create `tests/test_final_answer_validator.py`:

```python
"""Tests for FinalAnswerValidator Python binding."""

import senza


def test_final_answer_validator_factory_exists():
    """senza.hooks.final_answer_validator should be callable."""
    assert hasattr(senza.hooks, "final_answer_validator")


def test_final_answer_validator_creates_hook():
    """final_answer_validator should return a Hook object."""
    def my_validator(ctx):
        return None

    hook = senza.hooks.final_answer_validator(my_validator)
    assert hook is not None


def test_builder_method_exists():
    """HarnessBuilder should have a final_answer_validator method."""
    assert hasattr(senza.HarnessBuilder, "final_answer_validator")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_final_answer_validator.py -v`
Expected: FAIL — `final_answer_validator` not found

- [ ] **Step 3: Add `HookKind::FinalAnswerValidator` variant**

In `src/core/pyhooks.rs`:

1. Add import at the top (in the `use llm_harness_types::{...}` block):

```rust
    FinalAnswerValidationCtx, FinalAnswerValidationError, FinalAnswerValidator,
```

2. Add variant to `HookKind` enum (around line 1241):

```rust
    FinalAnswerValidator(Arc<dyn FinalAnswerValidator>),
```

3. Add `push_into` arm (around line 1289):

```rust
            HookKind::FinalAnswerValidator(h) => hooks.final_answer_validator.push(h.clone()),
```

4. Add `kind_name` arm (around line 1308):

```rust
            HookKind::FinalAnswerValidator(_) => "FinalAnswerValidator",
```

- [ ] **Step 4: Implement `PyFinalAnswerValidatorWrapper`**

In `src/core/pyhooks.rs`, add a new section (before the `HookKind` enum definition):

```rust
// ── FinalAnswerValidator ─────────────────────────────────────────────────────

/// Python callable wrapper for `FinalAnswerValidator`.
///
/// callback signature: `callback(ctx: dict) -> None | str | dict`
/// - None → accept the answer
/// - str → reject with code="rejected", message=<returned str>
/// - dict → reject with code=dict["code"], message=dict["message"]
pub struct PyFinalAnswerValidatorWrapper {
    callback: Arc<Py<PyAny>>,
    is_async: bool,
}

impl PyFinalAnswerValidatorWrapper {
    pub fn new(callback: Py<PyAny>) -> Self {
        let is_async = detect_async(&callback);
        Self {
            callback: Arc::new(callback),
            is_async,
        }
    }
}

impl FinalAnswerValidator for PyFinalAnswerValidatorWrapper {
    fn validate<'a>(
        &'a self,
        ctx: FinalAnswerValidationCtx<'a>,
    ) -> BoxFuture<'a, Result<(), FinalAnswerValidationError>> {
        let cb = Arc::clone(&self.callback);
        let is_async = self.is_async;
        // Serialize candidate to owned data (avoids borrowing across threads).
        let candidate_json: Value = serde_json::to_value(ctx.candidate)
            .unwrap_or(Value::Null);
        let turn_index = ctx.turn_index;

        Box::pin(async move {
            let result = Python::with_gil(|py| {
                let ctx_dict = PyDict::new(py);
                ctx_dict.set_item("candidate", value_to_pyobject(py, &candidate_json)?)?;
                ctx_dict.set_item("turn_index", turn_index)?;
                let ctx_obj = ctx_dict.into_any().unbind();

                if is_async {
                    // Schedule coroutine on the registered event loop.
                    let coro = cb.call1(py, (ctx_obj,))?;
                    crate::core::pyloop::run_coro(py, coro)
                } else {
                    // Sync callback: call directly.
                    cb.call1(py, (ctx_obj,))
                }
            });

            match result {
                Ok(obj) => {
                    let py = Python::with_gil(|py| py);
                    if obj.is_none(py) {
                        Ok(())
                    } else if let Ok(s) = obj.extract::<String>(py) {
                        Err(FinalAnswerValidationError::new("rejected", s))
                    } else {
                        // Try dict with "code" and "message"
                        let dict: Bound<PyDict> = obj.extract(py)?;
                        let code: String = dict
                            .get_item("code")?
                            .ok_or_else(|| {
                                pyo3::exceptions::PyTypeError::new_err(
                                    "validator dict must have 'code' key",
                                )
                            })?
                            .extract()?;
                        let message: String = dict
                            .get_item("message")?
                            .ok_or_else(|| {
                                pyo3::exceptions::PyTypeError::new_err(
                                    "validator dict must have 'message' key",
                                )
                            })?
                            .extract()?;
                        Err(FinalAnswerValidationError::new(code, message))
                    }
                }
                Err(e) => {
                    // Python exception in validator → treat as rejection.
                    Err(FinalAnswerValidationError::new(
                        "validator_error",
                        e.to_string(),
                    ))
                }
            }
        })
    }
}
```

- [ ] **Step 5: Add `create_final_answer_validator` factory function**

In `src/lib.rs`, after the `create_prepare_next_turn_hook` function (around line 855), add:

```rust
/// Create a `FinalAnswerValidator` from a Python callable.
///
/// callback signature: `callback(ctx: dict) -> None | str | dict`
/// - None → accept the candidate answer
/// - str → reject with code="rejected", message=<returned str>
/// - dict → reject with code=dict["code"], message=dict["message"]
#[pyfunction]
fn create_final_answer_validator<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, crate::core::pyhooks::PyHookWrapper>> {
    let wrapper = crate::core::pyhooks::PyFinalAnswerValidatorWrapper::new(callback);
    Py::new(py, crate::core::pyhooks::PyHookWrapper {
        kind: crate::core::pyhooks::HookKind::FinalAnswerValidator(Arc::new(wrapper)),
    })
    .map(|p| p.into_bound(py))
}
```

- [ ] **Step 6: Register in `lib.rs` module init**

After `create_prepare_next_turn_hook` registration (around line 242), add:

```rust
    m.add_function(wrap_pyfunction!(create_final_answer_validator, m)?)?;
```

- [ ] **Step 7: Add `final_answer_validator()` method to `PyHarnessBuilder`**

In `src/core/pybuilder.rs`, in the `#[pymethods]` impl, after `final_answer_mode` (around line 309), add:

```rust
    /// Register a `FinalAnswerValidator` (without wrapping in a Plugin).
    ///
    /// Multiple calls accumulate validators. A rejected candidate is never
    /// committed; the loop retries (letting the model generate a new answer).
    #[pyo3(text_signature = "($self, validator)")]
    fn final_answer_validator<'a>(
        mut slf: PyRefMut<'a, Self>,
        validator: &Bound<'_, PyHookWrapper>,
    ) -> PyResult<PyRefMut<'a, Self>> {
        if let Some(b) = slf.builder.take() {
            let mut harness_hooks = llm_harness_agent::HarnessHooks::none();
            validator.borrow().push_into(&mut harness_hooks);
            slf.builder = Some(b.hooks(harness_hooks));
        }
        Ok(slf)
    }
```

- [ ] **Step 8: Add to `__init__.py` hooks submodule**

In `senza-pkg/senza/__init__.py`, in the `_hooks` SimpleNamespace (around line 427), add:

```python
    final_answer_validator=create_final_answer_validator,
```

Also add `del create_final_answer_validator` in the cleanup section.

- [ ] **Step 9: Add stubs to `__init__.pyi`**

In the `hooks` class (around line 461), add:

```python
    def final_answer_validator(
        callback: Callable[[dict], Optional[Union[str, dict]]],
    ) -> Hook: ...
```

In the `HarnessBuilder` class, after `final_answer_mode` (line 579), add:

```python
    def final_answer_validator(self, validator: Hook) -> HarnessBuilder: ...
```

- [ ] **Step 10: Build and run tests**

Run: `maturin develop && python -m pytest tests/test_final_answer_validator.py -v`
Expected: PASS

- [ ] **Step 11: Verify stubs**

Run: `python scripts/check_stubs.py`
Expected: zero discrepancies

- [ ] **Step 12: Commit**

```bash
git add src/core/pyhooks.rs src/core/pybuilder.rs src/lib.rs senza-pkg/senza/__init__.py senza-pkg/senza/__init__.pyi tests/test_final_answer_validator.py
git commit -m "feat: expose FinalAnswerValidator Python binding"
```

---

## Task 10: Final verification and cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run all tests**

Run: `maturin develop && python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 2: Run stub check**

Run: `python scripts/check_stubs.py`
Expected: zero discrepancies

- [ ] **Step 3: Verify no old API in docs**

Run: `grep -rn "create_openai_provider\|create_anthropic_provider\|create_before_turn_hook\|create_safety_defaults_plugin\|create_local_knowledge_source\|create_knowledge_plugin\|create_in_memory_store\|create_memory_plugin\|create_rule_chain\|create_contains_predicate\|create_jsonl_audit_sink\|create_seatbelt_sandbox" README.md docs/ SENZA_DESIGN.md`
Expected: no output

- [ ] **Step 4: Verify Rust formatting**

Run: `cargo fmt`

- [ ] **Step 5: Verify clippy**

Run: `cargo clippy -- -D warnings`
Expected: no new warnings

- [ ] **Step 6: Smoke test all new APIs**

Run:
```bash
python -c "
import senza

# __doc__ and __all__
assert senza.__doc__
assert 'HarnessBuilder' in senza.__all__

# EventType
assert senza.EventType.TEXT_DELTA == 'text_delta'

# create_tool with parameters= and single-arg callback
tool = senza.create_tool('t', 'd', {'type': 'object', 'properties': {}}, lambda a: None)
assert tool.name == 't'

# tools() plural
t1 = senza.create_tool('t1', 'd', {'type': 'object', 'properties': {}}, lambda a, c: None)
t2 = senza.create_tool('t2', 'd', {'type': 'object', 'properties': {}}, lambda a, c: None)
senza.HarnessBuilder('gpt-4o').tools([t1, t2])

# help() shows signature
import inspect
sig = inspect.signature(senza.HarnessBuilder.__init__)
assert 'model' in str(sig)

# session_repo
import tempfile
with tempfile.TemporaryDirectory() as d:
    repo = senza.knowledge.jsonl_session_repo(d)
    assert repo is not None
    assert hasattr(senza.HarnessBuilder, 'session_repo')

# final_answer_validator
hook = senza.hooks.final_answer_validator(lambda ctx: None)
assert hook is not None
assert hasattr(senza.HarnessBuilder, 'final_answer_validator')

print('All smoke tests passed!')
"
```
Expected: "All smoke tests passed!"

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: final verification and cleanup for DX optimization"
```
