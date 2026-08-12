//! Panic 隔离 + 类型化 Python 异常层级。
//!
//! 所有 `py.detach(block_on(...))` 调用应通过 `detach_catch_panic` /
//! `detach_catch_panic_result` 包裹，确保 Rust 侧的 panic 不会导致
//! Python 进程崩溃（SIGSEGV / Core Dump），而是映射为可捕获的
//! `senza.RustPanicError`。
//!
//! 此外，本模块定义了 Senza 的类型化异常层级，将 runtime 侧的 typed
//! error enum（`AgentError`、`HarnessError`、`WorkflowError` 等）映射
//! 为 Python 异常类，保留结构化信息（budget limits、step IDs 等）。

use std::future::Future;

use pyo3::exceptions::PyRuntimeError;
use pyo3::marker::Ungil;
use pyo3::prelude::*;

// ── Python 异常层级 ─────────────────────────────────────────────────────────

pyo3::create_exception!(senza, SenzaError, PyRuntimeError);
pyo3::create_exception!(senza, ProviderError, SenzaError);
pyo3::create_exception!(senza, RateLimitError, ProviderError);
pyo3::create_exception!(senza, ProviderTimeoutError, ProviderError);
pyo3::create_exception!(senza, ToolError, SenzaError);
pyo3::create_exception!(senza, ToolArgumentError, ToolError);
pyo3::create_exception!(senza, ToolAbortedError, ToolError);
pyo3::create_exception!(senza, ToolExecutionError, ToolError);
pyo3::create_exception!(senza, BudgetExceededError, SenzaError);
pyo3::create_exception!(senza, WorkflowError, SenzaError);
pyo3::create_exception!(senza, StepTimeoutError, WorkflowError);
pyo3::create_exception!(senza, StepFailedError, WorkflowError);
pyo3::create_exception!(senza, WorkflowPausedError, WorkflowError);
pyo3::create_exception!(senza, ValidationError, pyo3::exceptions::PyValueError);
pyo3::create_exception!(senza, HarnessStateError, SenzaError);
pyo3::create_exception!(senza, CompactionError, SenzaError);
pyo3::create_exception!(senza, StreamIdleTimeoutError, SenzaError);

pyo3::create_exception!(senza, RustPanicError, PyRuntimeError);

// ── Panic payload 提取 ──────────────────────────────────────────────────────

/// 从 panic payload（`Box<dyn Any + Send>`）提取消息字符串。
fn panic_payload_to_string(payload: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = payload.downcast_ref::<String>() {
        s.clone()
    } else if let Some(s) = payload.downcast_ref::<&'static str>() {
        (*s).to_string()
    } else {
        "unknown panic (non-string panic payload)".to_string()
    }
}

// ── Panic-safe detach wrappers ──────────────────────────────────────────────

/// `py.detach(f)` 的 panic-safe 版本（闭包返回 `Result<T, E>`）。
pub fn detach_catch_panic_result<R, E>(
    py: Python<'_>,
    f: impl FnOnce() -> Result<R, E> + Ungil + Send,
) -> PyResult<R>
where
    R: Ungil + Send,
    E: std::fmt::Display + Ungil + Send,
{
    let caught = py.detach(move || std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)));
    match caught {
        Ok(Ok(val)) => Ok(val),
        Ok(Err(e)) => Err(PyRuntimeError::new_err(e.to_string())),
        Err(payload) => Err(RustPanicError::new_err(panic_payload_to_string(&payload))),
    }
}

/// `py.detach(f)` 的 panic-safe 版本（闭包返回裸值，非 Result）。
pub fn detach_catch_panic<R: Ungil + Send>(
    py: Python<'_>,
    f: impl FnOnce() -> R + Ungil + Send,
) -> PyResult<R> {
    let caught = py.detach(move || std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)));
    match caught {
        Ok(val) => Ok(val),
        Err(payload) => Err(RustPanicError::new_err(panic_payload_to_string(&payload))),
    }
}

