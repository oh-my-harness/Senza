//! EventStream + WaitForExternalEventTool 的 Python 包装。
//!
//! 用于 human-in-the-loop 场景：Python 侧创建 channel，将 tool 注册到 engine，
//! 通过 handle 在外部推送事件，阻塞等待的 tool 被唤醒后返回结果。

use std::sync::Arc;

use futures::future::BoxFuture;
use llm_harness_runtime::lifecycle::event::{Event, EventStream, WaitForExternalEventTool};
use llm_harness_runtime::lifecycle::task::TaskId;
use llm_harness_types::{ContentBlock, Tool};
use pyo3::prelude::*;
use tokio::sync::{Mutex, mpsc};

use crate::value_conv::pyobject_to_value;

/// mpsc-backed EventStream。
struct ChannelStream {
    rx: mpsc::Receiver<Event>,
}

impl EventStream for ChannelStream {
    fn next<'a>(&'a mut self) -> BoxFuture<'a, Option<Event>> {
        Box::pin(async { self.rx.recv().await })
    }
}

/// 持有 sender 侧，供 Python 外部推送事件。
#[pyclass(name = "EventStreamHandle")]
pub struct PyEventStreamHandle {
    tx: mpsc::Sender<Event>,
}

#[pymethods]
impl PyEventStreamHandle {
    fn submit(&self, content: &str, details: &Bound<'_, PyAny>) -> PyResult<()> {
        let details_val = pyobject_to_value(details)?;
        let event = Event {
            content: vec![ContentBlock::Text {
                text: content.to_string(),
            }],
            details: details_val,
        };
        self.tx
            .try_send(event)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("submit failed: {e}")))
    }
}

#[pyclass(name = "WaitForExternalEventTool")]
pub struct PyWaitForExternalEventTool {
    pub(crate) tool: Arc<dyn Tool>,
}

#[pymethods]
impl PyWaitForExternalEventTool {
    fn name(&self) -> &str {
        self.tool.name()
    }
    fn description(&self) -> &str {
        self.tool.description()
    }
}

/// Create a human-in-the-loop event channel.
///
/// Returns `(handle, wait_tool)`. Register `wait_tool` on the engine
/// or harness; when the LLM calls it, execution pauses until
/// `handle.submit(event_type, payload)` is called from another thread.
#[pyfunction]
pub fn create_event_channel(
    py: Python<'_>,
    task_id: &str,
) -> PyResult<(Py<PyEventStreamHandle>, Py<PyWaitForExternalEventTool>)> {
    let (tx, rx) = mpsc::channel::<Event>(16);
    let stream: Arc<Mutex<Box<dyn EventStream>>> =
        Arc::new(Mutex::new(Box::new(ChannelStream { rx })));
    let tid = TaskId(task_id.to_string());
    let descriptor = serde_json::json!({ "review_id": tid.0.clone() });
    let tool: Arc<dyn Tool> =
        Arc::new(WaitForExternalEventTool::new(stream, descriptor, None, tid));
    let handle = Py::new(py, PyEventStreamHandle { tx })?;
    let tool_wrapper = Py::new(py, PyWaitForExternalEventTool { tool })?;
    Ok((handle, tool_wrapper))
}
