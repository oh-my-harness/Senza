//! Event-loop bridge for async Python callbacks (issue #13).
//!
//! ## Problem
//!
//! `async def` tool/hook callbacks are executed on `spawn_blocking`
//! threads.  Previously each call used `asyncio.run(coro)`, which creates
//! a **fresh** event loop.  If the coroutine uses resources tied to the
//! user's main loop (e.g. `aiohttp.ClientSession`, `asyncio.Lock`,
//! `asyncio.Queue`), they break with "Future attached to a different loop".
//!
//! ## Solution
//!
//! Provide [`set_event_loop`] so users (or the async streaming API, issue #11)
//! can register their running event loop.  [`run_coro`] then uses
//! `asyncio.run_coroutine_threadsafe(coro, loop).result()` to schedule the
//! coroutine back onto the user's loop.
//!
//! If no loop is registered, or the registered loop is not running,
//! we fall back to `asyncio.run(coro)` — the original behaviour — which is
//! safe for purely synchronous usage where no main loop exists.

use std::sync::Mutex;

use pyo3::prelude::*;
use pyo3::types::PyModule;

static EVENT_LOOP: Mutex<Option<Py<PyAny>>> = Mutex::new(None);

/// Register the user's event loop for async callback scheduling.
///
/// Call this from the thread that owns the loop, e.g.:
/// ```python
/// import asyncio, senza
/// loop = asyncio.new_event_loop()
/// senza.set_event_loop(loop)
/// threading.Thread(target=loop.run_forever, daemon=True).start()
/// ```
pub fn set_event_loop(loop_obj: Py<PyAny>) {
    *EVENT_LOOP.lock().unwrap() = Some(loop_obj);
}

/// Clear the registered event loop (mainly for testing).
#[allow(dead_code)]
pub fn clear_event_loop() {
    *EVENT_LOOP.lock().unwrap() = None;
}

/// Execute a Python coroutine, scheduling it on the user's main event
/// loop when possible.
///
/// - If a loop was registered via [`set_event_loop`] **and** it is running,
///   use `asyncio.run_coroutine_threadsafe(coro, loop).result()`.
/// - Otherwise, fall back to `asyncio.run(coro)` (creates a temporary loop).
pub fn run_coro<'py>(py: Python<'py>, coro: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let asyncio = PyModule::import(py, "asyncio")?;
    let guard = EVENT_LOOP.lock().unwrap();
    if let Some(loop_ref) = guard.as_ref() {
        let is_running: bool = loop_ref
            .bind(py)
            .getattr("is_running")?
            .call0()?
            .extract()?;
        if is_running {
            let future =
                asyncio.call_method1("run_coroutine_threadsafe", (coro, loop_ref.bind(py)))?;
            // Release the lock before blocking on .result() to avoid
            // holding it while the coroutine runs.
            drop(guard);
            return future.call_method0("result");
        }
    }
    drop(guard);
    // Fallback: create a temporary event loop.
    asyncio.call_method1("run", (coro,))
}
