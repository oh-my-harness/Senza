use std::sync::Arc;

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::core::pyplugin::PyPluginWrapper;

/// Opaque wrapper for `SessionRecallIndex`.
#[pyclass(name = "SessionRecallIndex")]
pub struct PySessionRecallIndex {
    pub index: Arc<dyn llm_harness_runtime_session_recall::SessionRecallIndex>,
}

/// Opaque wrapper for `SessionRepo`.
#[pyclass(name = "SessionRepo")]
pub struct PySessionRepo {
    pub repo: Arc<dyn llm_harness_agent::SessionRepo>,
}

/// Opaque wrapper for `SessionRecallKnowledgeSource`.
///
/// Use `.as_knowledge_source()` to obtain a `KnowledgeSource` for
/// registration in a `KnowledgeRegistry` via `create_knowledge_plugin`.
#[pyclass(name = "SessionRecallKnowledgeSource")]
pub struct PySessionRecallKnowledgeSource {
    pub source: Arc<llm_harness_runtime_session_recall::SessionRecallKnowledgeSource>,
}

#[pymethods]
impl PySessionRecallKnowledgeSource {
    /// Convert to a `KnowledgeSource` for registration in `KnowledgeRegistry`.
    #[pyo3(text_signature = "($self)")]
    fn as_knowledge_source<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<Bound<'py, super::pylocalsource::PyKnowledgeSource>> {
        let source: Arc<dyn llm_harness_runtime_knowledge::KnowledgeSource> = self.source.clone();
        Ok(Py::new(py, super::pylocalsource::PyKnowledgeSource { source })?.into_bound(py))
    }
}

/// Create an in-memory session recall index (non-persistent).
#[pyfunction]
#[pyo3(text_signature = "()")]
pub fn create_in_memory_session_recall_index<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, PySessionRecallIndex>> {
    let index: Arc<dyn llm_harness_runtime_session_recall::SessionRecallIndex> =
        Arc::new(llm_harness_runtime_session_recall::InMemorySessionRecallIndex::default());
    Ok(Py::new(py, PySessionRecallIndex { index })?.into_bound(py))
}

/// Create a SQLite-backed persistent session recall index.
#[pyfunction]
#[pyo3(text_signature = "(path)")]
pub fn create_sqlite_session_recall_index<'py>(
    py: Python<'py>,
    path: &str,
) -> PyResult<Bound<'py, PySessionRecallIndex>> {
    let index = llm_harness_runtime_session_recall::SqliteSessionRecallIndex::open(path)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let index: Arc<dyn llm_harness_runtime_session_recall::SessionRecallIndex> = Arc::new(index);
    Ok(Py::new(py, PySessionRecallIndex { index })?.into_bound(py))
}

/// Create an in-memory session repo (non-persistent).
#[pyfunction]
#[pyo3(text_signature = "()")]
pub fn create_in_memory_session_repo<'py>(py: Python<'py>) -> PyResult<Bound<'py, PySessionRepo>> {
    let repo: Arc<dyn llm_harness_agent::SessionRepo> =
        Arc::new(llm_harness_agent::InMemorySessionRepo::new());
    Ok(Py::new(py, PySessionRepo { repo })?.into_bound(py))
}

/// Create a file-system-backed `JsonlSessionRepo`.
///
/// Each session is stored in its own subdirectory: `{root_dir}/{session_id}/`.
/// Sessions persist across process restarts and can be loaded with
/// `HarnessBuilder.session_repo(repo, session_id=...)`.
#[pyfunction]
#[pyo3(text_signature = "(root_dir)")]
pub fn create_jsonl_session_repo<'py>(
    py: Python<'py>,
    root_dir: &str,
) -> PyResult<Bound<'py, PySessionRepo>> {
    let repo: Arc<dyn llm_harness_agent::SessionRepo> =
        Arc::new(llm_harness_agent::JsonlSessionRepo::new(root_dir));
    Ok(Py::new(py, PySessionRepo { repo })?.into_bound(py))
}

