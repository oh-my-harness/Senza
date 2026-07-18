//! Rules 审批系统的 Python 包装。
//!
//! 暴露：
//! - 4 个 Predicate 工厂函数（Contains / RegexField / NumberRangeField / RateLimit）
//! - `RuleChainBuilder` 链式 API
//! - `create_rule_approval_hook(chain)` → `Hook`（impl `BeforeToolCallHook`）

use std::sync::Arc;

use llm_harness_runtime::rules::{
    Contains, Decision, NumberRangeField, Predicate, RateLimit, RegexField, Rule, RuleBasedApprovalHook,
    RuleChain, RuleChainBuilder,
};
use llm_harness_types::BeforeToolCallHook;
use pyo3::prelude::*;

use crate::pyhooks::{HookKind, PyHookWrapper};

// ── Predicate wrapper ──────────────────────────────────────────────────────

/// Predicate handle（通过 `create_*_predicate` 创建）。
#[pyclass(name = "Predicate")]
pub struct PyPredicate {
    pub(crate) predicate: Box<dyn Predicate>,
}

/// 空实现，仅在 `std::mem::replace` 占位时使用。
struct NoopPredicate;

impl Predicate for NoopPredicate {
    fn test(&self, _tool_name: &str, _args: &serde_json::Value) -> bool {
        false
    }
}

// ── RuleChain wrapper ──────────────────────────────────────────────────────

/// RuleChain handle（通过 `RuleChainBuilder.build()` 创建）。
#[pyclass(name = "RuleChain")]
pub struct PyRuleChain {
    pub(crate) chain: RuleChain,
}

// ── RuleChainBuilder wrapper ───────────────────────────────────────────────

/// RuleChain builder（通过 `create_rule_chain()` 创建）。
#[pyclass(name = "RuleChainBuilder")]
pub struct PyRuleChainBuilder {
    builder: Option<RuleChainBuilder>,
}

#[pymethods]
impl PyRuleChainBuilder {
    /// 追加一条规则。
    ///
    /// - `tool_name` — 工具名，`"*"` 表示通配。
    /// - `predicate` — 通过 `create_*_predicate` 创建。
    /// - `on_match` — `"allow"` 或 `"deny"`。
    #[pyo3(text_signature = "($self, tool_name, predicate, on_match)")]
    fn rule<'a>(
        mut slf: PyRefMut<'a, Self>,
        tool_name: &str,
        predicate: &Bound<'_, PyPredicate>,
        on_match: &str,
    ) -> PyResult<PyRefMut<'a, Self>> {
        let decision = match on_match {
            "allow" => Decision::Allow,
            "deny" => Decision::Deny,
            other => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "on_match must be 'allow' or 'deny', got '{other}'"
                )));
            }
        };
        // Take predicate out of the wrapper (replace with no-op).
        let p = std::mem::replace(&mut predicate.borrow_mut().predicate, Box::new(NoopPredicate));
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.rule(Rule {
                tool_name: tool_name.to_string(),
                predicate: p,
                on_match: decision,
            }));
        }
        Ok(slf)
    }

    /// 设置全不命中时的 fallback（默认 Deny）。
    #[pyo3(text_signature = "($self, decision)")]
    fn fallback<'a>(
        mut slf: PyRefMut<'a, Self>,
        decision: &str,
    ) -> PyResult<PyRefMut<'a, Self>> {
        let d = match decision {
            "allow" => Decision::Allow,
            "deny" => Decision::Deny,
            other => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "decision must be 'allow' or 'deny', got '{other}'"
                )));
            }
        };
        if let Some(b) = slf.builder.take() {
            slf.builder = Some(b.fallback(d));
        }
        Ok(slf)
    }

    /// 构建规则链。
    #[pyo3(text_signature = "($self)")]
    fn build(&mut self) -> PyResult<PyRuleChain> {
        let b = self.builder.take().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("build() already consumed this builder")
        })?;
        Ok(PyRuleChain { chain: b.build() })
    }
}

