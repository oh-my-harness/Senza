# Senza 全量对齐 — 阶段 3：Knowledge + Memory + SessionRecall 绑定 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 llm-harness-runtime-knowledge / knowledge-local / memory / session-recall 四个 crate 的核心能力暴露为 Python 绑定，覆盖本地知识源 RAG、记忆服务读写、跨会话历史召回。

**Architecture:** 三个子系统有依赖链：memory 依赖 knowledge 的 `KnowledgeSource` trait；session-recall 依赖 knowledge 的 registry/citation 体系。绑定按依赖顺序实现：knowledge → memory → session-recall。

**Tech Stack:** Rust + PyO3 0.29 + llm-harness-runtime-knowledge/knowledge-local/memory/session-recall

## Global Constraints

- Runtime pin: `5eae99ed1c42dd558529bede9957518ba15eef5c` (已升级)
- PyO3 版本: 0.29
- 构建命令: `PYO3_PYTHON="$(pwd)/.venv/bin/python" cargo build`
- 测试命令: `PYO3_PYTHON="$(pwd)/.venv/bin/python" cargo test` + `.venv/bin/python -m pytest tests/ -v`
- stub 检查: `.venv/bin/python scripts/check_stubs.py` 必须零偏差
- Plugin 包装模式: `PyPluginWrapper::new(Arc::new(plugin))` → `Py::new(py, wrapper)`
- `src/knowledge/mod.rs` 已存在（阶段 1 占位），需更新内容
- 需要 `Arc<dyn ExecutionEnv>` 的 plugin 用 `PyEnvWrapper.env` 字段
- **session-recall sqlite feature 需在 Cargo.toml 启用**

## Spec 偏差（经调查确认）

1. **无 SQLite memory store** — runtime memory crate 没有 `SqliteMemoryStore`。改为提供 `create_in_memory_store()`（基于 live-tests 中的 InMemoryStore 模式）。spec 中的 `create_sqlite_memory_store(path)` 改为 `create_in_memory_store()`。
2. **EvidenceAuthority 需要 secret** — `EvidenceAuthority::new(secret: Vec<u8>, providers)` 需要 ≥32 字节密钥。Python 侧通过参数传入或自动生成。
3. **LocalDocumentSource::create() 是 async** — 需要在 tokio runtime 上执行。
4. **ObservedSessionRepo** 在 `llm_harness_agent` crate 中，不是 session-recall crate。

## File Structure

```
src/knowledge/
├── mod.rs                  # re-exports all submodules
├── pyknowledge.rs          # KnowledgeRegistry builder + KnowledgePlugin + EvidenceAuthority
├── pylocalsource.rs        # LocalDocumentSource + config
├── pymemory.rs             # MemoryService + MemoryPlugin + InMemoryStore + SecureMemoryWritePolicy
└── pysessionrecall.rs      # SessionRecallIndex + Projector + KnowledgeSource + HistoryRecallPlugin
```

---

### Task 1: 启用 session-recall sqlite feature

**Files:**
- Modify: `Cargo.toml`

- [ ] **Step 1: 修改 Cargo.toml**

将 session-recall 依赖行改为:
```toml
llm-harness-runtime-session-recall = { git = "https://github.com/oh-my-harness/llm-harness-runtime", rev = "5eae99ed1c42dd558529bede9957518ba15eef5c", features = ["sqlite"] }
```

- [ ] **Step 2: 验证编译**

Run: `PYO3_PYTHON="$(pwd)/.venv/bin/python" cargo build`
Expected: 编译通过（rusqlite 被引入）

- [ ] **Step 3: Commit**

```bash
git add Cargo.toml
git commit -m "feat(knowledge): enable sqlite feature for session-recall"
```

---

### Task 2: LocalDocumentSource 绑定

**Files:**
- Create: `src/knowledge/pylocalsource.rs`
- Modify: `src/knowledge/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_local_knowledge_source.py`

**Interfaces:**
- Consumes: `LocalDocumentSource::create(config, file_system, parsers, access_control)` — async, returns `Result<Self, LocalDocumentSourceError>`
- `LocalDocumentSourceConfig { source_id, name, description, domains, roots: Vec<DocumentRootConfig>, source_secret: Vec<u8>, max_document_bytes }`
- `DocumentRootConfig { id, path: PathBuf }`
- `OsDocumentFileSystem` — default impl
- `DocumentParserRegistry::default()` — registers Markdown + Text parsers
- `KnowledgeAccessControl::default()` — uses `DenyAllAuthorizer`; for Python bindings use `AllowAllAuthorizer` via `KnowledgeAccessControl::new(Arc::new(AllowAllAuthorizer))`
- Produces: `senza.create_local_knowledge_source(path, source_id, name?, description?, domains?, max_document_bytes?) -> LocalKnowledgeSource` (opaque wrapper)

