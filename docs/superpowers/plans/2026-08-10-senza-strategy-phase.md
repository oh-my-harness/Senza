# Senza 全量对齐 — 阶段 2：Strategy 层绑定 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 llm-harness-strategy crate 的 12 个核心能力暴露为 Python 绑定，覆盖安全防护、循环安全、状态面板、记忆防御、注入过滤、来源标记、项目指令、审计、通知、工具输出截断、内置事件流和 context-aware 压缩。

**Architecture:** 每个绑定是一个 `create_*` 工厂函数，返回 `PyPluginWrapper`（已有的 opaque Plugin 包装）。配置通过 dict 或 builder class 传入。所有文件放在 `src/strategy/` 子目录下。

**Tech Stack:** Rust + PyO3 0.29 + llm-harness-strategy crate

## Global Constraints

- Runtime pin: `5eae99ed1c42dd558529bede9957518ba15eef5c` (已升级，阶段 1 完成)
- PyO3 版本: 0.29
- 构建命令: `PYO3_PYTHON="$(pwd)/.venv/bin/python" cargo build`
- 测试命令: `PYO3_PYTHON="$(pwd)/.venv/bin/python" cargo test` + `.venv/bin/python -m pytest tests/ -v`
- stub 检查: `.venv/bin/python scripts/check_stubs.py` 必须零偏差
- 所有 plugin 绑定返回 `PyPluginWrapper`（已有类，在 `src/core/pyplugin.rs`）
- Plugin 包装模式: `PyPluginWrapper::new(Arc::new(plugin))` → `Py::new(py, wrapper)`
- `src/strategy/mod.rs` 已存在（阶段 1 创建的占位文件），需要更新内容
- 需要 `Arc<dyn ExecutionEnv>` 的 plugin 用已有的 `create_os_env()` 返回的 `PyEnvWrapper.env` 字段
- `AuditSink` trait 对象需要从 Python 侧传入 path 创建 `JsonlAuditSink`（阶段 4 才暴露 JsonlAuditSink 本身，本阶段先用回调式 sink）

---

## File Structure

```
src/strategy/
├── mod.rs                  # re-exports all submodules
├── pysafety.rs             # SafetyDefaultsPlugin
├── pyloopsafety.rs         # LoopSafetyPlugin + config
├── pystatuspanel.rs        # StatusPanelPlugin + config
├── pymemorydefense.rs      # MemoryDefensePlugin + builder
├── pyinjection.rs          # InjectionFilterPlugin + patterns
├── pysourcetag.rs          # SourceTagPlugin
├── pyprojectinstr.rs       # ProjectInstructionPlugin
├── pyaudit.rs              # AuditPlugin
├── pynotify.rs             # NotifyPlugin + NotifyUserTool + channel
├── pytoolguard.rs          # ToolOutputGuardPlugin
├── pyeventstreams.rs       # timer/heartbeat/filter/webhook streams
└── pycompaction.rs         # context_aware_prompt_spec
```

---

### Task 1: SafetyDefaultsPlugin 绑定

**Files:**
- Create: `src/strategy/pysafety.rs`
- Modify: `src/strategy/mod.rs`
- Modify: `src/lib.rs` (注册函数)
- Modify: `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_safety_defaults.py`

**Interfaces:**
- Consumes: `llm_harness_strategy::SafetyDefaultsPlugin` (implements `Plugin`, has `new()`, `default_enabled()`)
- Produces: `senza.create_safety_defaults_plugin() -> Plugin`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_safety_defaults.py`：

```python
import senza


def test_safety_defaults_plugin_creates():
    """create_safety_defaults_plugin() returns a valid Plugin."""
    plugin = senza.create_safety_defaults_plugin()
    assert plugin is not None


def test_safety_defaults_plugin_usable_in_builder():
    """SafetyDefaultsPlugin can be installed on a harness builder."""
    provider = senza.create_openai_provider(api_key="sk-test")
    env = senza.create_os_env(".")
    plugin = senza.create_safety_defaults_plugin()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .env(env)
        .build()
    )
    assert harness is not None
    assert harness.phase() == "idle"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_safety_defaults.py -v`
Expected: FAIL with `AttributeError: module 'senza' has no attribute 'create_safety_defaults_plugin'`

- [ ] **Step 3: 实现 pysafety.rs**

创建 `src/strategy/pysafety.rs`：

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use crate::core::pyplugin::PyPluginWrapper;

/// Create a SafetyDefaultsPlugin that enforces bash command blacklist
/// and path traversal protection.
///
/// Returns a Plugin that can be installed on a HarnessBuilder via `.plugin()`.
#[pyfunction]
pub fn create_safety_defaults_plugin<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::SafetyDefaultsPlugin::new());
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

- [ ] **Step 4: 更新 mod.rs**

在 `src/strategy/mod.rs` 中添加：

```rust
pub mod pysafety;
```

- [ ] **Step 5: 在 lib.rs 注册函数**

在 `src/lib.rs` 的函数注册区域添加：

```rust
m.add_function(wrap_pyfunction!(strategy::pysafety::create_safety_defaults_plugin, m)?)?;
```

- [ ] **Step 6: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_safety_defaults.py -v`
Expected: 2 passed