// ── Factory functions ──────────────────────────────────────────────────────

/// 创建一个 `RuleChainBuilder`。
#[pyfunction]
#[pyo3(text_signature = "()")]
pub fn create_rule_chain<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, PyRuleChainBuilder>> {
    Py::new(py, PyRuleChainBuilder {
        builder: Some(RuleChain::builder()),
    })
    .map(|p| p.into_bound(py))
}

/// 创建一个 `Contains` predicate：tool_name ∈ allowed。
#[pyfunction]
#[pyo3(text_signature = "(allowed)")]
pub fn create_contains_predicate<'py>(
    py: Python<'py>,
    allowed: Vec<String>,
) -> PyResult<Bound<'py, PyPredicate>> {
    Py::new(py, PyPredicate {
        predicate: Box::new(Contains::new(allowed)),
    })
    .map(|p| p.into_bound(py))
}

/// 创建一个 `RegexField` predicate：args[arg_path] 匹配 pattern。
#[pyfunction]
#[pyo3(text_signature = "(arg_path, pattern)")]
pub fn create_regex_field_predicate<'py>(
    py: Python<'py>,
    arg_path: &str,
    pattern: &str,
) -> PyResult<Bound<'py, PyPredicate>> {
    let regex = regex::Regex::new(pattern)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("invalid regex: {e}")))?;
    Py::new(py, PyPredicate {
        predicate: Box::new(RegexField {
            arg_path: arg_path.to_string(),
            pattern: regex,
        }),
    })
    .map(|p| p.into_bound(py))
}

/// 创建一个 `NumberRangeField` predicate：args[arg_path] 在 [min, max]。
#[pyfunction]
#[pyo3(text_signature = "(arg_path, min, max)")]
pub fn create_number_range_predicate<'py>(
    py: Python<'py>,
    arg_path: &str,
    min: f64,
    max: f64,
) -> PyResult<Bound<'py, PyPredicate>> {
    Py::new(py, PyPredicate {
        predicate: Box::new(NumberRangeField {
            arg_path: arg_path.to_string(),
            min,
            max,
        }),
    })
    .map(|p| p.into_bound(py))
}

/// 创建一个 `RateLimit` predicate：单位时间内同 tool 调用次数 ≤ max。
#[pyfunction]
#[pyo3(text_signature = "(max, window_seconds)")]
pub fn create_rate_limit_predicate<'py>(
    py: Python<'py>,
    max: usize,
    window_seconds: f64,
) -> PyResult<Bound<'py, PyPredicate>> {
    // RateLimit::new takes u32; clamp usize → u32.
    let max_u32 = u32::try_from(max).map_err(|_| {
        pyo3::exceptions::PyValueError::new_err(format!("max must fit in u32, got {max}"))
    })?;
    Py::new(py, PyPredicate {
        predicate: Box::new(RateLimit::new(
            max_u32,
            std::time::Duration::from_secs_f64(window_seconds),
        )),
    })
    .map(|p| p.into_bound(py))
}

/// 从 `RuleChain` 创建一个工具调用审批 `Hook`（impl `BeforeToolCallHook`）。
#[pyfunction]
#[pyo3(text_signature = "(chain)")]
pub fn create_rule_approval_hook<'py>(
    py: Python<'py>,
    chain: &Bound<'py, PyRuleChain>,
) -> PyResult<Bound<'py, PyHookWrapper>> {
    // Move the RuleChain out of the wrapper (replace with an empty chain).
    let chain_inner =
        std::mem::replace(&mut chain.borrow_mut().chain, RuleChain::builder().build());
    let hook: Arc<dyn BeforeToolCallHook> = Arc::new(RuleBasedApprovalHook::new(chain_inner));
    Py::new(py, PyHookWrapper {
        kind: HookKind::BeforeToolCall(hook),
    })
    .map(|p| p.into_bound(py))
}