**Design:** Python 侧传入文档根路径 + source_id，Rust 侧自动创建 config + file system + parser registry + access control。source_secret 自动生成 32 字节随机。`LocalKnowledgeSource` 是 opaque wrapper holding `Arc<dyn KnowledgeSource>`，因为 `LocalDocumentSource` 需要后续被注册到 `KnowledgeRegistry`。

- [ ] **Step 1: 写失败测试**

```python
import senza
import tempfile
import os


def test_local_knowledge_source_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test markdown file
        with open(os.path.join(tmpdir, "test.md"), "w") as f:
            f.write("# Test\nThis is a test document.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="test-docs",
            name="Test Documents",
        )
        assert source is not None


def test_local_knowledge_source_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "doc1.md"), "w") as f:
            f.write("# Doc 1\nContent here.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="my-docs",
            name="My Docs",
            description="A collection of documents",
            domains=["general"],
            max_document_bytes=1048576,
        )
        assert source is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pylocalsource.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// Opaque wrapper for a knowledge source.
#[pyclass(name = "KnowledgeSource")]
pub struct PyKnowledgeSource {
    pub source: Arc<dyn llm_harness_runtime_knowledge::KnowledgeSource>,
}

/// Create a local document knowledge source that indexes Markdown and text
/// files from a directory.
///
/// Args:
///     path: Root directory containing documents.
///     source_id: Unique identifier for this knowledge source.
///     name: Display name (defaults to source_id).
///     description: Description (defaults to empty string).
///     domains: List of domain tags (defaults to ["general"]).
///     max_document_bytes: Max file size in bytes (default 1MB).
#[pyfunction]
#[pyo3(signature = (path, source_id, name=None, description=None, domains=None, max_document_bytes=1048576))]
pub fn create_local_knowledge_source<'py>(
    py: Python<'py>,
    path: &str,
    source_id: &str,
    name: Option<String>,
    description: Option<String>,
    domains: Option<Vec<String>>,
    max_document_bytes: usize,
) -> PyResult<Bound<'py, PyKnowledgeSource>> {
    let rt = crate::core::pyagent::runtime(py);
    let config = llm_harness_runtime_knowledge_local::LocalDocumentSourceConfig {
        source_id: source_id.to_string(),
        name: name.unwrap_or_else(|| source_id.to_string()),
        description: description.unwrap_or_default(),
        domains: domains.unwrap_or_else(|| vec!["general".to_string()]),
        roots: vec![llm_harness_runtime_knowledge_local::DocumentRootConfig {
            id: "root".to_string(),
            path: std::path::PathBuf::from(path),
        }],
        source_secret: (0..32).map(|i| i as u8).collect(), // Simple deterministic secret
        max_document_bytes,
    };
    let file_system = Arc::new(llm_harness_runtime_knowledge_local::OsDocumentFileSystem);
    let parsers = llm_harness_runtime_knowledge_local::DocumentParserRegistry::default();
    let access_control = llm_harness_runtime_knowledge::KnowledgeAccessControl::new(
        Arc::new(llm_harness_runtime_knowledge::AllowAllAuthorizer),
    );

    let source = py.detach(|| {
        rt.block_on(async move {
            llm_harness_runtime_knowledge_local::LocalDocumentSource::create(
                config, file_system, parsers, access_control,
            )
            .await
        })
    }).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok(Py::new(py, PyKnowledgeSource { source: Arc::new(source) })?.into_bound(py))
}
```

注意：`source_secret` 使用简单确定性值而非随机，因为 Python 侧不需要密码学安全性（用户可通过其他方式覆盖）。如果 `KnowledgeAccessControl::new` 不存在，检查是否用 `KnowledgeAccessControl::default()` 或 `KnowledgeAccessControl::with_authorizer()`。检查实际 API。`py.detach` 应使用 `detach_catch_panic` 模式。

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub:
```python
class KnowledgeSource:
    pass  # opaque

def create_local_knowledge_source(
    path: str,
    source_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    domains: Optional[list[str]] = None,
    max_document_bytes: int = 1048576,
) -> KnowledgeSource: ...
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(knowledge): expose LocalDocumentSource"
```

---

### Task 3: KnowledgeRegistry + KnowledgePlugin 绑定

**Files:**
- Create: `src/knowledge/pyknowledge.rs`
- Modify: `src/knowledge/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_knowledge_plugin.py`