- [ ] **Step 7: 更新 stub**

在 `senza-pkg/senza/__init__.pyi` 中添加（在 Plugin 区域之后）：

```python
# ── Strategy plugins ──────────────────────────────────────────────────────────

def create_safety_defaults_plugin() -> Plugin: ...
```

- [ ] **Step 8: 验证 stub 零偏差**

Run: `.venv/bin/python scripts/check_stubs.py`
Expected: 零偏差

- [ ] **Step 9: Commit**

```bash
git add src/strategy/pysafety.rs src/strategy/mod.rs src/lib.rs senza-pkg/senza/__init__.pyi tests/test_safety_defaults.py
git commit -m "feat(strategy): expose SafetyDefaultsPlugin"
```

---

### Task 2: LoopSafetyPlugin 绑定

**Files:**
- Create: `src/strategy/pyloopsafety.rs`
- Modify: `src/strategy/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_loop_safety.py`

**Interfaces:**
- Consumes: `llm_harness_strategy::LoopSafetyPlugin` (has `new(config: LoopSafetyConfig)`, `LoopSafetyConfig::default_enabled()`, `LoopSafetyConfig::disabled()`)
- Produces: `senza.create_loop_safety_plugin(config: dict | None = None) -> Plugin`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_loop_safety.py`：

```python
import senza


def test_loop_safety_default_enabled():
    """create_loop_safety_plugin() with no args enables all guards with defaults."""
    plugin = senza.create_loop_safety_plugin()
    assert plugin is not None


def test_loop_safety_disabled():
    """create_loop_safety_plugin(None) creates a disabled (no-op) plugin."""
    plugin = senza.create_loop_safety_plugin(None)
    assert plugin is not None


def test_loop_safety_in_builder():
    """LoopSafetyPlugin can be installed on a harness builder."""
    provider = senza.create_openai_provider(api_key="sk-test")
    plugin = senza.create_loop_safety_plugin()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_loop_safety.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 pyloopsafety.rs**

创建 `src/strategy/pyloopsafety.rs`：

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use crate::core::pyplugin::PyPluginWrapper;

/// Create a LoopSafetyPlugin that guards against death spirals, repetition,
/// failure cascades, truncation loops, and excessive turns.
///
/// Args:
///     config: Optional dict. If None or omitted, enables all guards with
///             defaults. If explicitly None, creates a disabled (no-op) plugin.
///             Currently only None (default-enabled) and a dict with
///             {"enabled": False} (disabled) are supported.
#[pyfunction]
pub fn create_loop_safety_plugin<'py>(
    py: Python<'py>,
    config: Option<&Bound<'_, PyAny>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let cfg = if let Some(c) = config {
        // Check if user passed {"enabled": False}
        let enabled: bool = c.getattr("get")?.call1(("enabled", true))?.extract()?;
        if enabled {
            llm_harness_strategy::LoopSafetyConfig::default_enabled()
        } else {
            llm_harness_strategy::LoopSafetyConfig::disabled()
        }
    } else {
        llm_harness_strategy::LoopSafetyConfig::default_enabled()
    };
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::LoopSafetyPlugin::new(cfg));
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证（同 Task 1 模式）**

stub 添加：
```python
def create_loop_safety_plugin(config: Optional[dict] = None) -> Plugin: ...
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(strategy): expose LoopSafetyPlugin"
```

---

### Task 3: StatusPanelPlugin 绑定

**Files:**
- Create: `src/strategy/pystatuspanel.rs`
- Modify: `src/strategy/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_status_panel.py`

**Interfaces:**
- Consumes: `llm_harness_strategy::StatusPanelPlugin` (has `new(config: StatusPanelConfig)`, `with_defaults()`)
- Produces: `senza.create_status_panel_plugin() -> Plugin`

- [ ] **Step 1: 写失败测试**

