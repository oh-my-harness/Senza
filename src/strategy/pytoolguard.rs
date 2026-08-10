use std::sync::Arc;

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::core::pyplugin::PyPluginWrapper;
use crate::runtime::pyworkflow::PyEnvWrapper;

/// Create a ToolOutputGuardPlugin that truncates excessive tool output
/// as a fallback safety net.
///
/// Args:
///     env: ExecutionEnv (from create_os_env())
///     config: Optional dict with "max_lines", "max_bytes", "head_lines",
///             "tail_lines", "skip_tools" (list[str])
#[pyfunction]
#[pyo3(signature = (env, config=None))]
pub fn create_tool_output_guard_plugin<'py>(
    py: Python<'py>,
    env: &Bound<'_, PyAny>,
    config: Option<&Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let env_wrapper: PyRef<'_, PyEnvWrapper> = env.extract()?;
    let env_arc = env_wrapper.env.clone();

    let plugin: Arc<dyn llm_harness_agent::Plugin> = if let Some(cfg) = config {
        let mut tc = llm_harness_strategy::ToolOutputGuardConfig::default();
        if let Some(v) = cfg
            .get_item("max_lines")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            tc.max_lines = v;
        }
        if let Some(v) = cfg
            .get_item("max_bytes")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            tc.max_bytes = v;
        }
        if let Some(v) = cfg
            .get_item("head_lines")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            tc.head_lines = v;
        }
        if let Some(v) = cfg
            .get_item("tail_lines")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            tc.tail_lines = v;
        }
        if let Some(v) = cfg
            .get_item("skip_tools")?
            .and_then(|v| v.extract::<Vec<String>>().ok())
        {
            tc.skip_tools = v.into_iter().collect();
        }
        Arc::new(llm_harness_strategy::ToolOutputGuardPlugin::with_config(
            env_arc, tc,
        ))
    } else {
        Arc::new(llm_harness_strategy::ToolOutputGuardPlugin::new(env_arc))
    };
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