**Interfaces:**
- `KnowledgeRegistryBuilder::new()` → `.source(Arc<dyn KnowledgeSource>)` → `.build() -> Result<KnowledgeRegistry, KnowledgeRegistryBuildError>`
- `EvidenceAuthority::new(secret: Vec<u8>, providers: impl IntoIterator<Item = EvidenceProviderId>) -> Result<Self, &'static str>`
- `EvidenceProviderId(pub String)`
- `KnowledgePlugin::new(registry: Arc<KnowledgeRegistry>, authority: Arc<EvidenceAuthority>, provider_id: EvidenceProviderId, config: KnowledgePluginConfig) -> Result<Self, KnowledgePluginBuildError>`
- `KnowledgePluginConfig { tools: KnowledgeToolConfig, citation_policy: KnowledgeCitationPolicy }` — both have `Default`
- Produces: `senza.create_knowledge_plugin(sources: list[KnowledgeSource], config: dict | None = None) -> Plugin`

**Design:** 一个高阶工厂函数封装完整构建链：收集 sources → build registry → create EvidenceAuthority → create KnowledgePlugin。Python 用户只需传入 `KnowledgeSource` 列表和可选 config dict。secret 自动生成。provider_id 自动生成为 `"local"`.

- [ ] **Step 1: 写失败测试**

```python
import senza
import tempfile
import os


def test_knowledge_plugin_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "test.md"), "w") as f:
            f.write("# Test\nContent here.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="test-docs",
        )
        plugin = senza.create_knowledge_plugin(sources=[source])
        assert plugin is not None


def test_knowledge_plugin_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "doc.md"), "w") as f:
            f.write("# Doc\nContent.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="docs",
        )
        plugin = senza.create_knowledge_plugin(
            sources=[source],
            config={"max_search_results": 10, "max_read_bytes": 50000},
        )
        assert plugin is not None


def test_knowledge_plugin_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "doc.md"), "w") as f:
            f.write("# Doc\nContent.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="docs",
        )
        plugin = senza.create_knowledge_plugin(sources=[source])
        provider = senza.create_openai_provider(api_key="sk-test")
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("*", provider)
            .plugin(plugin)
            .build()
        )
        assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pyknowledge.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use crate::core::pyplugin::PyPluginWrapper;
use super::pylocalsource::PyKnowledgeSource;

/// Create a KnowledgePlugin that registers knowledge_search and knowledge_read
/// tools, enabling the LLM to search and read from registered knowledge sources.
///
/// Args:
///     sources: List of KnowledgeSource objects (from create_local_knowledge_source).
///     config: Optional dict with "max_search_results" (int, default 20),
///             "max_read_bytes" (int, default 100000).
#[pyfunction]
#[pyo3(signature = (sources, config=None))]
pub fn create_knowledge_plugin<'py>(
    py: Python<'py>,
    sources: Vec<Bound<'py, PyKnowledgeSource>>,
    config: Option<&Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    // Extract Arc<dyn KnowledgeSource> from each PyKnowledgeSource
    let mut builder = llm_harness_runtime_knowledge::KnowledgeRegistryBuilder::new();
    for src in &sources {
        let borrowed: PyRef<'_, PyKnowledgeSource> = src.extract()?;
        builder = builder.source(borrowed.source.clone());
    }

    // Build tool config
    let mut tools = llm_harness_runtime_knowledge::KnowledgeToolConfig::default();
    if let Some(cfg) = config {
        if let Some(v) = cfg.get_item("max_search_results")?.and_then(|v| v.extract::<usize>().ok()) {
            tools.max_search_results = v;
        }
        if let Some(v) = cfg.get_item("max_read_bytes")?.and_then(|v| v.extract::<usize>().ok()) {
            tools.max_read_bytes = v;
        }
    }

    // Build registry
    let registry = Arc::new(builder.build()
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?);

    // Create EvidenceAuthority with a deterministic secret
    let secret: Vec<u8> = (0..32).map(|i| i as u8).collect();
    let provider_id = llm_harness_runtime_knowledge::EvidenceProviderId("local".to_string());
    let authority = Arc::new(
        llm_harness_runtime_knowledge::EvidenceAuthority::new(secret, [provider_id.clone()])
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?,
    );

    let plugin_config = llm_harness_runtime_knowledge::KnowledgePluginConfig::default();

    let plugin = llm_harness_runtime_knowledge::KnowledgePlugin::new(
        registry, authority, provider_id, plugin_config,
    ).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let plugin: Arc<dyn llm_harness_agent::Plugin> = Arc::new(plugin);
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub:
```python
def create_knowledge_plugin(
    sources: list[KnowledgeSource],
    config: Optional[dict] = None,
) -> Plugin: ...
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(knowledge): expose KnowledgePlugin + registry builder"
```

---

### Task 4: InMemoryStore + SecureMemoryWritePolicy 绑定

**Files:**
- Create: `src/knowledge/pymemory.rs` (InMemoryStore + SecureMemoryWritePolicy parts)
- Modify: `src/knowledge/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_memory_store.py`

**Interfaces:**
- `MemoryStore` trait — need our own `InMemoryStore` impl (runtime doesn't provide one)
- `SecureMemoryWritePolicy::new(secret: Vec<u8>, config: SecureMemoryWritePolicyConfig) -> Result<Self, SecureMemoryWritePolicyBuildError>`
- `SecureMemoryWritePolicyConfig { max_content_bytes, allowed_kinds, default_ttl, max_ttl, metadata }`
- `MemoryMutationGate` trait — need `AllowAllGate` impl (from live-tests pattern)
- Produces: `senza.create_in_memory_store(read_source_id: str) -> MemoryStore` (opaque)
  `senza.create_secure_write_policy(config: dict | None = None) -> MemoryWritePolicy` (opaque)

**Design:** `InMemoryStore` is a simple `Mutex<Vec<(KnowledgeRef, Vec<u8>)>>` backed store. `AllowAllGate` always approves. These are Senza-side implementations since runtime doesn't provide them.

- [ ] **Step 1: 写失败测试**

```python
import senza