```python
import senza


def test_status_panel_plugin_creates():
    plugin = senza.create_status_panel_plugin()
    assert plugin is not None


def test_status_panel_in_builder():
    provider = senza.create_openai_provider(api_key="sk-test")
    plugin = senza.create_status_panel_plugin()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pystatuspanel.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use crate::core::pyplugin::PyPluginWrapper;

/// Create a StatusPanelPlugin that injects a status bar into the LLM context
/// and registers a todo_write tool for task tracking.
#[pyfunction]
pub fn create_status_panel_plugin<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::StatusPanelPlugin::with_defaults());
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub: `def create_status_panel_plugin() -> Plugin: ...`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(strategy): expose StatusPanelPlugin"
```

---

### Task 4: MemoryDefensePlugin 绑定

**Files:**
- Create: `src/strategy/pymemorydefense.rs`
- Modify: `src/strategy/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_memory_defense.py`

**Interfaces:**
- Consumes: `MemoryDefensePlugin::builder() -> MemoryDefensePluginBuilder` (has `.action(action)`, `.extra_file(name)`, `.extra_files(names)`, `.build() -> MemoryDefensePlugin`)
- Produces: `senza.MemoryDefensePluginBuilder` class + `senza.create_memory_defense_plugin() -> Plugin` (convenience)

- [ ] **Step 1: 写失败测试**

```python
import senza


def test_memory_defense_default():
    plugin = senza.create_memory_defense_plugin()
    assert plugin is not None


def test_memory_defense_builder():
    builder = senza.MemoryDefensePluginBuilder()
    builder = builder.extra_file("CLAUDE.md")
    plugin = builder.build()
    assert plugin is not None


def test_memory_defense_in_builder():
    provider = senza.create_openai_provider(api_key="sk-test")
    plugin = senza.create_memory_defense_plugin()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pymemorydefense.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use crate::core::pyplugin::PyPluginWrapper;

/// Builder for MemoryDefensePlugin with fluent configuration.
#[pyclass(name = "MemoryDefensePluginBuilder")]
pub struct PyMemoryDefensePluginBuilder {
    builder: llm_harness_strategy::MemoryDefensePluginBuilder,
}

#[pymethods]
impl PyMemoryDefensePluginBuilder {
    #[new]
    fn new() -> Self {
        Self {
            builder: llm_harness_strategy::MemoryDefensePlugin::builder(),
        }
    }

    /// Add an extra memory file name to protect (e.g. "CLAUDE.md").
    fn extra_file(mut slf: PyRefMut<'_, Self>, name: &str) -> PyRefMut<'_, Self> {
        slf.builder = slf.builder.take().extra_file(name);
        slf
    }

    /// Add multiple extra memory file names.
    fn extra_files(mut slf: PyRefMut<'_, Self>, names: Vec<String>) -> PyRefMut<'_, Self> {
        let refs: Vec<&str> = names.iter().map(|s| s.as_str()).collect();
        slf.builder = slf.builder.take().extra_files(&refs);
        slf
    }

    /// Build the MemoryDefensePlugin.
    fn build(mut slf: PyRefMut<'_, Self>, py: Python<'_>) -> PyResult<Bound<'_, PyPluginWrapper>> {
        let builder = std::mem::take(&mut slf.builder);
        let plugin: Arc<dyn llm_harness_agent::Plugin> =
            Arc::new(builder.build());
        Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
    }
}

// Helper trait to work around builder consuming self
trait BuilderExt {
    fn take(&mut self) -> llm_harness_strategy::MemoryDefensePluginBuilder;
}

impl BuilderExt for llm_harness_strategy::MemoryDefensePluginBuilder {
    fn take(&mut self) -> llm_harness_strategy::MemoryDefensePluginBuilder {
        std::mem::replace(self, llm_harness_strategy::MemoryDefensePlugin::builder())
    }
}

/// Create a MemoryDefensePlugin with default settings.
#[pyfunction]
pub fn create_memory_defense_plugin<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::MemoryDefensePlugin::builder().build());
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

注意：`MemoryDefensePluginBuilder` 的方法 consume self（`mut self`），需要用 `take` 模式处理。如果 `BuilderExt` trait 不工作，改为 `Option<Builder>` 包装。

- [ ] **Step 4-8: 更新 mod.rs、lib.rs（注册 class + function）、stub、验证**

stub:
```python
class MemoryDefensePluginBuilder:
    def __new__() -> MemoryDefensePluginBuilder: ...
    def extra_file(name: str) -> MemoryDefensePluginBuilder: ...
    def extra_files(names: list[str]) -> MemoryDefensePluginBuilder: ...
    def build() -> Plugin: ...

