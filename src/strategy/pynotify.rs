use std::sync::Arc;

use pyo3::prelude::*;

use crate::core::pyplugin::PyPluginWrapper;

/// Create a NotifyPlugin that registers a notify_user tool, allowing the
/// LLM to proactively send notifications to the user.
///
/// Note: The NotificationChannel must be injected separately via
/// RunExtensions on the Rust side. This plugin only registers the tool.
#[pyfunction]
pub fn create_notify_plugin<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::NotifyPlugin::new());
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