def test_in_memory_store_creates():
    store = senza.create_in_memory_store("test-source")
    assert store is not None


def test_secure_write_policy_creates():
    policy = senza.create_secure_write_policy()
    assert policy is not None


def test_secure_write_policy_with_config():
    policy = senza.create_secure_write_policy(
        {"max_content_bytes": 8192, "max_ttl_seconds": 3600}
    )
    assert policy is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pymemory.rs (store + policy + gate)**

Implement `InMemoryStore`, `AllowAllGate`, and the factory functions. Key types:

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::Mutex;
use futures::future::BoxFuture;
use llm_harness_runtime_knowledge::{KnowledgeError, KnowledgeRef, KnowledgeRequestContext};
use llm_harness_runtime_memory::{
    MemoryConsistency, MemoryDeleteReceipt, MemoryStore, MemoryStoreDescriptor,
    MemoryVisibility, MemoryWrite, MemoryWriteReceipt, MemoryWritePolicy,
    MemoryMutationGate, MemoryMutationRequest, MemoryMutationGateError,
    SecureMemoryWritePolicy, SecureMemoryWritePolicyConfig,
};

// ── InMemoryStore ──────────────────────────────────────────────────────

pub struct InMemoryStore {
    descriptor: MemoryStoreDescriptor,
    entries: Mutex<Vec<(KnowledgeRef, Vec<u8>)>>,
}

impl InMemoryStore {
    pub fn new(read_source_id: String) -> Self {
        Self {
            descriptor: MemoryStoreDescriptor {
                read_source_id,
                consistency: MemoryConsistency::Immediate,
            },
            entries: Mutex::new(Vec::new()),
        }
    }
}

// ... impl MemoryStore for InMemoryStore (follow live-tests pattern)

// ── AllowAllGate ───────────────────────────────────────────────────────

pub struct AllowAllGate;
impl MemoryMutationGate for AllowAllGate { ... }

// ── Opaque wrappers ────────────────────────────────────────────────────

#[pyclass(name = "MemoryStore")]
pub struct PyMemoryStore {
    pub store: Arc<dyn MemoryStore>,
}

#[pyclass(name = "MemoryWritePolicy")]
pub struct PyMemoryWritePolicy {
    pub policy: Arc<dyn MemoryWritePolicy>,
}

#[pyclass(name = "MemoryMutationGate")]
pub struct PyMemoryMutationGate {
    pub gate: Arc<dyn MemoryMutationGate>,
}

// ── Factory functions ──────────────────────────────────────────────────

#[pyfunction]
pub fn create_in_memory_store<'py>(...) -> ... { ... }

#[pyfunction]
pub fn create_secure_write_policy<'py>(...) -> ... { ... }
```

注意：`Mutex` 用 `std::sync::Mutex` 因为 `MemoryStore::upsert` 返回 `BoxFuture`，需要 `Send`。实际上需要 `tokio::sync::Mutex` 因为 future 里 lock。检查 live-tests 用的是 `std::sync::Mutex`（因为 `.lock().unwrap()` 是同步的，在 async block 里直接调用）。确认哪种可以编译。

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub:
```python
class MemoryStore:
    pass  # opaque

class MemoryWritePolicy:
    pass  # opaque