def create_memory_defense_plugin() -> Plugin: ...
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(strategy): expose MemoryDefensePlugin + builder"
```

---

### Task 5: InjectionFilterPlugin 绑定

**Files:**
- Create: `src/strategy/pyinjection.rs`
- Modify: `src/strategy/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_injection_filter.py`

**Interfaces:**
- Consumes: `InjectionFilterPlugin` (has `Default`, `InjectionFilterHook::new(patterns)`, `InjectionFilterHook::with_extra(patterns)`, `InjectionPattern::replace(pattern)`, `InjectionPattern::remove(pattern)`, `InjectionPattern::default_patterns()`)
- Produces: `senza.create_injection_filter_plugin(patterns: list[str] | None = None) -> Plugin`

- [ ] **Step 1: 写失败测试**

```python
import senza


def test_injection_filter_default():
    plugin = senza.create_injection_filter_plugin()
    assert plugin is not None


def test_injection_filter_custom_patterns():
    plugin = senza.create_injection_filter_plugin(["ignore.*instructions", "system:.*"])
    assert plugin is not None


def test_injection_filter_in_builder():
    provider = senza.create_openai_provider(api_key="sk-test")
    plugin = senza.create_injection_filter_plugin()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pyinjection.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use crate::core::pyplugin::PyPluginWrapper;

/// Create an InjectionFilterPlugin that detects and filters prompt injection
/// patterns in tool outputs.
///
/// Args:
///     patterns: Optional list of regex pattern strings. Each pattern is
///               treated as "remove" (matched text is stripped). If None,
///               uses default_patterns().
#[pyfunction]
pub fn create_injection_filter_plugin<'py>(
    py: Python<'py>,
    patterns: Option<Vec<String>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let hook = if let Some(pats) = patterns {
        let parsed: Vec<llm_harness_strategy::InjectionPattern> = pats
            .iter()
            .map(|p| llm_harness_strategy::InjectionPattern::remove(p))
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        llm_harness_strategy::InjectionFilterHook::with_extra(parsed)
    } else {
        llm_harness_strategy::InjectionFilterHook::new(
            llm_harness_strategy::InjectionPattern::default_patterns().0
        )
    };
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::InjectionFilterPlugin::new(hook));
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

注意：`InjectionPattern::default_patterns()` 返回 `Self`（即 `InjectionPattern`），不是 `Vec`。需在实现时确认 `InjectionFilterHook::new` 的签名。如果 `new` 接收 `Vec<InjectionPattern>`，则用 `default_patterns()` 传入。调整代码以匹配实际 API。

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub: `def create_injection_filter_plugin(patterns: Optional[list[str]] = None) -> Plugin: ...`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(strategy): expose InjectionFilterPlugin"
```

---

### Task 6: SourceTagPlugin 绑定

**Files:**
- Create: `src/strategy/pysourcetag.rs`
- Modify: `src/strategy/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_source_tag.py`

**Interfaces:**
- Consumes: `SourceTagPlugin::new(entries: Vec<SourceTagEntry>)`, `SourceTagEntry { tool: String, label: String }`
- Produces: `senza.create_source_tag_plugin(entries: list[dict]) -> Plugin`

- [ ] **Step 1: 写失败测试**

```python
import senza


def test_source_tag_plugin_creates():
    entries = [
        {"tool": "web_search", "label": "webpage"},
        {"tool": "read_url", "label": "webpage"},
    ]
    plugin = senza.create_source_tag_plugin(entries)
    assert plugin is not None


def test_source_tag_plugin_empty():
    plugin = senza.create_source_tag_plugin([])
    assert plugin is not None


def test_source_tag_in_builder():
    provider = senza.create_openai_provider(api_key="sk-test")
    plugin = senza.create_source_tag_plugin([{"tool": "search", "label": "web"}])
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pysourcetag.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use crate::core::pyplugin::PyPluginWrapper;

/// Create a SourceTagPlugin that wraps external content tool results in
/// `<external_content source="...">` XML tags.
///
/// Args:
///     entries: List of dicts with "tool" (tool name) and "label" (source label) keys.
#[pyfunction]
pub fn create_source_tag_plugin<'py>(
    py: Python<'py>,
    entries: Vec<Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let mut parsed = Vec::with_capacity(entries.len());
    for entry in &entries {
        let tool: String = entry.get_item("tool")?.ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err("Each entry must have a 'tool' key")
        })?.extract()?;
        let label: String = entry.get_item("label")?.ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err("Each entry must have a 'label' key")
        })?.extract()?;
        parsed.push(llm_harness_strategy::SourceTagEntry { tool, label });
    }
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::SourceTagPlugin::new(parsed));
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

