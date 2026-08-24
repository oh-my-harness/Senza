# Runtime Crate Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Senza from runtime rev `c1a8273` (2026-08-12) to `03aed0c` (2026-08-21), adapting to the crate split, rename, and spawn API rewrite.

**Architecture:** The `llm-harness-runtime` crate has been deleted and split into `llm-harness-subagents` + `llm-harness-workflow` + `llm-harness-platform`. Ten sub-crates dropped the `-runtime` suffix. `HarnessBuilder` and `UsageLedger` moved from `llm-harness-runtime` to `llm-harness-agent`. The spawn hook model replaced `AsyncSpawnHook`/`IdleWatcher`/3 manual setters with a single `SpawnPlugin` that self-registers 4 hooks. The migration is mechanical path replacement for 20 files plus one semantic rewrite of `pyspawn.rs`.

**Tech Stack:** Rust 2024 edition, pyo3 0.29, Cargo git dependencies

**Spec:** No separate spec doc — this plan is self-contained. The authoritative reference is the runtime repo at rev `03aed0c`.

## Global Constraints

- Runtime git rev for ALL dependencies: `03aed0ce550aa0c95cb26d9667f6440bc3dd3349`
- Crate `llm-harness-runtime` no longer exists — do not reference it
- `llm-harness-sandbox` now contains `os`, `bwrap`, and `seatbelt` modules behind features (default = all three). Previously these were 3 separate crates.
- `HarnessBuilder` now lives in `llm_harness_agent` (re-exported at crate root: `llm_harness_agent::HarnessBuilder`)
- `UsageLedger` now lives in `llm_harness_agent::harness::cost` (re-exported as `llm_harness_agent::UsageLedger`)
- Spawn API: `message_bus_pair()`, `async_spawn_pair()`, `AsyncSpawnHook`, `IdleWatcher`, `set_idle_watcher()`, `set_async_spawn_hook()`, `set_abort_cascade_hook()` are ALL DELETED. Replaced by `MessageBus::new()` (returns `Arc<Self>`) + `SpawnPlugin::new(bus)` (returns `Arc<SpawnPlugin>`)
- `HarnessBuilderMcpExt` trait still exists at `llm_harness_mcp::builder::HarnessBuilderMcpExt`
- `EnvFactory` is re-exported by `llm_harness_subagents::EnvFactory` (origin: `llm_harness_platform::env::EnvFactory`)
- Branch: `feat/runtime-crate-migration` (created from `main`)

---

## File Structure

### Files modified (no new files created):

| File | Responsibility | Change type |
|---|---|---|
| `Cargo.toml` | Dependency declarations | Rename 12 crates, add 3 new, delete 1, update rev |
| `src/lib.rs` | Top-level pyo3 module | Import path replacement (2 lines) |
| `src/core/pybuilder.rs` | Python-facing HarnessBuilder wrapper | Import path replacement (8 lines) |
| `src/core/pyeventstream.rs` | Event stream Python wrapper | Import path replacement (2 lines) |
| `src/core/pyharness.rs` | AgentHarness Python wrapper | Import path replacement (2 lines) |
| `src/infra/pysandbox.rs` | Sandbox Python wrapper | Import path replacement (2 lines) |
| `src/infra/pytrace.rs` | Trace exporter Python wrapper | Import path replacement (2 lines) |
| `src/infra/pyaudit.rs` | Audit sink Python wrapper | Import path replacement (1 line) |
| `src/knowledge/pyknowledge.rs` | Knowledge plugin Python wrapper | Import path replacement (10 lines) |
| `src/knowledge/pylocalsource.rs` | Local knowledge source wrapper | Import path replacement (8 lines) |
| `src/knowledge/pymemory.rs` | Memory plugin Python wrapper | Import path replacement (5 lines) |
| `src/knowledge/pysessionrecall.rs` | Session recall Python wrapper | Import path replacement (12 lines) |
| `src/runtime/pymcp.rs` | MCP Python wrapper | Import path replacement (2 lines) |
| `src/runtime/pyrules.rs` | Rules Python wrapper | Import path replacement (1 line) |
| `src/runtime/pyspawn.rs` | Spawn wiring for Python `enable_spawn()` | **Semantic rewrite** of `wire_spawn()` + `SpawnWiring` |
| `src/runtime/pyworkflow.rs` | Workflow engine Python wrapper | Import path replacement (10 lines) |
| `src/shared/pyerror.rs` | Error conversion helpers | Import path replacement (2 lines) |
| `src/strategy/pyaudit.rs` | Strategy audit plugin | Import path replacement (1 line) |
| `src/strategy/pyeventstreams.rs` | Strategy event stream tool | Import path replacement (2 lines) |
| `tests/workflow_integration.rs` | Workflow integration test | Import path replacement (4 lines) |

