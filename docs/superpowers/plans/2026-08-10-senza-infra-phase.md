# Senza 全量对齐 — 阶段 4：Infra 层 + 收尾 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 完成最后 4 个 infra 绑定（JsonlAuditSink、InMemoryTraceExporter、BwrapSandbox、SeatbeltSandbox），然后创建 20 个 examples 覆盖所有已暴露能力，更新 SENZA_DESIGN.md。

**Architecture:** Infra 绑定放在 `src/infra/` 子目录。Examples 按目录分组（agent/strategy/knowledge/infra）。

## Global Constraints

- Runtime pin: `5eae99ed1c42dd558529bede9957518ba15eef5c`
- PyO3 0.29
- Build: `PYO3_PYTHON="$(pwd)/.venv/bin/python" cargo build`
- Test: `.venv/bin/python -m pytest tests/ -v`
- Stub: `.venv/bin/python scripts/check_stubs.py`
- macOS (当前平台): SeatbeltSandbox 可编译，BwrapSandbox 是 stub
- `src/infra/mod.rs` 已存在（占位）

## Key API Findings

1. **JsonlAuditSink** — `JsonlAuditSink::new(path: impl Into<PathBuf>) -> Self`，已在阶段 2 的 AuditPlugin 中内部使用。阶段 4 暴露为独立 Python 类，增加 `validate(path)` 方法。
2. **InMemoryTraceExporter** — `InMemoryTraceExporter::new() -> Self`，有 `exported_spans() -> Vec<SpanEvent>`。`#[doc(hidden)]` 标注但仍是 public。`TraceExporter` trait 在 `llm_harness_runtime::observability::tracer::TraceExporter`。
3. **SeatbeltSandbox** — `SeatbeltSandbox::new(config: SandboxConfig) -> Self`，实现 `Sandbox` trait。当前 `start()` 返回 error（fail-closed，issue #97）。
4. **BwrapSandbox** — 仅 Linux 有真实实现；macOS 是 stub，`new()` 返回 error。
5. **SandboxConfig** — `{ fs_allowlist: Vec<PathBuf>, fs_denylist: Vec<PathBuf>, net_allowlist: Vec<NetRule>, resource_limits: ResourceLimits, work_dir: Option<PathBuf> }`。从 dict 构造。
6. **Sandbox** trait — `start()`, `env()`, `reset()`, `shutdown()`, `config()`, `is_running()`。

## File Structure

```
src/infra/
├── mod.rs               # re-exports
├── pyaudit.rs           # JsonlAuditSink
├── pytrace.rs           # InMemoryTraceExporter
└── pysandbox.rs         # BwrapSandbox + SeatbeltSandbox
```

---

### Task 1: JsonlAuditSink 绑定

**Files:**
- Create: `src/infra/pyaudit.rs`
- Modify: `src/infra/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_jsonl_audit_sink.py`

**Interfaces:**
- `JsonlAuditSink::new(path: impl Into<PathBuf>) -> Self`
- `JsonlAuditSink::validate(path: &Path) -> Result<usize>` — async, returns number of valid entries
- Implements `AuditSink` trait (`record(entry)`, `flush()`)
- Produces: `senza.JsonlAuditSink` class with `__init__(path)`, `validate(path) -> int` (static method)

- [ ] **Step 1: 写失败测试**

```python
import senza
import tempfile
import os


def test_jsonl_audit_sink_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        sink = senza.JsonlAuditSink(os.path.join(tmpdir, "audit.jsonl"))
        assert sink is not None


def test_jsonl_audit_sink_validate_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "audit.jsonl")
        sink = senza.JsonlAuditSink(path)
        count = senza.JsonlAuditSink.validate(path)
        assert count == 0
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pyaudit.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;

/// JSONL file-backed audit sink with SHA-256 hash-chain integrity.
#[pyclass(name = "JsonlAuditSink")]
pub struct PyJsonlAuditSink {
    pub sink: Arc<llm_harness_runtime_audit_jsonl::JsonlAuditSink>,
}

#[pymethods]
impl PyJsonlAuditSink {
    #[new]
    fn new(path: &str) -> Self {
        Self {
            sink: Arc::new(llm_harness_runtime_audit_jsonl::JsonlAuditSink::new(path)),
        }
    }

    /// Validate the hash chain of a JSONL audit log file.
    /// Returns the number of valid entries.
    #[staticmethod]
    fn validate<'py>(py: Python<'py>, path: &str) -> PyResult<Bound<'py, PyAny>> {
        let path = std::path::PathBuf::from(path);
        let rt = crate::core::pyagent::runtime(py);
        py.detach(|| {
            rt.block_on(async move {
                llm_harness_runtime_audit_jsonl::JsonlAuditSink::validate(&path)
                    .await
                    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
            })
        })
    }
}
```

