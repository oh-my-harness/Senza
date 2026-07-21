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
