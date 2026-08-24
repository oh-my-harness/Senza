use std::sync::Arc;

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::core::pyplugin::PyPluginWrapper;
use crate::knowledge::pylocalsource::PyKnowledgeSource;

/// Create a KnowledgePlugin that registers knowledge_search and knowledge_read
/// tools, enabling the LLM to search and read from registered knowledge sources.
///
/// Args:
///     sources: List of KnowledgeSource objects (from create_local_knowledge_source).
///     config: Optional dict with "max_search_results" (int, default 10),
///             "max_read_bytes" (int, default 32768).
#[pyfunction]
#[pyo3(signature = (sources, config=None))]
pub fn create_knowledge_plugin<'py>(
    py: Python<'py>,
    sources: Vec<Bound<'py, PyKnowledgeSource>>,
    config: Option<&Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    // Build access control with AllowAllAuthorizer (trusted single-user Python SDK)
    let access_control = Arc::new(llm_harness_knowledge::KnowledgeAccessControl::new(
        Arc::new(llm_harness_knowledge::AllowAllAuthorizer),
    ));

    // Extract Arc<dyn KnowledgeSource> from each PyKnowledgeSource and build registry
    let mut builder = llm_harness_knowledge::KnowledgeRegistry::builder(access_control);
    for src in &sources {
        let borrowed = src.borrow();
        builder = builder.source(borrowed.source.clone());
    }

    // Build tool config from optional dict
    let mut tools = llm_harness_knowledge::KnowledgeToolConfig::default();
    if let Some(cfg) = config {
        if let Some(v) = cfg
            .get_item("max_search_results")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            tools.max_search_results = v;
        }
        if let Some(v) = cfg
            .get_item("max_read_bytes")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            tools.max_read_bytes = v;
        }
    }

    let plugin_config = llm_harness_knowledge::KnowledgePluginConfig {
        tools,
        citation_policy: llm_harness_knowledge::KnowledgeCitationPolicy::default(),
    };

    // Build registry
    let registry = Arc::new(
        builder
            .build()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?,
    );

    // Create EvidenceAuthority with a deterministic secret
    let secret: Vec<u8> = (0..32).map(|i| i as u8).collect();
    let provider_id = llm_harness_knowledge::EvidenceProviderId("local".to_string());
    let authority = Arc::new(
        llm_harness_knowledge::EvidenceAuthority::new(secret, [provider_id.clone()])
            .map_err(pyo3::exceptions::PyValueError::new_err)?,
    );

    // Create KnowledgePlugin
    let plugin = llm_harness_knowledge::KnowledgePlugin::new(
        registry,
        authority,
        provider_id,
        plugin_config,
    )
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let plugin: Arc<dyn llm_harness_agent::Plugin> = Arc::new(plugin);
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