class MemoryMutationGate:
    pass  # opaque

def create_in_memory_store(read_source_id: str) -> MemoryStore: ...

def create_secure_write_policy(config: Optional[dict] = None) -> MemoryWritePolicy: ...
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(knowledge): expose InMemoryStore + SecureMemoryWritePolicy"
```

---

### Task 5: MemoryService + MemoryPlugin 绑定

**Files:**
- Modify: `src/knowledge/pymemory.rs` (add MemoryService + MemoryPlugin)
- Modify: `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_memory_plugin.py`

**Interfaces:**
- `MemoryService::new(access_control, read_source, write_store, write_policy, mutation_gate) -> Result<Self, MemoryServiceBuildError>`
- `MemoryPlugin::new(service: Arc<MemoryService>) -> Self`
- Produces: `senza.create_memory_plugin(source: KnowledgeSource, store: MemoryStore, policy: MemoryWritePolicy, gate: MemoryMutationGate | None = None) -> Plugin`

**Design:** MemoryService needs `read_source: Arc<dyn KnowledgeSource>` (the same KnowledgeSource from Task 2) and `write_store: Arc<dyn MemoryStore>` (from Task 4). The `access_control` is created internally with `AllowAllAuthorizer`. The `mutation_gate` defaults to `AllowAllGate` if not provided.

Important: `MemoryService` requires `read_source.descriptor().id == write_store.descriptor().read_source_id`. The Python user must ensure the source_id passed to `create_in_memory_store()` matches the `source_id` of the `KnowledgeSource`.

- [ ] **Step 1: 写失败测试**

```python
import senza
import tempfile
import os


def test_memory_plugin_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "mem.md"), "w") as f:
            f.write("# Memory\nInitial content.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="memory-store",
        )
        store = senza.create_in_memory_store("memory-store")
        policy = senza.create_secure_write_policy()
        plugin = senza.create_memory_plugin(
            source=source,
            store=store,
            policy=policy,
        )
        assert plugin is not None


def test_memory_plugin_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "mem.md"), "w") as f:
            f.write("# Memory\nContent.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="mem",
        )
        store = senza.create_in_memory_store("mem")
        policy = senza.create_secure_write_policy()
        plugin = senza.create_memory_plugin(source=source, store=store, policy=policy)
        provider = senza.create_openai_provider(api_key="sk-test")
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("*", provider)
            .plugin(plugin)
            .build()
        )
        assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 create_memory_plugin**

```rust
#[pyfunction]
#[pyo3(signature = (source, store, policy, gate=None))]
pub fn create_memory_plugin<'py>(
    py: Python<'py>,
    source: &Bound<'_, PyKnowledgeSource>,
    store: &Bound<'_, PyMemoryStore>,
    policy: &Bound<'_, PyMemoryWritePolicy>,
    gate: Option<&Bound<'_, PyMemoryMutationGate>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let src: PyRef<'_, PyKnowledgeSource> = source.extract()?;
    let store: PyRef<'_, PyMemoryStore> = store.extract()?;
    let policy: PyRef<'_, PyMemoryWritePolicy> = policy.extract()?;
    let gate: Arc<dyn MemoryMutationGate> = if let Some(g) = gate {
        let g: PyRef<'_, PyMemoryMutationGate> = g.extract()?;
        g.gate.clone()
    } else {
        Arc::new(AllowAllGate)
    };

    let access_control = llm_harness_runtime_knowledge::KnowledgeAccessControl::new(
        Arc::new(llm_harness_runtime_knowledge::AllowAllAuthorizer),
    );

    let service = llm_harness_runtime_memory::MemoryService::new(
        access_control,
        src.source.clone(),
        store.store.clone(),
        policy.policy.clone(),
        gate,
    ).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_runtime_memory::MemoryPlugin::new(Arc::new(service)));
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

- [ ] **Step 4-8: 更新 lib.rs、stub、验证**

stub: `def create_memory_plugin(source: KnowledgeSource, store: MemoryStore, policy: MemoryWritePolicy, gate: Optional[MemoryMutationGate] = None) -> Plugin: ...`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(knowledge): expose MemoryPlugin + MemoryService"
```

---

### Task 6: SessionRecallIndex + Projector 绑定

**Files:**
- Create: `src/knowledge/pysessionrecall.rs`
- Modify: `src/knowledge/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_session_recall_index.py`

