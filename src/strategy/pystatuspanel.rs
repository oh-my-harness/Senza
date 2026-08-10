use std::sync::Arc;

use pyo3::prelude::*;

use crate::core::pyplugin::PyPluginWrapper;

/// Create a StatusPanelPlugin that injects a status bar into the LLM context
/// and registers a todo_write tool for task tracking.
#[pyfunction]
pub fn create_status_panel_plugin<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::StatusPanelPlugin::with_defaults());
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
