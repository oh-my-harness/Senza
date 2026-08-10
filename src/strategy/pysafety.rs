use std::sync::Arc;

use pyo3::prelude::*;

use crate::core::pyplugin::PyPluginWrapper;

/// Create a SafetyDefaultsPlugin that enforces bash command blacklist
/// and path traversal protection.
///
/// Returns a Plugin that can be installed on a HarnessBuilder via `.plugin()`.
#[pyfunction]
pub fn create_safety_defaults_plugin<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::SafetyDefaultsPlugin::new());
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
