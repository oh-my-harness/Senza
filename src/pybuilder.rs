//! `HarnessBuilder` 的 Python 包装。
//!
//! 提供 fluent API 镜像 Rust `HarnessBuilder`：`.system_prompt()`、
//! `.max_tokens()`、`.temperature()`、`.tool()`、`.plugin()`、
//! `.provider()`、`.build()`。
//!
//! `build()` 释放 GIL 后用全局 tokio runtime 执行 async `HarnessBuilder::build`，
//! 返回 `PyAgentHarness`（包装真实 `AgentHarness`）。

use std::sync::Arc;

use llm_harness_runtime::builder::HarnessBuilder;
use llm_harness_types::{ExecutionEnv, Tool, UnsupportedEnv};
use pyo3::prelude::*;

use crate::pyagent::runtime;
use crate::pyharness::PyAgentHarness;
use crate::pyharness::parse_thinking_level;
use crate::pyplugin::PyPluginWrapper;
use crate::pyprovider::PyProvider;
use crate::pytool::PyToolWrapper;

/// Python 侧的 `HarnessBuilder`。
///
/// 镜像 Rust `HarnessBuilder` 的 fluent API。fluent 方法以 `PyRefMut`
/// 接收 `self`，修改内部 builder 后返回自身，支持链式调用。
#[pyclass(name = "HarnessBuilder")]
pub struct PyHarnessBuilder {
    builder: Option<HarnessBuilder>,
}
#[pymethods]
impl PyHarnessBuilder {
    /// 创建一个新的 builder，指定初始模型 ID。
    #[new]
    fn new(model: &str) -> Self {
        Self {
            builder: Some(HarnessBuilder::new(model)),
        }
    }

    /// 设置系统提示。重复调用后写覆盖前写。
    fn system_prompt<'a>(mut slf: PyRefMut<'a, Self>, prompt: &str) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.system_prompt(Some(prompt.to_string())));
        }
        slf
    }

    /// 设置每次 provider 调用的最大输出 token 数。
    fn max_tokens<'a>(mut slf: PyRefMut<'a, Self>, tokens: u32) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.max_tokens(tokens));
        }
        slf
    }

    /// 设置采样温度。`None` 重置为 provider 默认值。
    fn temperature<'a>(mut slf: PyRefMut<'a, Self>, temp: Option<f32>) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.temperature(temp));
        }
        slf
    }

    /// 注册一个 `Tool`（来自 `create_tool`）。
    fn tool<'a>(
        mut slf: PyRefMut<'a, Self>,
        tool: &Bound<'_, PyToolWrapper>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            let t: Arc<dyn Tool> = tool.borrow().tool.clone();
            slf.builder = Some(b.tool(t));
        }
        slf
    }

    /// 安装一个 `Plugin`（来自 `create_plugin`），累积其 tools/hooks/skills。
    fn plugin<'a>(
        mut slf: PyRefMut<'a, Self>,
        plugin: &Bound<'_, PyPluginWrapper>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            let p = &plugin.borrow().plugin;
            slf.builder = Some(b.install(p.as_ref()));
        }
        slf
    }

    /// 注册一个 LLM provider，匹配 `pattern` 的 model 会路由到此 provider。
    fn provider<'a>(
        mut slf: PyRefMut<'a, Self>,
        pattern: &str,
        provider: &Bound<'_, PyProvider>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            let client = provider.borrow().client.clone();
            slf.builder = Some(b.provider(pattern, client));
        }
        slf
    }

    /// 设置 thinking level（构建时）。
    ///
    /// 接受: "off", "minimal", "low", "medium", "high", "xhigh", 或 "budget:<tokens>"。
    fn thinking_level<'a>(
        mut slf: PyRefMut<'a, Self>,
        level: &str,
    ) -> PyResult<PyRefMut<'a, Self>> {
        if let Some(b) = slf.builder.take() {
            let tl = parse_thinking_level(level)?;
            slf.builder = Some(b.thinking_level(tl));
        }
        Ok(slf)
    }

    /// Enable or disable auto-compaction (enabled by default).
    fn auto_compact<'a>(mut slf: PyRefMut<'a, Self>, enabled: bool) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.auto_compact(enabled));
        }
        slf
    }

    /// Set the token budget reserved for system prompt + new response during compaction.
    fn compaction_reserve_tokens<'a>(
        mut slf: PyRefMut<'a, Self>,
        tokens: Option<u32>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.compaction_reserve_tokens(tokens));
        }
        slf
    }

    /// Set how many recent tokens to keep unsummarized during compaction.
    fn compaction_keep_recent_tokens<'a>(
        mut slf: PyRefMut<'a, Self>,
        tokens: Option<u32>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.compaction_keep_recent_tokens(tokens));
        }
        slf
    }

    /// 返回 builder 状态摘要。
    fn __repr__(&self) -> String {
        match &self.builder {
            Some(_) => "HarnessBuilder(pending)".to_string(),
            None => "HarnessBuilder(consumed)".to_string(),
        }
    }

    /// 构建 harness 并返回 `AgentHarness`。
    ///
    /// 使用 `UnsupportedEnv`（无文件系统 / shell 能力）作为执行环境。
    /// 释放 GIL 后用全局 tokio runtime 执行 async build。若未注册任何
    /// provider，返回 `RuntimeError`（`HarnessBuildError::NoProvider`）。
    fn build(&mut self, py: Python<'_>) -> PyResult<Py<PyAgentHarness>> {
        let builder = self.builder.take().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("build() already consumed this builder")
        })?;

        let env: Arc<dyn ExecutionEnv> = Arc::new(UnsupportedEnv::new());
        let rt = runtime(py);
        let result = py.detach(move || rt.block_on(async move { builder.build(env).await }));

        match result {
            Ok(harness) => Py::new(py, PyAgentHarness::new(Arc::new(harness))),
            Err(e) => Err(pyo3::exceptions::PyRuntimeError::new_err(e.to_string())),
        }
    }
}