注意：`SourceTagEntry` 的字段是 `pub`，可以直接构造。如果不行，检查是否有 `new` 方法。

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub: `def create_source_tag_plugin(entries: list[dict]) -> Plugin: ...`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(strategy): expose SourceTagPlugin"
```

---

### Task 7: ProjectInstructionPlugin 绑定

**Files:**
- Create: `src/strategy/pyprojectinstr.rs`
- Modify: `src/strategy/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_project_instruction.py`

**Interfaces:**
- Consumes: `ProjectInstructionPlugin::new(env: Arc<dyn ExecutionEnv>)`, `.with_config(env, config: ProjectInstructionConfig)`
- Produces: `senza.create_project_instruction_plugin(env: ExecutionEnv, config: dict | None = None) -> Plugin`

- [ ] **Step 1: 写失败测试**

```python
import senza
import tempfile


def test_project_instruction_plugin_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_project_instruction_plugin(env)
        assert plugin is not None


def test_project_instruction_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_project_instruction_plugin(
            env, {"file_names": ["CLAUDE.md", "AGENTS.md"], "max_depth": 3}
        )
        assert plugin is not None


def test_project_instruction_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = senza.create_openai_provider(api_key="sk-test")
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_project_instruction_plugin(env)
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("*", provider)
            .plugin(plugin)
            .env(env)
            .build()
        )
        assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pyprojectinstr.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use crate::core::pyplugin::PyPluginWrapper;
use crate::runtime::pyworkflow::PyEnvWrapper;

/// Create a ProjectInstructionPlugin that auto-injects project instruction
/// files (CLAUDE.md, AGENTS.md, .cursorrules, SOUL.md) into the system prompt.
///
/// Args:
///     env: ExecutionEnv (from create_os_env())
///     config: Optional dict with "file_names" (list[str]), "max_depth" (int|None),
///             "max_bytes" (int|None)
#[pyfunction]
pub fn create_project_instruction_plugin<'py>(
    py: Python<'py>,
    env: &Bound<'_, PyAny>,
    config: Option<&Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let env_wrapper: PyRef<'_, PyEnvWrapper> = env.extract()?;
    let env_arc = env_wrapper.env.clone();

    let plugin: Arc<dyn llm_harness_agent::Plugin> = if let Some(cfg) = config {
        let mut pic = llm_harness_strategy::ProjectInstructionConfig::default();
        if let Some(names) = cfg.get_item("file_names")?.and_then(|v| v.extract::<Vec<String>>().ok()) {
            pic.file_names = names;
        }
        if let Some(depth) = cfg.get_item("max_depth")?.and_then(|v| v.extract::<Option<usize>>().ok()) {
            pic.max_depth = depth;
        }
        if let Some(bytes) = cfg.get_item("max_bytes")?.and_then(|v| v.extract::<Option<u64>>().ok()) {
            pic.max_bytes = bytes;
        }
        Arc::new(llm_harness_strategy::ProjectInstructionPlugin::with_config(env_arc, pic))
    } else {
        Arc::new(llm_harness_strategy::ProjectInstructionPlugin::new(env_arc))
    };
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub: `def create_project_instruction_plugin(env: ExecutionEnv, config: Optional[dict] = None) -> Plugin: ...`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(strategy): expose ProjectInstructionPlugin"
```

---

### Task 8: AuditPlugin 绑定

**Files:**
- Create: `src/strategy/pyaudit.rs`
- Modify: `src/strategy/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_audit_plugin.py`

**Interfaces:**
- Consumes: `AuditPlugin::new(sink: Arc<dyn AuditSink>)`, `AuditPlugin::with_trace_id(self, trace_id)`, `AuditPlugin::with_task_id(self, task_id)`
- Produces: `senza.create_audit_plugin(sink_path: str, trace_id: str | None = None, task_id: str | None = None) -> Plugin`

设计说明：`AuditSink` 是 trait，Python 侧无法直接实现。本阶段用 `JsonlAuditSink` 作为内置实现（从 `llm_harness_runtime_audit_jsonl` crate），通过 path 参数创建。JsonlAuditSink 本身的完整暴露在阶段 4。

- [ ] **Step 1: 写失败测试**

```python
import senza
import tempfile
import os