Use `detach_catch_panic_result` for the async validate call.

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub:
```python
class JsonlAuditSink:
    def __new__(path: str) -> JsonlAuditSink: ...
    @staticmethod
    def validate(path: str) -> int: ...
```

- [ ] **Step 9: Commit**

---

### Task 2: InMemoryTraceExporter 绑定

**Files:**
- Create: `src/infra/pytrace.rs`
- Modify: `src/infra/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_trace_exporter.py`

**Interfaces:**
- `InMemoryTraceExporter::new() -> Self`
- `.exported_spans() -> Vec<SpanEvent>`
- Implements `TraceExporter` trait
- `SpanEvent` has fields: `span_id`, `trace_id`, `parent_span_id`, `name`, `kind`, `start_time`, `end_time`, `attributes`, `status`
- Produces: `senza.InMemoryTraceExporter` class with `__init__()`, `exported_spans() -> list[dict]`, `exported_span_count() -> int`

- [ ] **Step 1: 写失败测试**

```python
import senza


def test_in_memory_trace_exporter_creates():
    exporter = senza.InMemoryTraceExporter()
    assert exporter is not None


def test_in_memory_trace_exporter_empty():
    exporter = senza.InMemoryTraceExporter()
    spans = exporter.exported_spans()
    assert isinstance(spans, list)
    assert len(spans) == 0
    assert exporter.exported_span_count() == 0
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pytrace.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;

/// In-memory trace exporter for testing.
/// Accumulates spans in memory for inspection.
#[pyclass(name = "InMemoryTraceExporter")]
pub struct PyInMemoryTraceExporter {
    pub exporter: Arc<llm_harness_runtime_trace_otel::InMemoryTraceExporter>,
}

#[pymethods]
impl PyInMemoryTraceExporter {
    #[new]
    fn new() -> Self {
        Self {
            exporter: Arc::new(llm_harness_runtime_trace_otel::InMemoryTraceExporter::new()),
        }
    }

    /// Return all exported spans as a list of dicts.
    fn exported_spans(&self, py: Python<'_>) -> PyResult<Vec<Py<PyAny>>> {
        let spans = self.exporter.exported_spans();
        // Convert each SpanEvent to a dict
        let mut result = Vec::with_capacity(spans.len());
        for span in spans {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("name", span.name.clone())?;
            dict.set_item("span_id", format!("{:?}", span.span_id))?;
            dict.set_item("trace_id", format!("{:?}", span.trace_id))?;
            dict.set_item("status", format!("{:?}", span.status))?;
            dict.set_item("kind", format!("{:?}", span.kind))?;
            result.push(dict.into_any().unbind());
        }
        Ok(result)
    }

    /// Return the number of exported spans.
    fn exported_span_count(&self) -> usize {
        self.exporter.exported_spans().len()
    }
}
```

Note: `SpanEvent` fields may not be directly accessible or may have complex types (UUID, HashMap). Convert to strings for Python consumption. Check actual `SpanEvent` struct.

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub:
```python
class InMemoryTraceExporter:
    def __new__() -> InMemoryTraceExporter: ...
    def exported_spans(self) -> list[dict]: ...
    def exported_span_count(self) -> int: ...
```

- [ ] **Step 9: Commit**

---

### Task 3: Sandbox 绑定（BwrapSandbox + SeatbeltSandbox）

