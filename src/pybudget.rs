//! BudgetExceededHook 的 Python 包装。
//!
//! callback 签名：`callback(cost: dict, limit: float) -> bool`
//! 返回 `True` 继续，`False` 停止并标记失败。支持 `async def`。
//!
//! 复用 `pyhooks` 的 async callback 执行模式（`spawn_blocking` +
//! `Python::attach` + `call_callback_with_mode`），async def 回调在
//! `spawn_blocking` 线程上通过 `asyncio.run()` 执行。

use std::sync::Arc;

use futures::future::BoxFuture;
use llm_harness_runtime::control::budget::BudgetExceededHook;
use llm_harness_types::CostAggregate;
use pyo3::prelude::*;

use crate::pyhooks::{call_callback_with_mode, detect_async};
use crate::pyworkflow::cost_aggregate_to_dict;

/// Python 侧的 `BudgetExceededHook` wrapper。
///
/// 不透明句柄：由 `create_budget_exceeded_hook` 创建，传给
/// `HarnessBuilder.budget(limit, exceeded_hook=...)`。
#[pyclass(name = "BudgetExceededHook")]
pub struct PyBudgetExceededHook {
    pub(crate) hook: Arc<dyn BudgetExceededHook>,
}

impl PyBudgetExceededHook {
    pub fn new(hook: Arc<dyn BudgetExceededHook>) -> Self {
        Self { hook }
    }
}

/// Python callable → `BudgetExceededHook`。
struct PyBudgetCallback {
    callback: Arc<Py<PyAny>>,
    is_async: bool,
}

impl PyBudgetCallback {
    fn new(callback: Py<PyAny>) -> Self {
        let is_async = detect_async(&callback);
        Self {
            callback: Arc::new(callback),
            is_async,
        }
    }
}

impl BudgetExceededHook for PyBudgetCallback {
    fn on_budget_exceeded<'a>(
        &'a self,
        cost: &'a CostAggregate,
        budget_limit: f64,
    ) -> BoxFuture<'a, bool> {
        let cb = Arc::clone(&self.callback);
        let is_async = self.is_async;
        // CostAggregate 实现了 Clone；在进入 spawn_blocking 前提取 owned 数据，
        // 避免跨线程借用 &'a CostAggregate（其生命周期可能短于 blocking 线程）。
        let cost = cost.clone();

        Box::pin(async move {
            let result = tokio::task::spawn_blocking(move || {
                Python::attach(|py| {
                    let cost_dict = cost_aggregate_to_dict(py, &cost)?;
                    let raw =
                        call_callback_with_mode(py, &cb, (cost_dict, budget_limit), is_async)?;
                    let should_continue: bool = raw.extract()?;
                    Ok::<_, PyErr>(should_continue)
                })
            })
            .await;

            match result {
                Ok(Ok(b)) => b,
                Ok(Err(e)) => {
                    tracing::warn!("BudgetExceededHook error: {e}");
                    // fail-safe: 停止，避免预算超限后继续烧钱
                    false
                }
                Err(e) => {
                    tracing::warn!("BudgetExceededHook join error: {e}");
                    false
                }
            }
        })
    }
}

/// 从 Python callable 创建一个 `BudgetExceededHook`。
///
/// callback 签名：`callback(cost: dict, limit: float) -> bool`
/// 返回 `True` 继续运行，`False` 停止并标记失败。
/// 支持 `async def` 回调（在 `spawn_blocking` 线程上通过 `asyncio.run()` 执行）。
#[pyfunction]
#[pyo3(text_signature = "(callback)")]
pub fn create_budget_exceeded_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, PyBudgetExceededHook>> {
    let hook: Arc<dyn BudgetExceededHook> = Arc::new(PyBudgetCallback::new(callback));
    Py::new(py, PyBudgetExceededHook::new(hook)).map(|p| p.into_bound(py))
}
