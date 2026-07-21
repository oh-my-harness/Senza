//! `HarnessBuilder` 的 Python 包装。
//!
//! 提供 fluent API 镜像 Rust `HarnessBuilder`：`.system_prompt()`、
//! `.max_tokens()`、`.temperature()`、`.tool()`、`.plugin()`、
//! `.provider()`、`.build()`。
//!
//! `build()` 释放 GIL 后用全局 tokio runtime 执行 async `HarnessBuilder::build`，
//! 返回 `PyAgentHarness`（包装真实 `AgentHarness`）。

use std::sync::Arc;

use llm_harness_agent::ModelInfo;
use llm_harness_agent::{Plugin, Skill};
use llm_harness_loop::config::RetryConfig;
use llm_harness_loop::final_answer::FinalAnswerMode;
use llm_harness_runtime::builder::HarnessBuilder;
use llm_harness_types::{ExecutionEnv, StreamOptions, Tool, UnsupportedEnv};
use pyo3::prelude::*;

use crate::pyagent::runtime;
use crate::pybudget::PyBudgetExceededHook;
use crate::pyharness::PyAgentHarness;
use crate::pyharness::parse_thinking_level;
use crate::pyhooks::PyHookWrapper;
use crate::pyplugin::PyPluginWrapper;
use crate::pypricing::PyPricingProvider;
use crate::pyprovider::PyProvider;
use crate::pyresponseformat::PyResponseFormat;
use crate::pyskills::PySkill;
use crate::pytool::PyToolWrapper;