---

## Task 1: Update Cargo.toml

**Files:**
- Modify: `Cargo.toml:14-50`

**Interfaces:**
- Produces: Updated dependency declarations that all subsequent tasks rely on for `use` statement resolution.

- [ ] **Step 1: Update all dependency entries**

Replace the entire `[dependencies]` runtime section (lines 14-28) and platform-specific sections (lines 42, 45) and dev-dependencies (line 50).

New `[dependencies]` runtime entries (replacing lines 14-28):

```toml
llm-harness-types   = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-loop    = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-agent   = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-platform = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-subagents = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-workflow = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-sandbox = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-tools = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-mcp = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
session-viewer     = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-strategy = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-knowledge = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-knowledge-local = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-session-recall = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349", features = ["sqlite-bundled"] }
llm-harness-memory = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-audit-jsonl = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
llm-harness-trace-otel = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349" }
```

New platform-specific sections (replacing lines 41-45):

```toml
[target.'cfg(target_os = "linux")'.dependencies]
# llm-harness-sandbox already in [dependencies]; bwrap feature is on by default.

[target.'cfg(target_os = "macos")'.dependencies]
# llm-harness-sandbox already in [dependencies]; seatbelt feature is on by default.
```

New dev-dependencies line (replacing line 50):

```toml
llm-harness-loop = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "03aed0ce550aa0c95cb26d9667f6440bc3dd3349", features = ["test-utils"] }
```

Key changes:
- Deleted: `llm-harness-runtime` (crate no longer exists)
- Deleted: `llm-harness-runtime-sandbox-os`, `llm-harness-runtime-sandbox-bwrap`, `llm-harness-runtime-sandbox-seatbelt` (merged into `llm-harness-sandbox`)
- Added: `llm-harness-platform`, `llm-harness-subagents`, `llm-harness-workflow`
- Renamed: all `llm-harness-runtime-*` → `llm-harness-*` (drop `-runtime` suffix)
- Updated: all rev → `03aed0ce550aa0c95cb26d9667f6440bc3dd3349`

- [ ] **Step 2: Verify Cargo.toml parses**

Run: `cargo metadata --format-version 1 --no-deps 2>&1 | head -5`
Expected: JSON output starting with `{"packages":[`, no errors about unknown crates.

- [ ] **Step 3: Commit**

```bash
git add Cargo.toml
git commit -m "cargo: update runtime deps to rev 03aed0c (crate split + rename)"
```

---

## Task 2: Migrate import paths — core files

**Files:**
- Modify: `src/lib.rs`
- Modify: `src/core/pybuilder.rs`
- Modify: `src/core/pyeventstream.rs`
- Modify: `src/core/pyharness.rs`

**Interfaces:**
- Consumes: Task 1's updated Cargo.toml crate names
- Produces: Correct import paths for `HarnessBuilder`, `UsageLedger`, `workflow`, `lifecycle` modules used by later tasks.

**Path mapping (authoritative reference for all import tasks):**

```
llm_harness_runtime::builder::HarnessBuilder           → llm_harness_agent::HarnessBuilder
llm_harness_runtime::control::cost::UsageLedger        → llm_harness_agent::UsageLedger
llm_harness_runtime::workflow::*                       → llm_harness_workflow::workflow::*
llm_harness_runtime::lifecycle::*                      → llm_harness_workflow::lifecycle::*
llm_harness_runtime::rules::*                          → llm_harness_workflow::rules::*
llm_harness_runtime::spawn::*                          → llm_harness_subagents::*
llm_harness_runtime::platform::sandbox::*              → llm_harness_platform::sandbox::*
llm_harness_runtime::observability::tracer::*          → llm_harness_platform::tracer::*
llm_harness_runtime_knowledge::*                       → llm_harness_knowledge::*
llm_harness_runtime_knowledge_local::*                 → llm_harness_knowledge_local::*
llm_harness_runtime_memory::*                          → llm_harness_memory::*
llm_harness_runtime_session_recall::*                  → llm_harness_session_recall::*
llm_harness_runtime_mcp::*                             → llm_harness_mcp::*
llm_harness_runtime_tools::*                           → llm_harness_tools::*
llm_harness_runtime_audit_jsonl::*                     → llm_harness_audit_jsonl::*
llm_harness_runtime_trace_otel::*                      → llm_harness_trace_otel::*
llm_harness_runtime_sandbox_os::*                      → llm_harness_sandbox::os::*
llm_harness_runtime_sandbox_seatbelt::SeatbeltSandbox  → llm_harness_sandbox::SeatbeltSandbox
llm_harness_runtime_sandbox_bwrap::BwrapSandbox        → llm_harness_sandbox::BwrapSandbox
```

