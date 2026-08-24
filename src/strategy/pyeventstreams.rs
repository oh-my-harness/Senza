use std::sync::{Arc, Mutex};

use chrono::Utc;
use pyo3::prelude::*;
use pyo3::types::PyTuple;
use tokio::sync::Mutex as TokioMutex;

use llm_harness_types::Tool;
use llm_harness_workflow::lifecycle::event::WaitForExternalEventTool;
use llm_harness_workflow::lifecycle::task::TaskId;

use crate::shared::value_conv::pyobject_to_value;

// ── Webhook stream (existing) ────────────────────────────────────────────

/// Opaque wrapper for WebhookChannel.
///
/// The channel is the sender side of a webhook event stream. External
/// systems call `push(payload)` to inject events that the EventStream
/// consumer will receive.
#[pyclass(name = "WebhookChannel")]
pub struct PyWebhookChannel {
    pub channel: llm_harness_strategy::WebhookChannel,
}

#[pymethods]
impl PyWebhookChannel {
    /// Push a payload into the webhook stream.
    ///
    /// The payload is converted to JSON and delivered to the EventStream
    /// consumer. Accepts dicts, lists, strings, numbers, bools, and None.
    fn push(&self, py: Python<'_>, payload: &Bound<'_, PyAny>) -> PyResult<()> {
        let value = pyobject_to_value(payload)?;
        let channel = self.channel.clone();
        let rt = crate::core::pyagent::runtime(py);
        crate::shared::pyerror::detach_catch_panic_result(py, move || {
            rt.block_on(async move {
                channel
                    .push(value)
                    .await
                    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
            })
        })
    }
}

/// Opaque wrapper for a webhook event stream consumer.
///
/// This holds the `Box<dyn EventStream>` behind a `Mutex` so that the
/// `PyEventStream` struct is `Send + Sync` (required by `#[pyclass]`).
/// `EventStream` itself is only `Send`, not `Sync`.
#[pyclass(name = "EventStream")]
pub struct PyEventStream {
    pub stream: Mutex<Option<Box<dyn llm_harness_types::EventStream>>>,
}

/// Create a webhook event stream pair: a WebhookChannel for external systems
/// to push events, and an EventStream for the workflow engine to consume.
///
/// Args:
///     buffer: Channel capacity (number of pending events). 64 is reasonable.
///
/// Returns: (WebhookChannel, EventStream)
#[pyfunction]
pub fn create_webhook_stream<'py>(py: Python<'py>, buffer: usize) -> PyResult<Bound<'py, PyTuple>> {
    let (channel, stream) = llm_harness_strategy::WebhookStream::new(buffer);
    let py_channel = Py::new(py, PyWebhookChannel { channel })?;
    let py_stream = Py::new(
        py,
        PyEventStream {
            stream: Mutex::new(Some(stream)),
        },
    )?;
    PyTuple::new(py, vec![py_channel.into_any(), py_stream.into_any()])
}

// ── Timer stream ─────────────────────────────────────────────────────────

/// Create a one-shot timer event stream that fires after `delay_ms` milliseconds.
///
/// Returns: (EventStream, WaitForExternalEventTool)
/// Register the tool on a harness; when the LLM calls it, execution pauses
/// until the timer fires.
#[pyfunction]
pub fn create_timer_stream<'py>(
    py: Python<'py>,
    delay_ms: u64,
    label: &str,
    task_id: &str,
) -> PyResult<Bound<'py, PyTuple>> {
    let fire_at = Utc::now() + chrono::Duration::milliseconds(delay_ms as i64);
    let stream: Box<dyn llm_harness_types::EventStream> = Box::new(
        llm_harness_strategy::TimerStream::once(fire_at, label.to_string()),
    );
    let stream_arc: Arc<TokioMutex<Box<dyn llm_harness_types::EventStream>>> =
        Arc::new(TokioMutex::new(stream));
    let tid = TaskId(task_id.to_string());
    let descriptor = serde_json::json!({ "type": "timer", "label": label });
    let tool: Arc<dyn Tool> = Arc::new(WaitForExternalEventTool::new(
        stream_arc, descriptor, None, tid,
    ));
    let py_tool = Py::new(
        py,
        crate::core::pyeventstream::PyWaitForExternalEventTool { tool },
    )?;
    PyTuple::new(py, vec![py_tool.into_any()])
}

