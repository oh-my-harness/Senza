use pyo3::prelude::*;
use pyo3::types::PyTuple;

/// Create a context-aware compaction prompt spec that preserves
/// task context, decisions, and file operations during summarization.
///
/// Returns: (system_prompt, user_template) tuple. Pass these to
/// builder.compaction_prompt(system_prompt, user_template).
#[pyfunction]
pub fn create_context_aware_compaction_prompt<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, PyTuple>> {
    let spec = llm_harness_strategy::context_aware_prompt_spec();
    let system_prompt = spec.system_prompt().to_string();
    let user_template = spec.user_template().to_string();
    PyTuple::new(py, vec![system_prompt, user_template])
}
