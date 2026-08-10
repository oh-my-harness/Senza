use std::sync::Mutex;

use pyo3::prelude::*;
use pyo3::types::PyTuple;

use crate::shared::value_conv::pyobject_to_value;

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