def test_audit_plugin_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        sink_path = os.path.join(tmpdir, "audit.jsonl")
        plugin = senza.create_audit_plugin(sink_path)
        assert plugin is not None


def test_audit_plugin_with_trace_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        sink_path = os.path.join(tmpdir, "audit.jsonl")
        plugin = senza.create_audit_plugin(sink_path, trace_id="trace-123", task_id="task-456")
        assert plugin is not None


def test_audit_plugin_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        sink_path = os.path.join(tmpdir, "audit.jsonl")
        provider = senza.create_openai_provider(api_key="sk-test")
        plugin = senza.create_audit_plugin(sink_path)
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("*", provider)
            .plugin(plugin)
            .build()
        )
        assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pyaudit.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use crate::core::pyplugin::PyPluginWrapper;

/// Create an AuditPlugin that logs tool calls to a JSONL file with
/// SHA-256 hash-chain integrity.
///
/// Args:
///     sink_path: Path to the JSONL audit log file.
///     trace_id: Optional trace ID for correlation.
///     task_id: Optional task ID for correlation.
#[pyfunction]
#[pyo3(signature = (sink_path, trace_id=None, task_id=None))]
pub fn create_audit_plugin<'py>(
    py: Python<'py>,
    sink_path: &str,
    trace_id: Option<String>,
    task_id: Option<String>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let sink = Arc::new(llm_harness_runtime_audit_jsonl::JsonlAuditSink::new(sink_path));
    let mut plugin = llm_harness_strategy::AuditPlugin::new(sink);
    if let Some(tid) = trace_id {
        plugin = plugin.with_trace_id(tid);
    }
    if let Some(tid) = task_id {
        plugin = plugin.with_task_id(tid);
    }
    let plugin: Arc<dyn llm_harness_agent::Plugin> = Arc::new(plugin);
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub:
```python
def create_audit_plugin(
    sink_path: str,
    trace_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> Plugin: ...
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(strategy): expose AuditPlugin with JsonlAuditSink"
```

---

### Task 9: NotifyPlugin + NotifyUserTool 绑定

**Files:**
- Create: `src/strategy/pynotify.rs`
- Modify: `src/strategy/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_notify.py`

**Interfaces:**
- Consumes: `NotifyPlugin::new()`, `NotifyUserTool` (implements `Tool`), `NotificationChannel` trait, `NotificationMessage`
- Produces: `senza.create_notify_plugin() -> Plugin`

设计说明：`NotificationChannel` 是 trait，Python 侧通过回调实现。暴露一个 `create_notification_channel(callback)` 函数，将 Python callable 包装为 `NotificationChannel`。

- [ ] **Step 1: 写失败测试**

```python
import senza


def test_notify_plugin_creates():
    plugin = senza.create_notify_plugin()
    assert plugin is not None


def test_notify_plugin_in_builder():
    provider = senza.create_openai_provider(api_key="sk-test")
    plugin = senza.create_notify_plugin()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pynotify.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use crate::core::pyplugin::PyPluginWrapper;

/// Create a NotifyPlugin that registers a notify_user tool, allowing the
/// LLM to proactively send notifications to the user.
#[pyfunction]
pub fn create_notify_plugin<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::NotifyPlugin::new());
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

注意：`NotifyPlugin` 注册 `NotifyUserTool`，但该 tool 需要 `NotificationChannel` 通过 `RunExtensions` 注入。Python 侧的 channel 注入需要 `WorkflowRunRequest::with_extension`，这在本阶段不暴露（typed extension 无法从 Python 直接构造）。因此本阶段只暴露 plugin 本身——tool 会注册但 channel 需要在 Rust 侧注入。这是一个已知限制，在 stub 文档中说明。

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub: `def create_notify_plugin() -> Plugin: ...`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(strategy): expose NotifyPlugin"
```

---

### Task 10: ToolOutputGuardPlugin 绑定

**Files:**
- Create: `src/strategy/pytoolguard.rs`
- Modify: `src/strategy/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_tool_output_guard.py`

**Interfaces:**
- Consumes: `ToolOutputGuardPlugin::new(env: Arc<dyn ExecutionEnv>)`, `.with_config(env, config: ToolOutputGuardConfig)`
- Produces: `senza.create_tool_output_guard_plugin(env: ExecutionEnv, config: dict | None = None) -> Plugin`

- [ ] **Step 1: 写失败测试**