/// Create a `SessionRecallKnowledgeSource` from a session repo and recall index.
#[pyfunction]
#[pyo3(signature = (repo, index))]
#[pyo3(text_signature = "(repo, index)")]
pub fn create_session_recall_knowledge_source<'py>(
    py: Python<'py>,
    repo: &Bound<'_, PySessionRepo>,
    index: &Bound<'_, PySessionRecallIndex>,
) -> PyResult<Bound<'py, PySessionRecallKnowledgeSource>> {
    let repo: PyRef<'_, PySessionRepo> = repo.extract()?;
    let index: PyRef<'_, PySessionRecallIndex> = index.extract()?;

    let access_control = Arc::new(llm_harness_runtime_knowledge::KnowledgeAccessControl::new(
        Arc::new(llm_harness_runtime_knowledge::AllowAllAuthorizer),
    ));

    let service = Arc::new(
        llm_harness_runtime_session_recall::SessionRecallService::new(
            repo.repo.clone(),
            index.index.clone(),
            access_control,
        ),
    );
    let source =
        Arc::new(llm_harness_runtime_session_recall::SessionRecallKnowledgeSource::new(service));
    Ok(Py::new(py, PySessionRecallKnowledgeSource { source })?.into_bound(py))
}

/// Create a `HistoryRecallPlugin` that automatically injects recalled
/// conversation history into the model context.
///
/// Args:
///     source: A `SessionRecallKnowledgeSource` (from
///         `create_session_recall_knowledge_source`).
///     config: Optional dict with keys:
///         - `max_hits` (int)
///         - `max_bytes_per_hit` (int)
///         - `max_total_bytes` (int)
///         - `max_tokens_per_hit` (int)
///         - `max_total_tokens` (int)
///         - `timeout_ms` (int → Duration)
///         - `include_reference_labels` (bool)
#[pyfunction]
#[pyo3(signature = (source, config=None))]
#[pyo3(text_signature = "(source, config=None)")]
pub fn create_history_recall_plugin<'py>(
    py: Python<'py>,
    source: &Bound<'_, PySessionRecallKnowledgeSource>,
    config: Option<&Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let src: PyRef<'_, PySessionRecallKnowledgeSource> = source.extract()?;

    let mut plugin_config =
        llm_harness_runtime_session_recall::HistoryRecallPluginConfig::default();
    if let Some(cfg) = config {
        let mut budget = llm_harness_runtime_session_recall::SessionRecallBudget::default();
        if let Some(v) = cfg
            .get_item("max_hits")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            budget.max_hits = v;
        }
        if let Some(v) = cfg
            .get_item("max_bytes_per_hit")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            budget.max_bytes_per_hit = v;
        }
        if let Some(v) = cfg
            .get_item("max_total_bytes")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            budget.max_total_bytes = v;
        }
        if let Some(v) = cfg
            .get_item("max_tokens_per_hit")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            budget.max_tokens_per_hit = v;
        }
        if let Some(v) = cfg
            .get_item("max_total_tokens")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            budget.max_total_tokens = v;
        }
        plugin_config.budget = budget;
        if let Some(v) = cfg
            .get_item("timeout_ms")?
            .and_then(|v| v.extract::<u64>().ok())
        {
            plugin_config.timeout = std::time::Duration::from_millis(v);
        }
        if let Some(v) = cfg
            .get_item("include_reference_labels")?
            .and_then(|v| v.extract::<bool>().ok())
        {
            plugin_config.include_reference_labels = v;
        }
    }

    let plugin = llm_harness_runtime_session_recall::HistoryRecallPlugin::new(
        src.source.clone(),
        plugin_config,
    )
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let plugin: Arc<dyn llm_harness_agent::Plugin> = Arc::new(plugin);
    Ok(Py::new(py, PyPluginWrapper::new(plugin))?.into_bound(py))
}