/// 在 tokio runtime 上执行 future，同时定期检查 Python 信号（SIGINT）。
pub fn block_on_with_signal_check<R, F>(
    py: Python<'_>,
    rt: &'static tokio::runtime::Runtime,
    future: F,
    signal_check_interval_ms: u64,
) -> PyResult<R>
where
    R: Send + Ungil + 'static,
    F: Future<Output = PyResult<R>> + Send + 'static,
{
    let interval = std::time::Duration::from_millis(signal_check_interval_ms);
    let caught = py.detach(move || {
        std::panic::catch_unwind(std::panic::AssertUnwindSafe(move || {
            rt.block_on(async move {
                tokio::pin!(future);
                loop {
                    tokio::select! {
                        biased;
                        result = &mut future => {
                            return result;
                        }
                        _ = tokio::time::sleep(interval) => {
                            Python::attach(|py| py.check_signals())?;
                        }
                    }
                }
            })
        }))
    });
    match caught {
        Ok(Ok(val)) => Ok(val),
        Ok(Err(e)) => Err(e),
        Err(payload) => Err(RustPanicError::new_err(panic_payload_to_string(&payload))),
    }
}

/// `py.detach(f)` 的 panic-safe 版本（闭包返回 `PyResult<R>`）。
pub fn detach_catch_panic_pyresult<R: Ungil + Send>(
    py: Python<'_>,
    f: impl FnOnce() -> PyResult<R> + Ungil + Send,
) -> PyResult<R> {
    let caught = py.detach(move || std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)));
    match caught {
        Ok(Ok(val)) => Ok(val),
        Ok(Err(e)) => Err(e),
        Err(payload) => Err(RustPanicError::new_err(panic_payload_to_string(&payload))),
    }
}

// ── 错误映射函数 ─────────────────────────────────────────────────────────────

use llm_harness_runtime::lifecycle::task::TaskError;
use llm_harness_runtime::workflow::error::WorkflowError as RustWorkflowError;
use llm_harness_types::{AgentError, HarnessError, ProviderErrorKind, ToolError as RustToolError};

/// 在 PyErr 异常实例上设置属性。
fn set_attr_str(py: Python<'_>, exc: &PyErr, name: &str, value: String) {
    if let Ok(instance) = exc.value(py).extract::<Py<PyAny>>() {
        let _ = instance.bind(py).setattr(name, value);
    }
}

fn set_attr_f64(py: Python<'_>, exc: &PyErr, name: &str, value: Option<f64>) {
    if let Ok(instance) = exc.value(py).extract::<Py<PyAny>>() {
        let _ = instance.bind(py).setattr(name, value);
    }
}

fn set_attr_u64(py: Python<'_>, exc: &PyErr, name: &str, value: u64) {
    if let Ok(instance) = exc.value(py).extract::<Py<PyAny>>() {
        let _ = instance.bind(py).setattr(name, value);
    }
}

fn set_attr_f64_val(py: Python<'_>, exc: &PyErr, name: &str, value: f64) {
    if let Ok(instance) = exc.value(py).extract::<Py<PyAny>>() {
        let _ = instance.bind(py).setattr(name, value);
    }
}
/// Map `AgentError` → typed Python exception.
pub fn agent_error_to_pyerr(e: AgentError) -> PyErr {
    match e {
        AgentError::ProviderTyped { message, kind } => match kind {
            ProviderErrorKind::RateLimit { retry_after } => {
                let exc = RateLimitError::new_err(message);
                Python::attach(|py| {
                    set_attr_f64(
                        py,
                        &exc,
                        "retry_after",
                        retry_after.map(|d| d.as_secs_f64()),
                    );
                });
                exc
            }
            ProviderErrorKind::Overloaded { retry_after } => {
                let exc = ProviderError::new_err(message);
                Python::attach(|py| {
                    set_attr_f64(
                        py,
                        &exc,
                        "retry_after",
                        retry_after.map(|d| d.as_secs_f64()),
                    );
                });
                exc
            }
            ProviderErrorKind::Timeout => ProviderTimeoutError::new_err(message),
            _ => ProviderError::new_err(message),
        },
        AgentError::Provider(msg) => ProviderError::new_err(msg),
        AgentError::Tool { tool_name, message } => {
            let exc = ToolExecutionError::new_err(format!("{tool_name}: {message}"));
            Python::attach(|py| {
                set_attr_str(py, &exc, "tool_name", tool_name);
            });
            exc
        }
        AgentError::FinalAnswerRejected { code, message } => {
            ToolError::new_err(format!("final answer rejected ({code}): {message}"))
        }
        AgentError::Aborted => ToolAbortedError::new_err("aborted"),
        AgentError::NotIdle => HarnessStateError::new_err("agent is not idle"),
        AgentError::InvalidInput(msg) => pyo3::exceptions::PyValueError::new_err(msg),
        AgentError::StreamIdle { timeout_ms } => {
            StreamIdleTimeoutError::new_err(format!("stream idle timeout after {timeout_ms}ms"))
        }
        AgentError::ResourceLimitExceeded(msg) => {
            SenzaError::new_err(format!("resource limit exceeded: {msg}"))
        }
        AgentError::Internal(msg) => SenzaError::new_err(msg),
    }
}