```python
import senza
import tempfile


def test_tool_output_guard_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_tool_output_guard_plugin(env)
        assert plugin is not None


def test_tool_output_guard_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_tool_output_guard_plugin(
            env, {"max_lines": 200, "max_bytes": 10000, "head_lines": 20, "tail_lines": 20}
        )
        assert plugin is not None


def test_tool_output_guard_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = senza.create_openai_provider(api_key="sk-test")
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_tool_output_guard_plugin(env)
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("*", provider)
            .plugin(plugin)
            .env(env)
            .build()
        )
        assert harness is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pytoolguard.rs**

```rust
use std::sync::Arc;
use pyo3::prelude::*;
use crate::core::pyplugin::PyPluginWrapper;
use crate::runtime::pyworkflow::PyEnvWrapper;

/// Create a ToolOutputGuardPlugin that truncates excessive tool output
/// as a fallback safety net.
///
/// Args:
///     env: ExecutionEnv (from create_os_env())
///     config: Optional dict with "max_lines", "max_bytes", "head_lines",
///             "tail_lines", "skip_tools" (list[str])
#[pyfunction]
pub fn create_tool_output_guard_plugin<'py>(
    py: Python<'py>,
    env: &Bound<'_, PyAny>,
    config: Option<&Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let env_wrapper: PyRef<'_, PyEnvWrapper> = env.extract()?;
    let env_arc = env_wrapper.env.clone();

    let plugin: Arc<dyn llm_harness_agent::Plugin> = if let Some(cfg) = config {
        let mut tc = llm_harness_strategy::ToolOutputGuardConfig::default();
        if let Some(v) = cfg.get_item("max_lines")?.and_then(|v| v.extract::<usize>().ok()) {
            tc.max_lines = v;
        }
        if let Some(v) = cfg.get_item("max_bytes")?.and_then(|v| v.extract::<usize>().ok()) {
            tc.max_bytes = v;
        }
        if let Some(v) = cfg.get_item("head_lines")?.and_then(|v| v.extract::<usize>().ok()) {
            tc.head_lines = v;
        }
        if let Some(v) = cfg.get_item("tail_lines")?.and_then(|v| v.extract::<usize>().ok()) {
            tc.tail_lines = v;
        }
        if let Some(v) = cfg.get_item("skip_tools")?.and_then(|v| v.extract::<Vec<String>>().ok()) {
            tc.skip_tools = v.into_iter().collect();
        }
        Arc::new(llm_harness_strategy::ToolOutputGuardPlugin::with_config(env_arc, tc))
    } else {
        Arc::new(llm_harness_strategy::ToolOutputGuardPlugin::new(env_arc))
    };
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
```

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub: `def create_tool_output_guard_plugin(env: ExecutionEnv, config: Optional[dict] = None) -> Plugin: ...`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(strategy): expose ToolOutputGuardPlugin"
```

---

### Task 11: 内置 EventStream 绑定

**Files:**
- Create: `src/strategy/pyeventstreams.rs`
- Modify: `src/strategy/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_event_streams.py`

**Interfaces:**
- Consumes: `TimerStream::once(fire_at, label)` / `TimerStream::interval(kind, period, label)`, `HeartbeatStream::new(interval, label)`, `FilterStream::new(inner, predicate)`, `WebhookStream::new(buffer) -> (WebhookChannel, Box<dyn EventStream>)`
- Produces: `senza.create_timer_stream(...)` / `senza.create_heartbeat_stream(...)` / `senza.create_webhook_stream(buffer) -> tuple`

设计说明：`EventStream` 是 trait 对象 `Box<dyn EventStream>`。Python 侧需要 opaque wrapper。但 EventStream 主要用于 workflow 的事件驱动场景，Senza 的 WorkflowEngine 目前不暴露 event stream 注入 API。因此本阶段暴露 webhook channel（最有用户价值：外部系统触发 workflow 事件）和 timer stream（定时触发）。

- [ ] **Step 1: 写失败测试**

```python
import senza


def test_webhook_stream_creates():
    channel, stream = senza.create_webhook_stream(buffer=16)
    assert channel is not None
    assert stream is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pyeventstreams.rs**

```rust
use pyo3::prelude::*;

/// Opaque wrapper for WebhookChannel.
#[pyclass(name = "WebhookChannel")]
pub struct PyWebhookChannel {
    pub channel: llm_harness_strategy::WebhookChannel,
}

/// Opaque wrapper for Box<dyn EventStream>.
#[pyclass(name = "EventStream")]
pub struct PyEventStream {
    pub stream: Option<Box<dyn llm_harness_types::EventStream>>,
}