- [ ] **Step 1: Update `src/lib.rs`**

Line 5: `use llm_harness_runtime::workflow::executor::{HttpCallExecutor, HttpCallPolicy, ShellExecutor};`
→ `use llm_harness_workflow::workflow::executor::{HttpCallExecutor, HttpCallPolicy, ShellExecutor};`

Line 6: `use llm_harness_runtime_sandbox_os::OsEnv;`
→ `use llm_harness_sandbox::os::OsEnv;`

Line 486: `as Arc<dyn llm_harness_runtime::workflow::judge::StepTransitionJudge>,`
→ `as Arc<dyn llm_harness_workflow::workflow::judge::StepTransitionJudge>,`

Line 624: `llm_harness_runtime_tools::FileSnapshotStore::new(),`
→ `llm_harness_tools::FileSnapshotStore::new(),`

Line 627: `Arc::new(llm_harness_runtime_tools::FsToolsPlugin::new(Some(store)));`
→ `Arc::new(llm_harness_tools::FsToolsPlugin::new(Some(store)));`

- [ ] **Step 2: Update `src/core/pybuilder.rs`**

Line 17: `use llm_harness_runtime::builder::HarnessBuilder;`
→ `use llm_harness_agent::HarnessBuilder;`

Line 18: `use llm_harness_runtime_knowledge::{KnowledgeAccessContext, KnowledgeScope, PrincipalRef};`
→ `use llm_harness_knowledge::{KnowledgeAccessContext, KnowledgeScope, PrincipalRef};`

Line 19: `use llm_harness_runtime_mcp::builder::HarnessBuilderMcpExt;`
→ `use llm_harness_mcp::builder::HarnessBuilderMcpExt;`

Line 48: `mcp_servers: Vec<(String, llm_harness_runtime_mcp::config::McpServerConfig)>,`
→ `mcp_servers: Vec<(String, llm_harness_mcp::config::McpServerConfig)>,`

Line 52: `mcp_manager: Option<Arc<llm_harness_runtime_mcp::manager::McpManager>>,`
→ `mcp_manager: Option<Arc<llm_harness_mcp::manager::McpManager>>,`

Line 565: `let ledger = llm_harness_runtime::control::cost::UsageLedger::default();`
→ `let ledger = llm_harness_agent::UsageLedger::default();`

Line 838 (doc comment): `Wraps \`llm_harness_runtime::control::cost::UsageLedger\``
→ `Wraps \`llm_harness_agent::UsageLedger\``

Line 845: `pub(crate) ledger: llm_harness_runtime::control::cost::UsageLedger,`
→ `pub(crate) ledger: llm_harness_agent::UsageLedger,`

Line 853: `ledger: llm_harness_runtime::control::cost::UsageLedger::default(),`
→ `ledger: llm_harness_agent::UsageLedger::default(),`

- [ ] **Step 3: Update `src/core/pyeventstream.rs`**

Line 9: `use llm_harness_runtime::lifecycle::event::{Event, EventStream, WaitForExternalEventTool};`
→ `use llm_harness_workflow::lifecycle::event::{Event, EventStream, WaitForExternalEventTool};`

Line 10: `use llm_harness_runtime::lifecycle::task::TaskId;`
→ `use llm_harness_workflow::lifecycle::task::TaskId;`

- [ ] **Step 4: Update `src/core/pyharness.rs`**

Line 19: `use llm_harness_runtime_knowledge::{KnowledgeAccessContext, KnowledgeScope, PrincipalRef};`
→ `use llm_harness_knowledge::{KnowledgeAccessContext, KnowledgeScope, PrincipalRef};`

Line 20: `use llm_harness_runtime_mcp::builder::McpAgentHarness;`
→ `use llm_harness_mcp::builder::McpAgentHarness;`

- [ ] **Step 5: Run cargo check to verify these files compile (expect errors in other files)**

Run: `cargo check 2>&1 | grep -E "^error" | head -20`
Expected: Errors in files NOT yet migrated (infra/, knowledge/, runtime/, etc.) but NO errors in the 4 files modified in this task.

- [ ] **Step 6: Commit**

```bash
git add src/lib.rs src/core/pybuilder.rs src/core/pyeventstream.rs src/core/pyharness.rs
git commit -m "migrate core import paths to new crate layout"
```

---

## Task 3: Migrate import paths — infra files

