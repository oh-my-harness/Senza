use std::sync::Arc;

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::core::pyplugin::PyPluginWrapper;
use crate::runtime::pyworkflow::PyEnvWrapper;

/// Create a ProjectInstructionPlugin that auto-injects project instruction
/// files (CLAUDE.md, AGENTS.md, .cursorrules, SOUL.md) into the system prompt.
///
/// Args:
///     env: ExecutionEnv (from create_os_env())
///     config: Optional dict with "file_names" (list[str]), "max_depth" (int|None),
///             "max_bytes" (int|None)
#[pyfunction]
#[pyo3(signature = (env, config=None))]
pub fn create_project_instruction_plugin<'py>(
    py: Python<'py>,
    env: &Bound<'_, PyAny>,
    config: Option<&Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let env_wrapper: PyRef<'_, PyEnvWrapper> = env.extract()?;
    let env_arc = env_wrapper.env.clone();

    let plugin: Arc<dyn llm_harness_agent::Plugin> = if let Some(cfg) = config {
        let mut pic = llm_harness_strategy::ProjectInstructionConfig::default();
        if let Some(names) = cfg
            .get_item("file_names")?
            .and_then(|v| v.extract::<Vec<String>>().ok())
        {
            pic.file_names = names;
        }
        if let Some(depth) = cfg
            .get_item("max_depth")?
            .and_then(|v| v.extract::<Option<usize>>().ok())
        {
            pic.max_depth = depth;
        }
        if let Some(bytes) = cfg
            .get_item("max_bytes")?
            .and_then(|v| v.extract::<Option<u64>>().ok())
        {
            pic.max_bytes = bytes;
        }
        Arc::new(llm_harness_strategy::ProjectInstructionPlugin::new(env_arc).with_config(pic))
    } else {
        Arc::new(llm_harness_strategy::ProjectInstructionPlugin::new(env_arc))
    };
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
