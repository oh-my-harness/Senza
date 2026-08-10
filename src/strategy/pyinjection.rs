use std::sync::Arc;

use pyo3::prelude::*;

use crate::core::pyplugin::PyPluginWrapper;

/// Create an InjectionFilterPlugin that detects and filters prompt injection
/// patterns in tool outputs.
///
/// Args:
///     patterns: Optional list of regex pattern strings. Each pattern is
///               treated as "remove" (matched text is stripped) and appended
///               on top of the built-in default patterns. If None, uses
///               the default patterns only.
#[pyfunction]
#[pyo3(signature = (patterns=None))]
pub fn create_injection_filter_plugin<'py>(
    py: Python<'py>,
    patterns: Option<Vec<String>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let hook = if let Some(pats) = patterns {
        let parsed: Vec<llm_harness_strategy::InjectionPattern> = pats
            .iter()
            .map(|p| llm_harness_strategy::InjectionPattern::remove(p))
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        llm_harness_strategy::InjectionFilterHook::with_extra(parsed)
    } else {
        llm_harness_strategy::InjectionFilterHook::default()
    };
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_strategy::InjectionFilterPlugin::new(hook));
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