**Files:**
- Modify: `src/infra/pysandbox.rs`
- Modify: `src/infra/pytrace.rs`
- Modify: `src/infra/pyaudit.rs`

**Interfaces:**
- Consumes: Task 1's updated Cargo.toml crate names

- [ ] **Step 1: Update `src/infra/pysandbox.rs`**

Line 13: `use llm_harness_runtime::platform::sandbox::{ResourceLimits, Sandbox, SandboxConfig};`
→ `use llm_harness_platform::sandbox::{ResourceLimits, Sandbox, SandboxConfig};`

Line 139: `let sandbox = llm_harness_runtime_sandbox_seatbelt::SeatbeltSandbox::new(cfg);`
→ `let sandbox = llm_harness_sandbox::SeatbeltSandbox::new(cfg);`

Line 158: `let sandbox = llm_harness_runtime_sandbox_bwrap::BwrapSandbox::new(cfg)`
→ `let sandbox = llm_harness_sandbox::BwrapSandbox::new(cfg)`

- [ ] **Step 2: Update `src/infra/pytrace.rs`**

Line 3 (doc comment): `Wraps \`llm_harness_runtime_trace_otel::InMemoryTraceExporter\`,`
→ `Wraps \`llm_harness_trace_otel::InMemoryTraceExporter\`,`

Line 6: `use llm_harness_runtime::observability::tracer::{AttributeValue, SpanEvent, SpanKind, SpanStatus};`
→ `use llm_harness_platform::tracer::{AttributeValue, SpanEvent, SpanKind, SpanStatus};`

Line 7: `use llm_harness_runtime_trace_otel::InMemoryTraceExporter;`
→ `use llm_harness_trace_otel::InMemoryTraceExporter;`

- [ ] **Step 3: Update `src/infra/pyaudit.rs`**

Line 3 (doc comment): `Wraps \`llm_harness_runtime_audit_jsonl::JsonlAuditSink\`,`
→ `Wraps \`llm_harness_audit_jsonl::JsonlAuditSink\`,`

Line 9: `use llm_harness_runtime_audit_jsonl::JsonlAuditSink;`
→ `use llm_harness_audit_jsonl::JsonlAuditSink;`

- [ ] **Step 4: Commit**

```bash
git add src/infra/pysandbox.rs src/infra/pytrace.rs src/infra/pyaudit.rs
git commit -m "migrate infra import paths to new crate layout"
```

---

## Task 4: Migrate import paths — knowledge files

**Files:**
- Modify: `src/knowledge/pyknowledge.rs`
- Modify: `src/knowledge/pylocalsource.rs`
- Modify: `src/knowledge/pymemory.rs`
- Modify: `src/knowledge/pysessionrecall.rs`

**Interfaces:**
- Consumes: Task 1's updated Cargo.toml crate names

- [ ] **Step 1: Update `src/knowledge/pyknowledge.rs`**

Replace all occurrences of `llm_harness_runtime_knowledge` → `llm_harness_knowledge` in this file. There are 10 occurrences on lines 24, 25, 29, 36, 52, 54, 66, 68, 73, 81.

- [ ] **Step 2: Update `src/knowledge/pylocalsource.rs`**

Replace all occurrences of `llm_harness_runtime_knowledge` → `llm_harness_knowledge` (lines 11, 50, 51, 66) and `llm_harness_runtime_knowledge_local` → `llm_harness_knowledge_local` (lines 36, 41, 48, 49, 56).

- [ ] **Step 3: Update `src/knowledge/pymemory.rs`**

Line 4: `use llm_harness_runtime_knowledge::{KnowledgeError, KnowledgeRef, KnowledgeRequestContext};`
→ `use llm_harness_knowledge::{KnowledgeError, KnowledgeRef, KnowledgeRequestContext};`

Line 5: `use llm_harness_runtime_memory::{`
→ `use llm_harness_memory::{`

Line 50: `llm_harness_runtime_knowledge_local::content_revision(write.content.as_bytes());`
→ `llm_harness_knowledge_local::content_revision(write.content.as_bytes());`

Line 216: `let access_control = Arc::new(llm_harness_runtime_knowledge::KnowledgeAccessControl::new(`
→ `let access_control = Arc::new(llm_harness_knowledge::KnowledgeAccessControl::new(`

Line 217: `Arc::new(llm_harness_runtime_knowledge::AllowAllAuthorizer),`
→ `Arc::new(llm_harness_knowledge::AllowAllAuthorizer),`

Line 220: `let service = llm_harness_runtime_memory::MemoryService::new(`
→ `let service = llm_harness_memory::MemoryService::new(`