use crate::pyworkflow::PyEnvWrapper;
/// Python 侧的 `HarnessBuilder`。
///
/// 镜像 Rust `HarnessBuilder` 的 fluent API。fluent 方法以 `PyRefMut`
/// 接收 `self`，修改内部 builder 后返回自身，支持链式调用。
#[pyclass(name = "HarnessBuilder")]
pub struct PyHarnessBuilder {
    builder: Option<HarnessBuilder>,
    /// 可选执行环境；`build()` 时注入。`None` → `UnsupportedEnv`（默认）。
    env: Option<Arc<dyn ExecutionEnv>>,
}
#[pymethods]
impl PyHarnessBuilder {
    #[new]
    fn new(model: &str) -> Self {
        Self {
            builder: Some(HarnessBuilder::new(model)),
            env: None,
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

    /// 设置执行环境，供 `bash`/`read`/`write`/`edit` 等需要文件系统或
    /// shell 能力的工具使用。传入 `create_os_env(working_dir)` 创建的 env。
    ///
    /// 未调用时使用 `UnsupportedEnv`——上述工具会返回错误。
    #[pyo3(text_signature = "($self, env)")]
    fn env<'a>(mut slf: PyRefMut<'a, Self>, env: &Bound<'_, PyEnvWrapper>) -> PyRefMut<'a, Self> {
        slf.env = Some(env.borrow().env.clone());
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

    /// 注册一个 `ShouldStopHook`（无需包装在 Plugin 中）。
    ///
    /// 多次调用累积多个 hook——`CompositeShouldStopHook` 为全执行语义，
    /// 注册顺序不影响正确性（每个 hook 都会运行）。
    #[pyo3(text_signature = "($self, hook)")]
    fn should_stop_hook<'a>(
        mut slf: PyRefMut<'a, Self>,
        hook: &Bound<'_, PyHookWrapper>,
    ) -> PyResult<PyRefMut<'a, Self>> {
        if let Some(b) = slf.builder.take() {
            let h = hook.borrow().as_should_stop_hook()?;
            slf.builder = Some(b.should_stop_hook(h));
        }
        Ok(slf)
    }

    /// 注册一个 `AfterTurnHook`（无需包装在 Plugin 中）。
    ///
    /// 多次调用累积多个 hook——`CompositeAfterTurnHook` 为全执行语义，
    /// 按注册顺序依次执行每个 hook（顺序保证）。
    #[pyo3(text_signature = "($self, hook)")]
    fn after_turn_hook<'a>(
        mut slf: PyRefMut<'a, Self>,
        hook: &Bound<'_, PyHookWrapper>,
    ) -> PyResult<PyRefMut<'a, Self>> {
        if let Some(b) = slf.builder.take() {
            let h = hook.borrow().as_after_turn_hook()?;
            slf.builder = Some(b.after_turn_hook(h));
        }
        Ok(slf)
    }

    /// 设置 response format，用于要求模型输出结构化 JSON。
    ///
    /// 传入 `create_json_object_format()` 或 `create_json_schema_format(...)` 创建的 format。
    /// 传 `None` 重置为默认值（不强制格式）。
    #[pyo3(text_signature = "($self, fmt)")]
    fn response_format<'a>(
        mut slf: PyRefMut<'a, Self>,
        fmt: Option<&Bound<'_, PyResponseFormat>>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            let fmt = fmt.map(|f| f.borrow().fmt.clone());
            slf.builder = Some(b.response_format(fmt));
        }
        slf
    }

    /// 直接设置 hook 集合。push 语义：hooks 追加到 builder 现有 hooks。
    ///
    /// 列表中每个 `Hook` 按其 kind 分发到对应的 hook 向量。多次调用可
    /// 组合来自不同来源的 hooks。
    #[pyo3(text_signature = "($self, hooks_list)")]
    fn hooks<'a>(
        mut slf: PyRefMut<'a, Self>,
        hooks_list: Vec<Bound<'_, PyHookWrapper>>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            let mut harness_hooks = llm_harness_agent::HarnessHooks::none();
            for h in &hooks_list {
                h.borrow().push_into(&mut harness_hooks);
            }
            slf.builder = Some(b.hooks(harness_hooks));
        }
        slf
    }

    /// 设置 transient provider 错误的重试配置。
    #[pyo3(text_signature = "($self, max_retries, base_delay_ms)")]
    fn retry<'a>(
        mut slf: PyRefMut<'a, Self>,
        max_retries: u32,
        base_delay_ms: u64,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.retry(Some(RetryConfig::new(max_retries, base_delay_ms))));
        }
        slf
    }

    /// 设置模型元数据（context_window, max_tokens）。
    #[pyo3(text_signature = "($self, context_window, max_tokens)")]
    fn model_info<'a>(
        mut slf: PyRefMut<'a, Self>,
        context_window: u32,
        max_tokens: u32,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.model_info(Some(ModelInfo {
                context_window,
                max_tokens,
            })));
        }
        slf
    }

    /// 设置 final-answer 分类模式。
    ///
    /// 接受: `"heuristic"`（默认，非工具终止消息视为最终答案）或
    /// `"tool"`（要求模型调用 `final_answer` 工具）。
    #[pyo3(text_signature = "($self, mode)")]
    fn final_answer_mode<'a>(
        mut slf: PyRefMut<'a, Self>,
        mode: &str,
    ) -> PyResult<PyRefMut<'a, Self>> {
        let m = match mode {
            "heuristic" => FinalAnswerMode::Heuristic,
            "tool" => FinalAnswerMode::required_tool(),
            other => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "final_answer_mode must be 'heuristic' or 'tool', got '{other}'"
                )));
            }
        };
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.final_answer_mode(m));
        }
        Ok(slf)
    }

    /// 设置 LLM 请求的 stream options。
    #[pyo3(text_signature = "($self, timeout_ms=None, max_retries=None)")]
    #[pyo3(signature = (timeout_ms=None, max_retries=None))]
    fn stream_options<'a>(
        mut slf: PyRefMut<'a, Self>,
        timeout_ms: Option<u64>,
        max_retries: Option<u32>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.stream_options(Some(StreamOptions {
                timeout_ms,
                max_retries,
                ..Default::default()
            })));
        }
        slf
    }

    /// 设置 steer/follow-up 队列容量。`None` 重置为默认值（32）。
    #[pyo3(text_signature = "($self, capacity=None)")]
    #[pyo3(signature = (capacity=None))]
    fn queue_capacity<'a>(
        mut slf: PyRefMut<'a, Self>,
        capacity: Option<usize>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.queue_capacity(capacity));
        }
        slf
    }

    /// 禁用 `SkillReadTool` 的自动注册。
    ///
    /// 默认情况下，当 skills 存在时 `build()` 会自动注册 `SkillReadTool`。
    /// 调用此方法可选择退出。
    #[pyo3(text_signature = "($self)")]
    fn disable_skill_read_tool<'a>(mut slf: PyRefMut<'a, Self>) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.disable_skill_read_tool());
        }
        slf
    }

    /// 追加单个 skill。
    ///
    /// skill 须由 `load_skills()` 创建。多次调用累积多个 skill。
    #[pyo3(text_signature = "($self, skill)")]
    fn skill<'a>(mut slf: PyRefMut<'a, Self>, skill: &Bound<'_, PySkill>) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            let plugin = SingleSkillPlugin {
                skill: skill.borrow().skill.clone(),
            };
            slf.builder = Some(b.install(&plugin));
        }
        slf
    }

    /// 追加多个 skill。
    ///
    /// `skills` 须由 `load_skills()` 创建。多次调用累积。
    #[pyo3(text_signature = "($self, skills)")]
    fn skills<'a>(
        mut slf: PyRefMut<'a, Self>,
        skills: Vec<Bound<'_, PySkill>>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            let collected: Vec<Skill> = skills.iter().map(|s| s.borrow().skill.clone()).collect();
            let plugin = MultiSkillPlugin { skills: collected };
            slf.builder = Some(b.install(&plugin));
        }
        slf
    }
    /// 配置独立的 compaction 模型。
    ///
    /// 设置后，compaction 摘要使用独立 provider/model，
    /// 而非主对话 client。`context_window` 和 `max_tokens`
    /// 应反映 compaction 模型的真实参数。
    #[pyo3(text_signature = "($self, model, context_window, max_tokens)")]
    fn compaction_model<'a>(
        mut slf: PyRefMut<'a, Self>,
        model: &str,
        context_window: u32,
        max_tokens: u32,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.compaction_model(
                model,
                ModelInfo {
                    context_window,
                    max_tokens,
                },
            ));
        }
        slf
    }

    /// 设置 pricing provider，用于成本计算。
    ///
    /// 设置后 builder 自动注入 `CostAccumulatorHook`，
    /// `harness.usage()["total_cost"]` 才有 USD 值。
    #[pyo3(text_signature = "($self, provider)")]
    fn pricing<'a>(
        mut slf: PyRefMut<'a, Self>,
        provider: &Bound<'_, PyPricingProvider>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            let p = provider.borrow().provider.clone();
            slf.builder = Some(b.pricing(p));
        }
        slf
    }
    /// 配置预算上限和可选的超限 hook。
    ///
    /// - `limit` — 预算上限（USD）。
    /// - `exceeded_hook=None` → surveillance 模式：只统计成本，不停。
    /// - `exceeded_hook=Some(h)` → 超限时由 `h` 决定继续/停止。
    #[pyo3(text_signature = "($self, limit, exceeded_hook=None)")]
    #[pyo3(signature = (limit, exceeded_hook=None))]
    fn budget<'a>(
        mut slf: PyRefMut<'a, Self>,
        limit: f64,
        exceeded_hook: Option<&Bound<'_, PyBudgetExceededHook>>,
    ) -> PyRefMut<'a, Self> {
        if let Some(b) = slf.builder.take() {
            let hook = exceeded_hook.map(|h| h.borrow().hook.clone());
            slf.builder = Some(b.budget(limit, hook));
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
    /// 执行环境为 `.env()` 设置的 env；未设置时使用 `UnsupportedEnv`
    /// （无文件系统 / shell 能力）。释放 GIL 后用全局 tokio runtime
    /// 执行 async build。若未注册任何 provider，返回 `RuntimeError`
    /// （`HarnessBuildError::NoProvider`）。
    fn build(&mut self, py: Python<'_>) -> PyResult<Py<PyAgentHarness>> {
        let builder = self.builder.take().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("build() already consumed this builder")
        })?;

        let env: Arc<dyn ExecutionEnv> = self
            .env
            .take()
            .unwrap_or_else(|| Arc::new(UnsupportedEnv::new()));
        let rt = runtime(py);
        let harness = crate::pyerror::detach_catch_panic_result(py, move || {
            rt.block_on(async move { builder.build(env).await })
        })?;
        Py::new(py, PyAgentHarness::new(Arc::new(harness)))
    }
}

