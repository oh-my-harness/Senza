//! Panic 隔离：把 Rust panic 转为 Python 自定义异常 `RustPanicError`。
//!
//! 所有 `py.detach(block_on(...))` 调用应通过 `detach_catch_panic` /
//! `detach_catch_panic_result` 包裹，确保 Rust 侧的 panic 不会导致
//! Python 进程崩溃（SIGSEGV / Core Dump），而是映射为可捕获的
//! `senza.RustPanicError`。

use pyo3::exceptions::PyRuntimeError;
use pyo3::marker::Ungil;
use pyo3::prelude::*;

pyo3::create_exception!(senza, RustPanicError, PyRuntimeError);

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

/// `py.detach(f)` 的 panic-safe 版本（闭包返回 `Result<T, E>`）。
///
/// 在 `catch_unwind` 中执行闭包 `f`（已释放 GIL）。若 `f` 返回 `Ok(T)`，
/// 透传；`Err(E)` 转为 `PyRuntimeError`；panic 转为 `RustPanicError`。
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
///
/// 在 `catch_unwind` 中执行闭包 `f`（已释放 GIL）。把 panic 转为
/// `RustPanicError`，正常返回值透传。
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
///
/// future 必须返回 `PyResult<R>`——即调用者在 future 内部自行将 Rust 错误
/// 映射为 `PyErr`（如 `PyRuntimeError` 或 `workflow_error_to_pyerr`）。
/// 这样本函数无需关心具体的错误类型，只负责：
/// - 定期检查 Python 信号（Ctrl+C → `KeyboardInterrupt`）
/// - 用 `catch_unwind` 把 Rust panic 转为 `RustPanicError`
/// - 释放 GIL（`py.detach`）
///
/// 每 `signal_check_interval_ms` 毫秒通过 `Python::attach` + `py.check_signals()`
/// 检查是否有挂起的信号。
pub fn block_on_with_signal_check<R, F>(
    py: Python<'_>,
    rt: &'static tokio::runtime::Runtime,
    future: F,
    signal_check_interval_ms: u64,
) -> PyResult<R>
where
    R: Send + Ungil + 'static,
    F: std::future::Future<Output = PyResult<R>> + Send + 'static,
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
///
/// 与 `detach_catch_panic_result` 不同，闭包直接返回 `PyResult<R>`，
/// 因此闭包内部可以通过 `Python::attach(|py| py.check_signals())`
/// 检查信号并在收到 SIGINT 时返回 `KeyboardInterrupt`，而不会被
/// `to_string()` 二次包装。
///
/// 用于循环型阻塞方法（如 `collect_until_settled`），在循环体内
/// 逐次检查信号。
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