Line 230: `llm_harness_runtime_memory::MemoryPlugin::new(Arc::new(service)),`
→ `llm_harness_memory::MemoryPlugin::new(Arc::new(service)),`

- [ ] **Step 4: Update `src/knowledge/pysessionrecall.rs`**

Replace all occurrences:
- `llm_harness_runtime_session_recall` → `llm_harness_session_recall` (lines 11, 26, 37, 48, 49, 60, 62, 108, 115, 144, 146, 192)
- `llm_harness_runtime_knowledge` → `llm_harness_knowledge` (lines 37, 103, 104)

- [ ] **Step 5: Commit**

```bash
git add src/knowledge/pyknowledge.rs src/knowledge/pylocalsource.rs src/knowledge/pymemory.rs src/knowledge/pysessionrecall.rs
git commit -m "migrate knowledge import paths to new crate layout"
```

---

## Task 5: Migrate import paths — runtime files (except pyspawn.rs)

**Files:**
- Modify: `src/runtime/pymcp.rs`
- Modify: `src/runtime/pyrules.rs`
- Modify: `src/runtime/pyworkflow.rs`

**Interfaces:**
- Consumes: Task 1's updated Cargo.toml crate names

- [ ] **Step 1: Update `src/runtime/pymcp.rs`**

Line 10: `use llm_harness_runtime_mcp::config::{McpConfigFile, McpServerConfig};`
→ `use llm_harness_mcp::config::{McpConfigFile, McpServerConfig};`

Line 11: `use llm_harness_runtime_mcp::manager::{ConnectionStatus, McpManager};`
→ `use llm_harness_mcp::manager::{ConnectionStatus, McpManager};`

- [ ] **Step 2: Update `src/runtime/pyrules.rs`**

Line 10: `use llm_harness_runtime::rules::{`
→ `use llm_harness_workflow::rules::{`

- [ ] **Step 3: Update `src/runtime/pyworkflow.rs`**

Line 14: `use llm_harness_runtime::builder::HarnessBuilder;`
→ `use llm_harness_agent::HarnessBuilder;`

Line 15: `use llm_harness_runtime::lifecycle::task::TaskId;`
→ `use llm_harness_workflow::lifecycle::task::TaskId;`

Line 16: `use llm_harness_runtime::lifecycle::task_store::{JsonlTaskStore, TaskStore, TaskSummary};`
→ `use llm_harness_workflow::lifecycle::task_store::{JsonlTaskStore, TaskStore, TaskSummary};`

Line 17: `use llm_harness_runtime::spawn::spawner::{EnvFactory, JsonlSessionFactory};`
→ `use llm_harness_subagents::spawner::{EnvFactory, JsonlSessionFactory};`

Line 18: `use llm_harness_runtime::workflow::engine::{WorkflowEngine, WorkflowEngineConfig, WorkflowEvent};`
→ `use llm_harness_workflow::workflow::engine::{WorkflowEngine, WorkflowEngineConfig, WorkflowEvent};`

Line 19: `use llm_harness_runtime::workflow::error::WorkflowError;`
→ `use llm_harness_workflow::workflow::error::WorkflowError;`

Line 20: `use llm_harness_runtime::workflow::executor::{ExecutorCtx, StepExecutor};`
→ `use llm_harness_workflow::workflow::executor::{ExecutorCtx, StepExecutor};`

Line 21: `use llm_harness_runtime::workflow::judge::{EdgeConditionJudge, StepCtx, StepTransitionJudge};`
→ `use llm_harness_workflow::workflow::judge::{EdgeConditionJudge, StepCtx, StepTransitionJudge};`

Line 22: `use llm_harness_runtime::workflow::model::{`
→ `use llm_harness_workflow::workflow::model::{`

Line 403: `structured_status: &llm_harness_runtime::workflow::model::StructuredStatus,`
→ `structured_status: &llm_harness_workflow::workflow::model::StructuredStatus,`

Line 788: `use llm_harness_runtime::workflow::engine::StepProgress;`
→ `use llm_harness_workflow::workflow::engine::StepProgress;`

Line 1091: `s: &llm_harness_runtime::workflow::model::StructuredStatus,`
→ `s: &llm_harness_workflow::workflow::model::StructuredStatus,`

Line 1093: `use llm_harness_runtime::workflow::model::StructuredStatus;`
→ `use llm_harness_workflow::workflow::model::StructuredStatus;`

Line 2081: `use llm_harness_runtime::workflow::model::{Step, StepExecutionPolicy, Workflow};`
→ `use llm_harness_workflow::workflow::model::{Step, StepExecutionPolicy, Workflow};`

- [ ] **Step 4: Commit**