// ── Heartbeat stream ─────────────────────────────────────────────────────

/// Opaque handle for a heartbeat stream. Call `tick()` to reset the watchdog.
#[pyclass(name = "HeartbeatHandle")]
pub struct PyHeartbeatHandle {
    handle: llm_harness_strategy::HeartbeatHandle,
}

#[pymethods]
impl PyHeartbeatHandle {
    /// Reset the watchdog — call on every meaningful activity.
    fn tick(&self) {
        self.handle.tick();
    }
}

/// Create a heartbeat (activity-driven watchdog) event stream.
///
/// When `tick()` is never called on the returned handle, the heartbeat fires
/// after `timeout_ms`. If the LLM calls the tool, it blocks until the heartbeat fires.
///
/// Returns: (HeartbeatHandle, WaitForExternalEventTool)
#[pyfunction]
pub fn create_heartbeat_stream<'py>(
    py: Python<'py>,
    timeout_ms: u64,
    label: &str,
    task_id: &str,
) -> PyResult<Bound<'py, PyTuple>> {
    let (handle, stream) = llm_harness_strategy::HeartbeatStream::new(
        std::time::Duration::from_millis(timeout_ms),
        label.to_string(),
    );
    let stream_arc: Arc<TokioMutex<Box<dyn llm_harness_types::EventStream>>> =
        Arc::new(TokioMutex::new(stream));
    let tid = TaskId(task_id.to_string());
    let descriptor = serde_json::json!({ "type": "heartbeat", "label": label });
    let tool: Arc<dyn Tool> = Arc::new(WaitForExternalEventTool::new(
        stream_arc, descriptor, None, tid,
    ));
    let py_handle = Py::new(py, PyHeartbeatHandle { handle })?;
    let py_tool = Py::new(
        py,
        crate::core::pyeventstream::PyWaitForExternalEventTool { tool },
    )?;
    PyTuple::new(py, vec![py_handle.into_any(), py_tool.into_any()])
}

// ── Shell monitor stream ─────────────────────────────────────────────────

/// Opaque handle for a shell monitor stream. Call `kill()` to terminate the monitored process.
#[pyclass(name = "ShellMonitorHandle")]
pub struct PyShellMonitorHandle {
    handle: llm_harness_strategy::ShellMonitorHandle,
}

#[pymethods]
impl PyShellMonitorHandle {
    /// Kill the monitored process.
    fn kill(&self) {
        self.handle.kill();
    }
}

/// Create a shell monitor event stream that captures stdout from a shell command.
///
/// When the LLM calls the tool, it blocks until the command produces output.
///
/// Args:
///     command: Shell command to execute.
///     cwd: Working directory (or None for current dir).
///     label: Label for the event stream.
///     task_id: Task identifier for persistence.
///
/// Returns: (ShellMonitorHandle, WaitForExternalEventTool)
#[pyfunction]
pub fn create_shell_monitor_stream<'py>(
    py: Python<'py>,
    command: &str,
    cwd: Option<&str>,
    label: &str,
    task_id: &str,
) -> PyResult<Bound<'py, PyTuple>> {
    let cwd_path = cwd.map(std::path::PathBuf::from);
    let (handle, stream) = llm_harness_strategy::ShellMonitorStream::new(
        command,
        cwd_path.as_deref(),
        Vec::new(),
        label.to_string(),
        llm_harness_strategy::ShellMonitorConfig::default(),
    )
    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("shell monitor failed: {e}")))?;
    let stream_arc: Arc<TokioMutex<Box<dyn llm_harness_types::EventStream>>> =
        Arc::new(TokioMutex::new(stream));
    let tid = TaskId(task_id.to_string());
    let descriptor = serde_json::json!({ "type": "shell_monitor", "label": label });
    let tool: Arc<dyn Tool> = Arc::new(WaitForExternalEventTool::new(
        stream_arc, descriptor, None, tid,
    ));
    let py_handle = Py::new(py, PyShellMonitorHandle { handle })?;
    let py_tool = Py::new(
        py,
        crate::core::pyeventstream::PyWaitForExternalEventTool { tool },
    )?;
    PyTuple::new(py, vec![py_handle.into_any(), py_tool.into_any()])
}
