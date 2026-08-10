use std::sync::Arc;

use pyo3::prelude::*;

use crate::core::pyplugin::PyPluginWrapper;

/// Create an AuditPlugin that logs tool calls to a JSONL file with
/// SHA-256 hash-chain integrity.
///
/// Args:
///     sink_path: Path to the JSONL audit log file.
///     trace_id: Optional trace ID for correlation.
///     task_id: Optional task ID for correlation.
#[pyfunction]
#[pyo3(signature = (sink_path, trace_id=None, task_id=None))]
pub fn create_audit_plugin<'py>(
    py: Python<'py>,
    sink_path: &str,
    trace_id: Option<String>,
    task_id: Option<String>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let sink = Arc::new(llm_harness_runtime_audit_jsonl::JsonlAuditSink::new(
        sink_path,
    ));
    let mut plugin = llm_harness_strategy::AuditPlugin::new(sink);
    if let Some(tid) = trace_id {
        plugin = plugin.with_trace_id(tid);
    }
    if let Some(tid) = task_id {
        plugin = plugin.with_task_id(tid);
    }
    let plugin: Arc<dyn llm_harness_agent::Plugin> = Arc::new(plugin);
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