```bash
git add src/runtime/pymcp.rs src/runtime/pyrules.rs src/runtime/pyworkflow.rs
git commit -m "migrate runtime import paths to new crate layout"
```

---

## Task 6: Migrate import paths — shared + strategy files

**Files:**
- Modify: `src/shared/pyerror.rs`
- Modify: `src/strategy/pyaudit.rs`
- Modify: `src/strategy/pyeventstreams.rs`

**Interfaces:**
- Consumes: Task 1's updated Cargo.toml crate names

- [ ] **Step 1: Update `src/shared/pyerror.rs`**

Line 148: `use llm_harness_runtime::lifecycle::task::TaskError;`
→ `use llm_harness_workflow::lifecycle::task::TaskError;`

Line 149: `use llm_harness_runtime::workflow::error::WorkflowError as RustWorkflowError;`
→ `use llm_harness_workflow::workflow::error::WorkflowError as RustWorkflowError;`

- [ ] **Step 2: Update `src/strategy/pyaudit.rs`**

Line 22: `let sink = Arc::new(llm_harness_runtime_audit_jsonl::JsonlAuditSink::new(`
→ `let sink = Arc::new(llm_harness_audit_jsonl::JsonlAuditSink::new(`

- [ ] **Step 3: Update `src/strategy/pyeventstreams.rs`**

Line 8: `use llm_harness_runtime::lifecycle::event::WaitForExternalEventTool;`
→ `use llm_harness_workflow::lifecycle::event::WaitForExternalEventTool;`

Line 9: `use llm_harness_runtime::lifecycle::task::TaskId;`
→ `use llm_harness_workflow::lifecycle::task::TaskId;`

- [ ] **Step 4: Commit**

```bash
git add src/shared/pyerror.rs src/strategy/pyaudit.rs src/strategy/pyeventstreams.rs
git commit -m "migrate shared+strategy import paths to new crate layout"
```

---

## Task 7: Migrate import paths — test file

**Files:**
- Modify: `tests/workflow_integration.rs`

**Interfaces:**
- Consumes: Task 1's updated Cargo.toml crate names

- [ ] **Step 1: Update `tests/workflow_integration.rs`**

Line 9: `use llm_harness_runtime::spawn::spawner::{EnvFactory, JsonlSessionFactory};`
→ `use llm_harness_subagents::spawner::{EnvFactory, JsonlSessionFactory};`

Line 10: `use llm_harness_runtime::workflow::engine::{WorkflowEngine, WorkflowEngineConfig};`
→ `use llm_harness_workflow::workflow::engine::{WorkflowEngine, WorkflowEngineConfig};`

Line 11: `use llm_harness_runtime::workflow::judge::StepTransitionJudge;`
→ `use llm_harness_workflow::workflow::judge::StepTransitionJudge;`

Line 12: `use llm_harness_runtime::workflow::model::{Edge, Step, Workflow};`
→ `use llm_harness_workflow::workflow::model::{Edge, Step, Workflow};`

- [ ] **Step 2: Commit**

```bash
git add tests/workflow_integration.rs
git commit -m "migrate test import paths to new crate layout"
```

---

## Task 8: Rewrite pyspawn.rs — SpawnPlugin migration

**Files:**
- Modify: `src/runtime/pyspawn.rs` (full rewrite of `wire_spawn()` + `SpawnWiring`)

**Interfaces:**
- Consumes: `llm_harness_subagents::message_bus::{MessageBus, MAIN_AGENT_ID}`, `llm_harness_subagents::plugin::SpawnPlugin`, `llm_harness_subagents::spawner::{HarnessSubAgentSpawner, JsonlSessionFactory, EnvFactory}`, `llm_harness_subagents::tools::{SpawnAgentTool, MessageSubagentTool, AwaitSubagentReplyTool, QuerySubagentTool, AbortSubagentTool}`, `llm_harness_subagents::delivery::SubAgentMessageConverter`, `llm_harness_agent::HarnessBuilder`, `llm_harness_sandbox::os::OsEnvFactory`
- Produces: `wire_spawn(builder, cfg) -> (HarnessBuilder, Option<SpawnWiring>)` with same signature shape, `SpawnWiring::post_build(harness: &Arc<AgentHarness>)` with same signature.

**Key API changes:**
- `message_bus_pair()` → `MessageBus::new()` (returns `Arc<MessageBus>`)
- `async_spawn_pair(bus)` → `SpawnPlugin::new(bus)` (returns `Arc<SpawnPlugin>`)
- `builder.after_turn_hook(async_hook)` + `.convert_to_llm(...)` → `builder.install(plugin.as_ref())` + `.convert_to_llm(...)`
- `SpawnWiring { bus, async_hook }` → `SpawnWiring { bus, plugin }`
- `post_build`: `set_idle_watcher` + `set_async_spawn_hook` + `set_abort_cascade_hook` → `plugin.set_harness_weak(Arc::downgrade(harness))`