**Files:**
- Create: `src/infra/pysandbox.rs`
- Modify: `src/infra/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_sandbox.py`

**Interfaces:**
- `SeatbeltSandbox::new(config: SandboxConfig) -> Self` (macOS)
- `BwrapSandbox::new(config: SandboxConfig) -> Result<Self>` (Linux; stub on macOS returns error)
- `Sandbox` trait: `start()`, `env()`, `reset()`, `shutdown()`, `config()`, `is_running()`
- `SandboxConfig { fs_allowlist, fs_denylist, net_allowlist, resource_limits, work_dir }`
- Produces: `senza.create_seatbelt_sandbox(config: dict | None = None) -> Sandbox` and `senza.create_bwrap_sandbox(config: dict | None = None) -> Sandbox`

**Design:** Both sandboxes are opaque `Sandbox` wrappers. Config dict maps to `SandboxConfig`. Platform-conditional: `create_seatbelt_sandbox` only registered on macOS, `create_bwrap_sandbox` only on Linux. On the wrong platform, the function is not registered (AttributeError).

- [ ] **Step 1: 写失败测试**

```python
import senza
import sys


def test_seatbelt_sandbox_creates():
    if sys.platform != "darwin":
        return  # Skip on non-macOS
    sandbox = senza.create_seatbelt_sandbox()
    assert sandbox is not None
    assert sandbox.is_running() == False


def test_seatbelt_sandbox_with_config():
    if sys.platform != "darwin":
        return
    sandbox = senza.create_seatbelt_sandbox({
        "fs_allowlist": ["/tmp"],
        "work_dir": "/tmp/sandbox",
    })
    assert sandbox is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pysandbox.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use llm_harness_runtime::platform::sandbox::{Sandbox, SandboxConfig, NetRule, ResourceLimits};

/// Opaque wrapper for a Sandbox.
#[pyclass(name = "Sandbox")]
pub struct PySandbox {
    // Sandbox::shutdown consumes self (Box<Self>), so we need to store
    // the sandbox as an Option to allow shutdown to take it.
    // Actually, Sandbox trait methods take &self except shutdown.
    // Store as Arc and don't expose shutdown (or use Mutex).
    // Simplest: store Arc<dyn Sandbox> — but shutdown takes Box<Self>.
    // For Python SDK, skip shutdown exposure (sandbox is dropped when Python object is dropped).
    // Use a trait object that doesn't need shutdown.
    // Actually let's just store the concrete type behind a Box.
    // Hmm, we have two different types (SeatbeltSandbox and BwrapSandbox).
    // Use Arc<dyn Sandbox> and skip shutdown.
    sandbox: Arc<dyn Sandbox>,
}

#[pymethods]
impl PySandbox {
    fn is_running(&self) -> bool {
        self.sandbox.is_running()
    }

    fn start<'py>(&self, py: Python<'py>) -> PyResult<()> {
        let sandbox = self.sandbox.clone();
        let rt = crate::core::pyagent::runtime(py);
        crate::shared::pyerror::detach_catch_panic_result(py, move || {
            rt.block_on(async move {
                sandbox.start().await
            })
        }).map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    }
}

fn dict_to_sandbox_config(config: Option<&Bound<'_, PyDict>>) -> SandboxConfig {
    // Parse dict into SandboxConfig
    ...
}

#[cfg(target_os = "macos")]
#[pyfunction]
#[pyo3(signature = (config=None))]
pub fn create_seatbelt_sandbox<'py>(
    py: Python<'py>,
    config: Option<&Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PySandbox>> {
    let cfg = dict_to_sandbox_config(config);
    let sandbox: Arc<dyn Sandbox> = Arc::new(
        llm_harness_runtime_sandbox_seatbelt::SeatbeltSandbox::new(cfg)
    );
    Py::new(py, PySandbox { sandbox }).map(|p| p.into_bound(py))
}

#[cfg(target_os = "linux")]
#[pyfunction]
#[pyo3(signature = (config=None))]
pub fn create_bwrap_sandbox<'py>(
    py: Python<'py>,
    config: Option<&Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PySandbox>> {
    let cfg = dict_to_sandbox_config(config);
    let sandbox = llm_harness_runtime_sandbox_bwrap::BwrapSandbox::new(cfg)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let sandbox: Arc<dyn Sandbox> = Arc::new(sandbox);
    Py::new(py, PySandbox { sandbox }).map(|p| p.into_bound(py))
}
```

