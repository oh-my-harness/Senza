use std::sync::Arc;

use pyo3::prelude::*;

/// Opaque wrapper for a knowledge source.
///
/// Instances are created by `create_local_knowledge_source` and consumed
/// by `create_knowledge_plugin`.
#[pyclass(name = "KnowledgeSource")]
pub struct PyKnowledgeSource {
    pub source: Arc<dyn llm_harness_knowledge::KnowledgeSource>,
}

/// Create a local document knowledge source that indexes Markdown and text
/// files from a directory.
///
/// Args:
///     path: Root directory containing documents.
///     source_id: Unique identifier for this knowledge source.
///     name: Display name (defaults to source_id).
///     description: Description (defaults to empty string).
///     domains: List of domain tags (defaults to ["general"]).
///     max_document_bytes: Max file size in bytes (default 1MB).
#[pyfunction]
#[pyo3(signature = (path, source_id, name=None, description=None, domains=None, max_document_bytes=1048576))]
pub fn create_local_knowledge_source<'py>(
    py: Python<'py>,
    path: &str,
    source_id: &str,
    name: Option<String>,
    description: Option<String>,
    domains: Option<Vec<String>>,
    max_document_bytes: usize,
) -> PyResult<Bound<'py, PyKnowledgeSource>> {
    let rt = crate::core::pyagent::runtime(py);
    let config = llm_harness_knowledge_local::LocalDocumentSourceConfig {
        source_id: source_id.to_string(),
        name: name.unwrap_or_else(|| source_id.to_string()),
        description: description.unwrap_or_default(),
        domains: domains.unwrap_or_else(|| vec!["general".to_string()]),
        roots: vec![llm_harness_knowledge_local::DocumentRootConfig {
            id: "root".to_string(),
            path: std::path::PathBuf::from(path),
        }],
        source_secret: (0..32).map(|i| i as u8).collect(),
        max_document_bytes,
    };
    let file_system = Arc::new(llm_harness_knowledge_local::OsDocumentFileSystem);
    let parsers = llm_harness_knowledge_local::DocumentParserRegistry::default();
    let access_control = Arc::new(llm_harness_knowledge::KnowledgeAccessControl::new(
        Arc::new(llm_harness_knowledge::AllowAllAuthorizer),
    ));

    let source = crate::shared::pyerror::detach_catch_panic_result(py, || {
        rt.block_on(async move {
            llm_harness_knowledge_local::LocalDocumentSource::create(
                config,
                file_system,
                parsers,
                access_control,
            )
            .await
        })
    })?;

    let source: Arc<dyn llm_harness_knowledge::KnowledgeSource> = Arc::new(source);
    Ok(Py::new(py, PyKnowledgeSource { source })?.into_bound(py))
}