/// Create a webhook event stream pair: a WebhookChannel for external systems
/// to push events, and an EventStream for the workflow engine to consume.
///
/// Returns: (WebhookChannel, EventStream)
#[pyfunction]
pub fn create_webhook_stream<'py>(
    py: Python<'py>,
    buffer: usize,
) -> PyResult<Bound<'py, PyTuple>> {
    let (channel, stream) = llm_harness_strategy::WebhookStream::new(buffer);
    let py_channel = Py::new(py, PyWebhookChannel { channel })?;
    let py_stream = Py::new(py, PyEventStream { stream: Some(stream) })?;
    Ok(PyTuple::new(py, vec![py_channel, py_stream])?.into_bound(py))
}
```

注意：`WebhookStream::new` 返回 `(WebhookChannel, Box<dyn EventStream>)`。`WebhookChannel` 可能需要暴露发送方法。检查实际 API 并调整。

- [ ] **Step 4-8: 更新 mod.rs、lib.rs（注册 2 个 class + 1 个 function）、stub、验证**

stub:
```python
class WebhookChannel:
    pass  # opaque

class EventStream:
    pass  # opaque

def create_webhook_stream(buffer: int) -> tuple[WebhookChannel, EventStream]: ...
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(strategy): expose WebhookStream event stream"
```

---

### Task 12: context_aware_prompt_spec 绑定

**Files:**
- Create: `src/strategy/pycompaction.rs`
- Modify: `src/strategy/mod.rs`, `src/lib.rs`, `senza-pkg/senza/__init__.pyi`
- Test: `tests/test_context_aware_compaction.py`

**Interfaces:**
- Consumes: `llm_harness_strategy::context_aware_prompt_spec() -> CompactionPromptSpec`
- Produces: `senza.create_context_aware_compaction_prompt() -> CompactionPromptSpec` (需要暴露 CompactionPromptSpec 为 Python 类，或返回 dict)

设计说明：`CompactionPromptSpec` 已在阶段 1 通过 `compaction_prompt(system_prompt, user_template)` 间接使用。这里暴露一个工厂函数返回预制的 context-aware spec。由于 `CompactionPromptSpec` 的字段是 `pub(crate)`，无法直接构造 Python 包装。改为返回 `(system_prompt, user_template)` 元组，用户传给 `builder.compaction_prompt(system_prompt, user_template)`。

- [ ] **Step 1: 写失败测试**

```python
import senza


def test_context_aware_compaction_prompt_returns_tuple():
    result = senza.create_context_aware_compaction_prompt()
    assert isinstance(result, tuple)
    assert len(result) == 2
    system_prompt, user_template = result
    assert isinstance(system_prompt, str)
    assert isinstance(user_template, str)
    assert "{conversation}" in user_template


def test_context_aware_compaction_prompt_usable_in_builder():
    provider = senza.create_openai_provider(api_key="sk-test")
    system_prompt, user_template = senza.create_context_aware_compaction_prompt()
    builder = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .compaction_prompt(system_prompt, user_template)
    )
    assert builder is not None
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 pycompaction.rs**

```rust
use pyo3::prelude::*;

/// Create a context-aware compaction prompt spec that preserves
/// task context, decisions, and file operations during summarization.
///
/// Returns: (system_prompt, user_template) tuple. Pass these to
/// builder.compaction_prompt(system_prompt, user_template).
#[pyfunction]
pub fn create_context_aware_compaction_prompt<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, PyTuple>> {
    let spec = llm_harness_strategy::context_aware_prompt_spec();
    let system_prompt = spec.system_prompt().to_string();
    let user_template = spec.user_template().to_string();
    Ok(PyTuple::new(py, vec![system_prompt, user_template])?.into_bound(py))
}
```

- [ ] **Step 4-8: 更新 mod.rs、lib.rs、stub、验证**

stub: `def create_context_aware_compaction_prompt() -> tuple[str, str]: ...`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(strategy): expose context_aware_prompt_spec"
```

---

### Task 13: 最终验证 + stub 检查

- [ ] **Step 1: 运行完整验证**

Run: `PYO3_PYTHON="$(pwd)/.venv/bin/python" cargo build && .venv/bin/python -m pytest tests/ -v`
Expected: 全部通过

- [ ] **Step 2: 验证 stub 零偏差**

Run: `.venv/bin/python scripts/check_stubs.py`
Expected: 零偏差

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test: final verification for Strategy phase"
```