- [ ] **Step 1: Rewrite imports (lines 1-28)**

Replace lines 17-27:

```rust
use llm_harness_agent::HarnessBuilder;
use llm_harness_subagents::delivery::SubAgentMessageConverter;
use llm_harness_subagents::message_bus::{MAIN_AGENT_ID, MessageBus};
use llm_harness_subagents::plugin::SpawnPlugin;
use llm_harness_subagents::spawner::{HarnessSubAgentSpawner, JsonlSessionFactory};
use llm_harness_subagents::tools::{
    AbortSubagentTool, AwaitSubagentReplyTool, MessageSubagentTool, QuerySubagentTool,
    SpawnAgentTool,
};
use llm_harness_sandbox::os::OsEnvFactory;
use llm_harness_types::Tool;
```

Keep lines 1-16 unchanged (stdlib + `use llm_harness_agent::{AgentHarness, Plugin};` + `use llm_harness_loop::convert::DefaultConvertToLlm;`).

- [ ] **Step 2: Rewrite `SpawnWiring` struct (lines 30-56)**

Replace the entire `SpawnWiring` struct and its `impl` block:

```rust
/// Post-build spawn wiring state. Held across `build()` and applied
/// to the constructed `AgentHarness`.
pub(crate) struct SpawnWiring {
    plugin: Arc<SpawnPlugin>,
}

impl SpawnWiring {
    /// Apply post-build: link the SpawnPlugin to the harness via weak ref.
    /// Must be called after `build()` returns the harness.
    pub(crate) fn post_build(&self, harness: &Arc<AgentHarness>) {
        self.plugin.set_harness_weak(Arc::downgrade(harness));
    }
}
```

Rationale: `SpawnPlugin` internally owns the `MessageBus` reference and registers 4 hooks (`BeforeRun`, `AfterTurn`, `AfterRun`, `OnAbort`) via `Plugin::register_hooks`. The `set_harness_weak` call gives the plugin a `Weak<AgentHarness>` so it can call `continue_run()` when sub-agent events arrive. This replaces the 3 deleted setters.

- [ ] **Step 3: Rewrite `wire_spawn()` function (lines 67-108)**

Replace the entire function body:

```rust
/// Wire spawn infrastructure into the builder and return post-build wiring state.
///
/// - Adds `SpawnAgentTool`, `MessageSubagentTool`, `AwaitSubagentReplyTool`,
///   `QuerySubagentTool`, `AbortSubagentTool` to the builder.
/// - Installs `SpawnPlugin` (registers before_run, after_turn, after_run,
///   on_abort hooks that manage sub-agent event delivery and idle wakeup).
/// - Sets `convert_to_llm(DefaultConvertToLlm + SubAgentMessageConverter)`.
/// - Returns `(modified_builder, SpawnWiring)` for post-build hook application.
pub(crate) fn wire_spawn(
    mut builder: HarnessBuilder,
    cfg: crate::core::pybuilder::SpawnConfig,
) -> (HarnessBuilder, Option<SpawnWiring>) {
    // 1. Message bus (Arc<MessageBus>, no event channel).
    let bus = MessageBus::new();

    // 2. Spawner.
    let spawner = HarnessSubAgentSpawner::new(
        cfg.model,
        cfg.client,
        cfg.session_dir,
        bus.clone(),
        |_cwd: &Path, _bus, _agent_id: &str| Box::new(NoopPlugin) as Box<dyn Plugin>,
    )
    .env_factory(Arc::new(OsEnvFactory))
    .session_factory(Arc::new(JsonlSessionFactory));
    let spawner = Arc::new(spawner);

    // 3. SpawnPlugin — replaces AsyncSpawnHook + IdleWatcher + AbortCascadeHook.
    let plugin = SpawnPlugin::new(bus.clone());

    // 4. Register tools + install plugin + convert_to_llm.
    builder = builder
        .tool(Arc::new(SpawnAgentTool::new(spawner.clone())) as Arc<dyn Tool>)
        .tool(Arc::new(MessageSubagentTool::new(bus.clone(), MAIN_AGENT_ID)) as Arc<dyn Tool>)
        .tool(Arc::new(AwaitSubagentReplyTool::new(bus.clone(), MAIN_AGENT_ID)) as Arc<dyn Tool>)
        .tool(Arc::new(QuerySubagentTool::new(bus.clone())) as Arc<dyn Tool>)
        .tool(Arc::new(AbortSubagentTool::new(bus.clone())) as Arc<dyn Tool>)
        .install(plugin.as_ref())
        .convert_to_llm(Some(Arc::new(
            DefaultConvertToLlm::new().with_custom_converter(Arc::new(SubAgentMessageConverter)),
        )));

    (builder, Some(SpawnWiring { plugin }))
}
```