// ── pub(crate) helpers（非 #[pymethods]：返回 Rust 类型） ─────────────────────

impl PyHarnessBuilder {
    /// 取出内部 `HarnessBuilder`（供 `with_step_builder` 适配器使用）。
    pub(crate) fn take_builder(&mut self) -> Option<HarnessBuilder> {
        self.builder.take()
    }

    /// 从已有 `HarnessBuilder` 构造包装（供 `with_step_builder` 适配器使用）。
    pub(crate) fn from_builder(b: HarnessBuilder) -> Self {
        Self {
            builder: Some(b),
            env: None,
        }
    }
}

// ── Skill plugin helpers ────────────────────────────────────────────────────

/// 单 skill 插件——通过 `Plugin::register_skills` 注入一个 skill。
struct SingleSkillPlugin {
    skill: Skill,
}

impl Plugin for SingleSkillPlugin {
    fn name(&self) -> &str {
        "senza-single-skill"
    }

    fn register_skills(&self, skills: &mut Vec<Skill>) {
        skills.push(self.skill.clone());
    }
}

/// 多 skill 插件——通过 `Plugin::register_skills` 注入一组 skill。
struct MultiSkillPlugin {
    skills: Vec<Skill>,
}

impl Plugin for MultiSkillPlugin {
    fn name(&self) -> &str {
        "senza-multi-skill"
    }

    fn register_skills(&self, skills: &mut Vec<Skill>) {
        skills.extend(self.skills.iter().cloned());
    }
}