**Interfaces:**
- `InMemorySessionRecallIndex::default()` / `SqliteSessionRecallIndex::open(path) -> Result<Self, SessionRecallError>`
- `SessionRecallProjector::new(repo: Arc<dyn SessionRepo>, index: Arc<dyn SessionRecallIndex>) -> Self`
- `SessionRecallService::new(repo, index, access_control) -> Self`
- `SessionRecallKnowledgeSource::new(service: Arc<SessionRecallService>) -> Self`
- Produces: `senza.create_in_memory_session_recall_index() -> SessionRecallIndex`
  `senza.create_sqlite_session_recall_index(path: str) -> SessionRecallIndex`
  `senza.create_session_recall_knowledge_source(repo: SessionRepo, index: SessionRecallIndex) -> KnowledgeSource`

**Design:** `SessionRecallIndex` is opaque wrapper holding `Arc<dyn SessionRecallIndex>`. `SessionRepo` is opaque wrapper holding `Arc<dyn SessionRepo>`. The user creates index + repo, then creates knowledge source from them. The knowledge source is registered into `KnowledgeRegistry` via `create_knowledge_plugin`.

Need to expose `InMemorySessionRepo` and `JsonlSessionRepo` from `llm_harness_agent` as well, since `SessionRecallProjector` needs `Arc<dyn SessionRepo>`.

- [ ] **Step 1: 写失败测试**

```python
import senza
import tempfile


def test_in_memory_session_recall_index_creates():
    index = senza.create_in_memory_session_recall_index()
    assert index is not None


def test_sqlite_session_recall_index_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        index = senza.create_sqlite_session_recall_index(
            path=tmpdir + "/recall.db"
        )
        assert index is not None


def test_session_recall_knowledge_source_creates():
    index = senza.create_in_memory_session_recall_index()
    repo = senza.create_in_memory_session_repo()
    source = senza.create_session_recall_knowledge_source(repo=repo, index=index)
    assert source is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pysessionrecall.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;

/// Opaque wrapper for SessionRecallIndex.
#[pyclass(name = "SessionRecallIndex")]
pub struct PySessionRecallIndex {
    pub index: Arc<dyn llm_harness_runtime_session_recall::SessionRecallIndex>,
}

/// Opaque wrapper for SessionRepo.
#[pyclass(name = "SessionRepo")]
pub struct PySessionRepo {
    pub repo: Arc<dyn llm_harness_agent::SessionRepo>,
}

/// Create an in-memory session recall index (non-persistent).
#[pyfunction]
pub fn create_in_memory_session_recall_index<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, PySessionRecallIndex>> {
    let index: Arc<dyn llm_harness_runtime_session_recall::SessionRecallIndex> =
        Arc::new(llm_harness_runtime_session_recall::InMemorySessionRecallIndex::default());
    Py::new(py, PySessionRecallIndex { index }).map(|p| p.into_bound(py))
}

/// Create a SQLite-backed persistent session recall index.
#[pyfunction]
pub fn create_sqlite_session_recall_index<'py>(
    py: Python<'py>,
    path: &str,
) -> PyResult<Bound<'py, PySessionRecallIndex>> {
    let index = llm_harness_runtime_session_recall::SqliteSessionRecallIndex::open(path)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let index: Arc<dyn llm_harness_runtime_session_recall::SessionRecallIndex> = Arc::new(index);
    Py::new(py, PySessionRecallIndex { index }).map(|p| p.into_bound(py))
}

/// Create an in-memory session repo (non-persistent).
#[pyfunction]
pub fn create_in_memory_session_repo<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, PySessionRepo>> {
    let repo: Arc<dyn llm_harness_agent::SessionRepo> =
        Arc::new(llm_harness_agent::InMemorySessionRepo::new());
    Py::new(py, PySessionRepo { repo }).map(|p| p.into_bound(py))
}

/// Create a SessionRecallKnowledgeSource from a session repo and recall index.
#[pyfunction]
pub fn create_session_recall_knowledge_source<'py>(
    py: Python<'py>,
    repo: &Bound<'_, PySessionRepo>,
    index: &Bound<'_, PySessionRecallIndex>,
) -> PyResult<Bound<'py, super::pylocalsource::PyKnowledgeSource>> {
    let repo: PyRef<'_, PySessionRepo> = repo.extract()?;
    let index: PyRef<'_, PySessionRecallIndex> = index.extract()?;

    let access_control = llm_harness_runtime_knowledge::KnowledgeAccessControl::new(
        Arc::new(llm_harness_runtime_knowledge::AllowAllAuthorizer),
    );

    let service = Arc::new(
        llm_harness_runtime_session_recall::SessionRecallService::new(
            repo.repo.clone(),
            index.index.clone(),
            access_control,
        ),
    );
    let source = llm_harness_runtime_session_recall::SessionRecallKnowledgeSource::new(service);
    let source: Arc<dyn llm_harness_runtime_knowledge::KnowledgeSource> = Arc::new(source);
    Py::new(py, super::pylocalsource::PyKnowledgeSource { source }).map(|p| p.into_bound(py))
}
```