Key changes:
- `message_bus_pair()` → `MessageBus::new()` (returns `Arc<Self>`, no event channel)
- `async_spawn_pair(bus)` → `SpawnPlugin::new(bus)` (returns `Arc<SpawnPlugin>`)
- `builder.after_turn_hook(async_hook)` → `builder.install(plugin.as_ref())` (plugin self-registers all 4 hooks)
- `SpawnWiring { bus, async_hook }` → `SpawnWiring { plugin }` (bus is owned by plugin internally)
- The `bus` variable is still cloned for the tools that need it directly (`MessageSubagentTool`, etc.)

- [ ] **Step 4: Run cargo check to verify compilation**

Run: `cargo check 2>&1 | grep -E "^error" | head -20`
Expected: No errors. All import paths should now be correct across the entire codebase.

If errors remain, they are likely in files this plan covers — verify all replacements were applied. Common missed patterns:
- Doc comments containing `llm_harness_runtime` (not just `use` statements)
- Inline type annotations like `Arc<dyn llm_harness_runtime::workflow::judge::StepTransitionJudge>`

- [ ] **Step 5: Commit**

```bash
git add src/runtime/pyspawn.rs
git commit -m "rewrite pyspawn: AsyncSpawnHook/IdleWatcher → SpawnPlugin"
```

---

## Task 9: Full compilation check and fix residual errors

**Files:**
- Potentially any file with a missed `llm_harness_runtime` reference

**Interfaces:**
- Consumes: All previous tasks

- [ ] **Step 1: Search for any remaining old references**

Run this search for `llm_harness_runtime` (the crate name, not the underscore-separated module paths already fixed):

Pattern to search: `llm_harness_runtime` in all `*.rs` files under `src/` and `tests/`.

Any remaining match is either:
- A doc comment (update it)
- A missed `use` statement (fix it)
- A type annotation in function signatures (fix it)

- [ ] **Step 2: Fix any remaining references found in Step 1**

Apply the path mapping from Task 2's reference table.

- [ ] **Step 3: Run cargo check until clean**

Run: `cargo check 2>&1`
Expected: `Finished` with no errors.

- [ ] **Step 4: Run cargo build**

Run: `cargo build 2>&1 | tail -5`
Expected: `Finished` with no errors.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: residual runtime import paths"
```

---

## Task 10: Run tests and verify

**Files:**
- No file modifications expected (only if tests reveal issues)

- [ ] **Step 1: Run Rust unit tests**

Run: `cargo test 2>&1`
Expected: All tests pass. Key areas to watch:
- `tests/workflow_integration.rs` — verifies workflow + spawn imports
- Any test in `src/runtime/pyspawn.rs` if present

- [ ] **Step 2: Build the Python extension**

Run: `maturin develop 2>&1 | tail -10`
Expected: Successful build, no linker errors.

- [ ] **Step 3: Smoke test Python import**

Run: `python -c "import senza; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit if any test fixes were needed**

```bash
git add -A
git commit -m "fix: test adjustments for runtime migration"
```

If no fixes needed, no commit — the previous tasks' commits are sufficient.

---

## Self-Review

**1. Spec coverage:** The "spec" is the runtime repo at rev `03aed0c`. The three breaking changes are: (a) crate rename/split, (b) `HarnessBuilder`/`UsageLedger` relocation, (c) spawn API rewrite. Tasks 1-7 cover (a) and (b) mechanically. Task 8 covers (c) semantically. Tasks 9-10 verify. ✓

**2. Placeholder scan:** No TBD/TODO. Every step has exact file paths, line numbers, and replacement text. The `wire_spawn()` rewrite in Task 8 contains the full implementation. ✓

**3. Type consistency:** `SpawnWiring` struct defined in Task 8 Step 2 with field `plugin: Arc<SpawnPlugin>`. Used in Task 8 Step 3's return value `SpawnWiring { plugin }`. `post_build` calls `self.plugin.set_harness_weak(...)`. `SpawnPlugin::new(bus)` returns `Arc<SpawnPlugin>` and `set_harness_weak` takes `Weak<AgentHarness>` — consistent with the runtime source at HEAD. ✓
