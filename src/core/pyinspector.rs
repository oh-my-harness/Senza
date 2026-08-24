//! PyO3 wrapper for the Agent Inspector Web API.

use std::sync::Arc;

use llm_harness_agent::AgentHarness;
use llm_harness_inspector::Inspector as RustInspector;
use pyo3::prelude::*;

/// Python-facing Inspector handle. Holds the underlying `Inspector` server
/// lifecycle. Dropping this struct shuts down the HTTP server.
#[pyclass(name = "Inspector")]
pub struct PyInspector {
    inner: Option<RustInspector>,
}

#[pymethods]
impl PyInspector {
    /// The bound address, if the server is running.
    #[getter]
    fn bound_addr(&self) -> Option<String> {
        self.inner
            .as_ref()
            .and_then(|i| i.bound_addr())
            .map(|a| a.to_string())
    }

    /// Shut down the inspector server.
    fn shutdown(&mut self) {
        if let Some(inspector) = self.inner.take() {
            // Drop triggers shutdown via the Inspector's Drop impl
            let _ = inspector;
        }
    }

    fn __repr__(&self) -> String {
        match self.inner.as_ref().and_then(|i| i.bound_addr()) {
            Some(addr) => format!("Inspector(bound={})", addr),
            None => "Inspector(shutdown)".to_string(),
        }
    }
}

impl PyInspector {
    /// Mount a new inspector on the given harness + port.
    pub(crate) async fn mount(harness: Arc<AgentHarness>, port: u16) -> PyResult<Self> {
        let inspector = RustInspector::builder(harness)
            .port(port)
            .mount()
            .await
            .map_err(|e| {
                pyo3::exceptions::PyRuntimeError::new_err(format!("inspector mount failed: {e}"))
            })?;
        Ok(Self {
            inner: Some(inspector),
        })
    }
}