- [ ] **Step 4-8: 更新 mod.rs、lib.rs（注册 2 个 class + 4 个 function）、stub、验证**

stub:
```python
class SessionRecallIndex:
    pass  # opaque

class SessionRepo:
    pass  # opaque

def create_in_memory_session_recall_index() -> SessionRecallIndex: ...
def create_sqlite_session_recall_index(path: str) -> SessionRecallIndex: ...
def create_in_memory_session_repo() -> SessionRepo: ...
def create_session_recall_knowledge_source(repo: SessionRepo, index: SessionRecallIndex) -> KnowledgeSource: ...
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(knowledge): expose SessionRecallIndex + KnowledgeSource"
```

---

### Task 7: HistoryRecallPlugin 绑定

**Files:**
- Modify: `src/knowledge/pysessionrecall.rs` (add HistoryRecallPlugin)
- Modify: `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_history_recall_plugin.py`

**Interfaces:**
- `HistoryRecallPlugin::new(source: Arc<SessionRecallKnowledgeSource>, config: HistoryRecallPluginConfig) -> Result<Self, HistoryRecallPluginBuildError>`
- `HistoryRecallPluginConfig { budget: SessionRecallBudget, failure_mode: HistoryRecallFailureMode, timeout: Duration, include_reference_labels: bool }`
- `SessionRecallBudget { max_hits, max_bytes_per_hit, max_total_bytes, max_tokens_per_hit, max_total_tokens }`
- Produces: `senza.create_history_recall_plugin(source: KnowledgeSource, config: dict | None = None) -> Plugin`

**Design:** The `source` must be a `SessionRecallKnowledgeSource` (created in Task 6). But since it's wrapped in `PyKnowledgeSource` (opaque `Arc<dyn KnowledgeSource>`), we need to either:
- (a) Keep a separate `PySessionRecallKnowledgeSource` wrapper holding `Arc<SessionRecallKnowledgeSource>`, OR
- (b) Downcast `Arc<dyn KnowledgeSource>` to `SessionRecallKnowledgeSource` (not possible without `Any`).

Use approach (a): `create_session_recall_knowledge_source` returns `PySessionRecallKnowledgeSource` (which also implements `KnowledgeSource` for registry registration). The `create_history_recall_plugin` takes `PySessionRecallKnowledgeSource`.

Actually, `KnowledgeRegistryBuilder::source()` needs `Arc<dyn KnowledgeSource>`. So `PySessionRecallKnowledgeSource` should also be convertible to `Arc<dyn KnowledgeSource>`. Make `PyKnowledgeSource` hold an `Arc<dyn KnowledgeSource>` and have `create_session_recall_knowledge_source` return both a `PySessionRecallKnowledgeSource` and a way to get `Arc<dyn KnowledgeSource>`.

Simplest approach: `create_session_recall_knowledge_source` returns a `PySessionRecallKnowledgeSource` which has a `.as_knowledge_source()` method returning `KnowledgeSource`. Or better: return a tuple `(KnowledgeSource, SessionRecallKnowledgeSource)`. Or: `PySessionRecallKnowledgeSource` wraps `Arc<SessionRecallKnowledgeSource>` and has a method `.as_knowledge_source() -> KnowledgeSource`.

Cleanest: return a `PySessionRecallKnowledgeSource` that has both `source: Arc<SessionRecallKnowledgeSource>` (for plugin) and implements conversion to `Arc<dyn KnowledgeSource>` (for registry). Expose a method `as_knowledge_source()` that returns `PyKnowledgeSource`.

- [ ] **Step 1: 写失败测试**

```python
import senza


def test_history_recall_plugin_creates():
    index = senza.create_in_memory_session_recall_index()
    repo = senza.create_in_memory_session_repo()
    recall_source = senza.create_session_recall_knowledge_source(repo=repo, index=index)
    plugin = senza.create_history_recall_plugin(source=recall_source)
    assert plugin is not None


def test_history_recall_plugin_with_config():
    index = senza.create_in_memory_session_recall_index()
    repo = senza.create_in_memory_session_repo()
    recall_source = senza.create_session_recall_knowledge_source(repo=repo, index=index)
    plugin = senza.create_history_recall_plugin(
        source=recall_source,
        config={"max_hits": 5, "timeout_ms": 1000},
    )
    assert plugin is not None


def test_history_recall_plugin_in_builder():
    index = senza.create_in_memory_session_recall_index()
    repo = senza.create_in_memory_session_repo()
    recall_source = senza.create_session_recall_knowledge_source(repo=repo, index=index)
    plugin = senza.create_history_recall_plugin(source=recall_source)
    provider = senza.create_openai_provider(api_key="sk-test")
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 HistoryRecallPlugin 绑定**

Modify `create_session_recall_knowledge_source` to return `PySessionRecallKnowledgeSource`:

```rust
/// Opaque wrapper for SessionRecallKnowledgeSource.
/// Use .as_knowledge_source() to get a KnowledgeSource for registry registration.
#[pyclass(name = "SessionRecallKnowledgeSource")]
pub struct PySessionRecallKnowledgeSource {
    pub source: Arc<llm_harness_runtime_session_recall::SessionRecallKnowledgeSource>,
}