Note: `Arc<dyn Sandbox>` won't work because `shutdown` takes `Box<Self>`. But we don't expose shutdown. The issue is `Sandbox` trait is not object-safe if `shutdown` takes `self: Box<Self>`. Check if `Arc<dyn Sandbox>` compiles. If not, use a concrete enum or store `Box<dyn Sandbox>` behind `Mutex`.

Actually `Sandbox: Send + Sync` and `shutdown(self: Box<Self>)` — this IS object-safe because `Box<Self>` is a valid receiver. But `Arc<dyn Sandbox>` won't give us `Box<dyn Sandbox>`. We might need to store `Box<dyn Sandbox>` and not expose shutdown, OR store as a concrete type.

Simplest approach: store `Arc<dyn Sandbox>` and don't call `shutdown` (sandbox is dropped naturally). The trait is object-safe (shutdown is just not callable through Arc). Check if this compiles.

- [ ] **Step 4-8: 更新 mod.rs、lib.rs（条件注册）、stub、验证**

stub:
```python
class Sandbox:
    def is_running(self) -> bool: ...
    def start(self) -> None: ...

# create_seatbelt_sandbox only on macOS
# create_bwrap_sandbox only on Linux
def create_seatbelt_sandbox(config: Optional[dict] = None) -> Sandbox: ...
def create_bwrap_sandbox(config: Optional[dict] = None) -> Sandbox: ...
```

- [ ] **Step 9: Commit**

---

### Task 4-13: Examples (10 sub-tasks, batch as 2-3 parallel agents)

Create 20 example files. Group by directory:

**strategy/ (12 files):**
- `strategy/01_safety_defaults.py` — SafetyDefaultsPlugin
- `strategy/02_loop_safety.py` — LoopSafetyPlugin
- `strategy/03_status_panel.py` — StatusPanelPlugin
- `strategy/04_memory_defense.py` — MemoryDefensePlugin
- `strategy/05_injection_filter.py` — InjectionFilterPlugin
- `strategy/06_source_tag.py` — SourceTagPlugin
- `strategy/07_project_instruction.py` — ProjectInstructionPlugin
- `strategy/08_audit.py` — AuditPlugin
- `strategy/09_notify.py` — NotifyPlugin
- `strategy/10_tool_output_guard.py` — ToolOutputGuardPlugin
- `strategy/11_event_streams.py` — WebhookStream
- `strategy/12_context_aware_compact.py` — context_aware_prompt_spec

**knowledge/ (3 files):**
- `knowledge/01_local_rag.py` — LocalDocumentSource + KnowledgePlugin
- `knowledge/02_memory_service.py` — MemoryPlugin
- `knowledge/03_session_recall.py` — HistoryRecallPlugin

**infra/ (3 files):**
- `infra/01_audit_jsonl.py` — JsonlAuditSink validate
- `infra/02_tracing.py` — InMemoryTraceExporter
- `infra/03_sandbox.py` — SeatbeltSandbox (macOS) / BwrapSandbox (Linux)

Each example follows the pattern: imports, setup (provider + env), demo of the feature, print result. No real API calls needed — just demonstrate the API surface (create plugin, install on builder, build harness). Use `sk-test` as API key.

- [ ] Each example gets its own file. Commit as batches.

---

### Task 14: SENZA_DESIGN.md 更新

Update the gap table (all marked complete), repo structure, crate dependencies.

- [ ] **Commit**

---

### Task 15: 最终验证

- [ ] **Step 1: cargo build**
- [ ] **Step 2: pytest**
- [ ] **Step 3: check_stubs.py**
- [ ] **Step 4: Each example can be imported** (`python -c "import senza; ..."` for each example, or at minimum `python -m py_compile examples/...`)