/// Map `HarnessError` → typed Python exception.
pub fn harness_error_to_pyerr(e: HarnessError) -> PyErr {
    match e {
        HarnessError::NotIdle(phase) => {
            HarnessStateError::new_err(format!("harness is not idle (phase: {phase:?})"))
        }
        HarnessError::SkillNotFound(name) => pyo3::exceptions::PyKeyError::new_err(name),
        HarnessError::Agent(e) => agent_error_to_pyerr(e),
        HarnessError::Session(e) => SenzaError::new_err(e.to_string()),
        HarnessError::Compaction(e) => CompactionError::new_err(e.to_string()),
        HarnessError::Env(e) => SenzaError::new_err(e.to_string()),
        HarnessError::Template(e) => SenzaError::new_err(e.to_string()),
    }
}

/// Map `WorkflowError` → typed Python exception.
pub fn workflow_error_to_pyerr(e: RustWorkflowError) -> PyErr {
    match e {
        RustWorkflowError::Validation(e) => ValidationError::new_err(e.to_string()),
        RustWorkflowError::WorkflowNotFound { task_id } => {
            pyo3::exceptions::PyKeyError::new_err(task_id)
        }
        RustWorkflowError::ExecutorNotFound { name } => pyo3::exceptions::PyKeyError::new_err(name),
        RustWorkflowError::StepTimeout { id, timeout_ms } => {
            let exc =
                StepTimeoutError::new_err(format!("step '{id}' timed out after {timeout_ms} ms"));
            Python::attach(|py| {
                set_attr_str(py, &exc, "step_id", id);
                set_attr_u64(py, &exc, "timeout_ms", timeout_ms);
            });
            exc
        }
        RustWorkflowError::StepExhausted {
            id, max_attempts, ..
        } => {
            let exc =
                StepFailedError::new_err(format!("step '{id}' exhausted {max_attempts} attempts"));
            Python::attach(|py| {
                set_attr_str(py, &exc, "step_id", id);
            });
            exc
        }
        RustWorkflowError::StepFailed { id, .. } => {
            let exc = StepFailedError::new_err(format!("step '{id}' failed"));
            Python::attach(|py| {
                set_attr_str(py, &exc, "step_id", id);
            });
            exc
        }
        RustWorkflowError::Paused(reason) => WorkflowPausedError::new_err(reason),
        RustWorkflowError::Harness(e) => harness_error_to_pyerr(e),
        RustWorkflowError::AlreadyRunning => SenzaError::new_err(e.to_string()),
        RustWorkflowError::InvalidStatus { .. } => HarnessStateError::new_err(e.to_string()),
        _ => SenzaError::new_err(e.to_string()),
    }
}

/// Map `TaskError` → typed Python exception.
pub fn task_error_to_pyerr(e: TaskError) -> PyErr {
    match e {
        TaskError::BudgetExceeded { limit, spent } => {
            let exc = BudgetExceededError::new_err(format!(
                "budget exceeded: limit={limit}, spent={spent}"
            ));
            Python::attach(|py| {
                set_attr_f64_val(py, &exc, "limit", limit);
                set_attr_f64_val(py, &exc, "spent", spent);
            });
            exc
        }
        TaskError::Cancelled(reason) => SenzaError::new_err(format!("task cancelled: {reason}")),
        TaskError::Paused(reason) => WorkflowPausedError::new_err(reason),
        TaskError::AuthError(msg) => ProviderError::new_err(format!("auth error: {msg}")),
        TaskError::RetriesExhausted { max } => {
            StepFailedError::new_err(format!("retries exhausted: max={max}"))
        }
        TaskError::Internal(msg) => SenzaError::new_err(msg),
    }
}

/// Map `RustToolError` → typed Python exception.
pub fn tool_error_to_pyerr(e: RustToolError) -> PyErr {
    match e {
        RustToolError::InvalidArguments(msg) => {
            ToolArgumentError::new_err(format!("invalid arguments: {msg}"))
        }
        RustToolError::Aborted => ToolAbortedError::new_err("tool aborted"),
        RustToolError::Execution(msg) => ToolExecutionError::new_err(msg),
        RustToolError::Other(e) => ToolExecutionError::new_err(e.to_string()),
    }
}
