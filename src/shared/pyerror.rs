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
// ProviderErrorKind → 1:1 typed exceptions (runtime typed provider errors).
// Timeout 复用既有的 ProviderTimeoutError（历史命名，保留兼容）。
pyo3::create_exception!(senza, InvalidRequestError, ProviderError);
pyo3::create_exception!(senza, UnauthorizedError, ProviderError);
pyo3::create_exception!(senza, ForbiddenError, ProviderError);
pyo3::create_exception!(senza, OverloadedError, ProviderError);
pyo3::create_exception!(senza, ServerError, ProviderError);
pyo3::create_exception!(senza, StreamError, ProviderError);
pyo3::create_exception!(senza, StreamIncompleteError, ProviderError);
pyo3::create_exception!(senza, NetworkError, ProviderError);
pyo3::create_exception!(senza, DecodeError, ProviderError);
pyo3::create_exception!(senza, ProviderCodeError, ProviderError);
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
            ProviderErrorKind::InvalidRequest(_) => InvalidRequestError::new_err(message),
            ProviderErrorKind::Unauthorized => UnauthorizedError::new_err(message),
            ProviderErrorKind::Forbidden => ForbiddenError::new_err(message),
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
                let exc = OverloadedError::new_err(message);
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
            ProviderErrorKind::ServerError(_) => ServerError::new_err(message),
            ProviderErrorKind::Timeout => ProviderTimeoutError::new_err(message),
            ProviderErrorKind::Stream(_) => StreamError::new_err(message),
            ProviderErrorKind::StreamIncomplete {
                received_chunks,
                finish_reason,
            } => {
                let exc = StreamIncompleteError::new_err(message);
                Python::attach(|py| {
                    set_attr_u64(py, &exc, "received_chunks", received_chunks as u64);
                    if let Ok(instance) = exc.value(py).extract::<Py<PyAny>>() {
                        let _ = instance.bind(py).setattr("finish_reason", finish_reason);
                    }
                });
                exc
            }
            ProviderErrorKind::Network => NetworkError::new_err(message),
            ProviderErrorKind::Decode(_) => DecodeError::new_err(message),
            ProviderErrorKind::Other { code } => {
                let exc = ProviderCodeError::new_err(message);
                Python::attach(|py| {
                    set_attr_str(py, &exc, "code", code);
                });
                exc
            }
            // #[non_exhaustive] 兜底——runtime 未来新增 kind 不会破坏编译。
            _ => ProviderError::new_err(message),
        },
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

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::Python;
    use std::time::Duration;

    fn provider_typed(message: &str, kind: ProviderErrorKind) -> AgentError {
        AgentError::ProviderTyped {
            message: message.to_string(),
            kind,
        }
    }

    /// 断言 `agent_error_to_pyerr` 把 ProviderTyped 的 kind 映射为对应的 Python 异常类。
    #[test]
    fn maps_provider_typed_to_typed_python_exceptions() {
        Python::attach(|py| {
            let cases: Vec<(AgentError, &str)> = vec![
                (
                    provider_typed("bad", ProviderErrorKind::InvalidRequest("x".into())),
                    "InvalidRequestError",
                ),
                (
                    provider_typed("no auth", ProviderErrorKind::Unauthorized),
                    "UnauthorizedError",
                ),
                (
                    provider_typed("denied", ProviderErrorKind::Forbidden),
                    "ForbiddenError",
                ),
                (
                    provider_typed(
                        "limited",
                        ProviderErrorKind::RateLimit {
                            retry_after: Some(Duration::from_secs(30)),
                        },
                    ),
                    "RateLimitError",
                ),
                (
                    provider_typed("busy", ProviderErrorKind::Overloaded { retry_after: None }),
                    "OverloadedError",
                ),
                (
                    provider_typed("500", ProviderErrorKind::ServerError("boom".into())),
                    "ServerError",
                ),
                (
                    provider_typed("timeout", ProviderErrorKind::Timeout),
                    "ProviderTimeoutError",
                ),
                (
                    provider_typed("stream", ProviderErrorKind::Stream("reset".into())),
                    "StreamError",
                ),
                (
                    provider_typed(
                        "cut",
                        ProviderErrorKind::StreamIncomplete {
                            received_chunks: 3,
                            finish_reason: Some("length".into()),
                        },
                    ),
                    "StreamIncompleteError",
                ),
                (
                    provider_typed("net", ProviderErrorKind::Network),
                    "NetworkError",
                ),
                (
                    provider_typed("decode", ProviderErrorKind::Decode("json".into())),
                    "DecodeError",
                ),
                (
                    provider_typed(
                        "E429",
                        ProviderErrorKind::Other {
                            code: "E429".into(),
                        },
                    ),
                    "ProviderCodeError",
                ),
            ];

            for (e, expected) in cases {
                let err = agent_error_to_pyerr(e);
                let value = err.value(py);
                let actual = value
                    .getattr("__class__")
                    .unwrap()
                    .getattr("__name__")
                    .unwrap()
                    .extract::<String>()
                    .unwrap();
                assert_eq!(actual, expected, "kind 应映射为 {expected}");
                assert!(
                    value.is_instance_of::<ProviderError>(),
                    "{expected} 应为 ProviderError 子类"
                );
            }
        });
    }

    /// 结构化字段透传：retry_after / received_chunks / finish_reason / code。
    #[test]
    fn provider_typed_carries_structured_fields() {
        Python::attach(|py| {
            // RateLimit -> retry_after (秒, float)
            let rate = agent_error_to_pyerr(provider_typed(
                "limited",
                ProviderErrorKind::RateLimit {
                    retry_after: Some(Duration::from_secs(45)),
                },
            ));
            let v = rate.value(py);
            let ra: Option<f64> = v.getattr("retry_after").unwrap().extract().unwrap();
            assert_eq!(ra, Some(45.0));

            // Overloaded -> retry_after 可为 None
            let ov_err = agent_error_to_pyerr(provider_typed(
                "busy",
                ProviderErrorKind::Overloaded { retry_after: None },
            ));
            let ov = ov_err.value(py);
            let ov_ra: Option<f64> = ov.getattr("retry_after").unwrap().extract().unwrap();
            assert!(ov_ra.is_none());

            // StreamIncomplete -> received_chunks + finish_reason
            let si_err = agent_error_to_pyerr(provider_typed(
                "cut",
                ProviderErrorKind::StreamIncomplete {
                    received_chunks: 7,
                    finish_reason: None,
                },
            ));
            let si = si_err.value(py);
            let chunks: u64 = si.getattr("received_chunks").unwrap().extract().unwrap();
            assert_eq!(chunks, 7);
            let fr: Option<String> = si.getattr("finish_reason").unwrap().extract().unwrap();
            assert!(fr.is_none());

            // Other { code } -> code
            let pc_err = agent_error_to_pyerr(provider_typed(
                "E429",
                ProviderErrorKind::Other {
                    code: "E429".into(),
                },
            ));
            let pc = pc_err.value(py);
            let code: String = pc.getattr("code").unwrap().extract().unwrap();
            assert_eq!(code, "E429");
        });
    }
}
