use std::sync::Arc;

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::core::pyplugin::PyPluginWrapper;

/// Create a SourceTagPlugin that wraps external content tool results in
/// `<external_content source="...">` XML tags.
///
/// Args:
///     entries: List of dicts with "tool" (tool name) and "label" (source label) keys.
#[pyfunction]
pub fn create_source_tag_plugin<'py>(
    py: Python<'py>,
    entries: Vec<Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let mut parsed = Vec::with_capacity(entries.len());
    for entry in &entries {
        let tool: String = entry
            .get_item("tool")?
            .ok_or_else(|| {
                pyo3::exceptions::PyValueError::new_err("Each entry must have a 'tool' key")
            })?
            .extract()?;
        let label: String = entry
            .get_item("label")?
            .ok_or_else(|| {
                pyo3::exceptions::PyValueError::new_err("Each entry must have a 'label' key")
            })?
            .extract()?;
        parsed.push(llm_harness_strategy::SourceTagEntry { tool, label });
    }
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::SourceTagPlugin::new(parsed));
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