#[pymethods]
impl PySessionRecallKnowledgeSource {
    /// Convert to a KnowledgeSource for registration in KnowledgeRegistry.
    fn as_knowledge_source<'py>(
        &self,
        py: Python<'py>,
    ) -> Bound<'py, super::pylocalsource::PyKnowledgeSource> {
        let source: Arc<dyn llm_harness_runtime_knowledge::KnowledgeSource> = self.source.clone();
        Py::new(py, super::pylocalsource::PyKnowledgeSource { source })
            .unwrap()
            .into_bound(py)
    }
}
```

Then `create_history_recall_plugin`:

```rust
#[pyfunction]
#[pyo3(signature = (source, config=None))]
pub fn create_history_recall_plugin<'py>(
    py: Python<'py>,
    source: &Bound<'_, PySessionRecallKnowledgeSource>,
    config: Option<&Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let src: PyRef<'_, PySessionRecallKnowledgeSource> = source.extract()?;

    let mut plugin_config = llm_harness_runtime_session_recall::HistoryRecallPluginConfig::default();
    if let Some(cfg) = config {
        let mut budget = llm_harness_runtime_session_recall::SessionRecallBudget::default();
        if let Some(v) = cfg.get_item("max_hits")?.and_then(|v| v.extract::<usize>().ok()) {
            budget.max_hits = v;
        }
        if let Some(v) = cfg.get_item("max_bytes_per_hit")?.and_then(|v| v.extract::<usize>().ok()) {
            budget.max_bytes_per_hit = v;
        }
        if let Some(v) = cfg.get_item("max_total_bytes")?.and_then(|v| v.extract::<usize>().ok()) {
            budget.max_total_bytes = v;
        }
        if let Some(v) = cfg.get_item("max_tokens_per_hit")?.and_then(|v| v.extract::<usize>().ok()) {
            budget.max_tokens_per_hit = v;
        }
        if let Some(v) = cfg.get_item("max_total_tokens")?.and_then(|v| v.extract::<usize>().ok()) {
            budget.max_total_tokens = v;
        }
        plugin_config.budget = budget;
        if let Some(v) = cfg.get_item("timeout_ms")?.and_then(|v| v.extract::<u64>().ok()) {
            plugin_config.timeout = std::time::Duration::from_millis(v);
        }
        if let Some(v) = cfg.get_item("include_reference_labels")?.and_then(|v| v.extract::<bool>().ok()) {
            plugin_config.include_reference_labels = v;
        }
    }

    let plugin = llm_harness_runtime_session_recall::HistoryRecallPlugin::new(
        src.source.clone(),
        plugin_config,
    ).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let plugin: Arc<dyn llm_harness_agent::Plugin> = Arc::new(plugin);
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

Also update `create_session_recall_knowledge_source` to return `PySessionRecallKnowledgeSource` instead of `PyKnowledgeSource`.

- [ ] **Step 4-8: 更新 lib.rs、stub、验证**

stub:
```python
class SessionRecallKnowledgeSource:
    def as_knowledge_source(self) -> KnowledgeSource: ...

def create_session_recall_knowledge_source(
    repo: SessionRepo, index: SessionRecallIndex
) -> SessionRecallKnowledgeSource: ...

def create_history_recall_plugin(
    source: SessionRecallKnowledgeSource,
    config: Optional[dict] = None,
) -> Plugin: ...
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(knowledge): expose HistoryRecallPlugin"
```

---

### Task 8: 最终验证 + stub 检查

- [ ] **Step 1: 运行完整验证**

Run: `PYO3_PYTHON="$(pwd)/.venv/bin/python" cargo build && .venv/bin/python -m pytest tests/ -v`
Expected: 全部通过

- [ ] **Step 2: 验证 stub 零偏差**

Run: `.venv/bin/python scripts/check_stubs.py`
Expected: 零偏差

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test: final verification for Knowledge phase"
```
