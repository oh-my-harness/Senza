use std::sync::Arc;

use pyo3::prelude::*;

use crate::core::pyplugin::PyPluginWrapper;

/// Builder for MemoryDefensePlugin with fluent configuration.
///
/// The underlying Rust builder consumes self on each method, so we store
/// it in an `Option` and `take()` + replace on every call.
#[pyclass(name = "MemoryDefensePluginBuilder")]
pub struct PyMemoryDefensePluginBuilder {
    builder: Option<llm_harness_strategy::MemoryDefensePluginBuilder>,
}

#[pymethods]
impl PyMemoryDefensePluginBuilder {
    #[new]
    fn new() -> Self {
        Self {
            builder: Some(llm_harness_strategy::MemoryDefensePlugin::builder()),
        }
    }

    /// Add an extra memory file name to protect (e.g. "CLAUDE.md").
    fn extra_file<'a>(mut slf: PyRefMut<'a, Self>, name: &str) -> PyRefMut<'a, Self> {
        let b = slf.builder.take().unwrap_or_default();
        slf.builder = Some(b.extra_file(name));
        slf
    }

    /// Add multiple extra memory file names.
    fn extra_files<'a>(mut slf: PyRefMut<'a, Self>, names: Vec<String>) -> PyRefMut<'a, Self> {
        let b = slf.builder.take().unwrap_or_default();
        let refs: Vec<&str> = names.iter().map(|s| s.as_str()).collect();
        slf.builder = Some(b.extra_files(&refs));
        slf
    }

    /// Build the MemoryDefensePlugin.
    fn build<'a>(&mut self, py: Python<'a>) -> PyResult<Bound<'a, PyPluginWrapper>> {
        let builder = self
            .builder
            .take()
            .unwrap_or_else(llm_harness_strategy::MemoryDefensePlugin::builder);
        let plugin: Arc<dyn llm_harness_agent::Plugin> = Arc::new(builder.build());
        Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
    }
}

/// Create a MemoryDefensePlugin with default settings.
#[pyfunction]
pub fn create_memory_defense_plugin<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::MemoryDefensePlugin::builder().build());
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
