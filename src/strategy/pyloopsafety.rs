use std::sync::Arc;

use pyo3::prelude::*;

use crate::core::pyplugin::PyPluginWrapper;

/// Create a LoopSafetyPlugin that guards against death spirals, repetition,
/// failure cascades, truncation loops, and excessive turns.
///
/// Args:
///     config: Optional dict. If None or omitted, enables all guards with
///             defaults. If a dict with `{"enabled": False}`, creates a
///             disabled (no-op) plugin.
#[pyfunction]
#[pyo3(signature = (config=None))]
pub fn create_loop_safety_plugin<'py>(
    py: Python<'py>,
    config: Option<&Bound<'_, PyAny>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let cfg = if let Some(c) = config {
        let enabled: bool = c.getattr("get")?.call1(("enabled", true))?.extract()?;
        if enabled {
            llm_harness_strategy::LoopSafetyConfig::default_enabled()
        } else {
            llm_harness_strategy::LoopSafetyConfig::disabled()
        }
    } else {
        llm_harness_strategy::LoopSafetyConfig::default_enabled()
    };
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::LoopSafetyPlugin::new(cfg));
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
