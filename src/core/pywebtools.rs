//! PyO3 wrappers for web/code tools (`web_search`, `web_fetch`, `code_exec`).
//!
//! Exposes `create_web_search_tool`, `create_web_fetch_tool`,
//! `create_web_tools_plugin`, and `create_code_exec_tool` as `#[pyfunction]`s,
//! plus the opaque `NativeTool` pyclass wrapping any `Arc<dyn Tool>`.

use std::sync::Arc;

use llm_harness_tools::{
    CodeExecTool, WebFetchTool, WebSearchConfig, WebSearchTool, WebToolsPlugin,
};
use llm_harness_types::Tool;
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::core::pyplugin::PyPluginWrapper;

/// Parse a Python dict into a `WebSearchConfig`, falling back to `default()`.
///
/// Recognised keys: `provider`, `base_url`, `api_key`, `max_results`,
/// `fetch_timeout_secs`, `max_fetch_chars`.
fn parse_config(config: Option<&Bound<'_, PyDict>>) -> PyResult<WebSearchConfig> {
    let Some(dict) = config else {
        return Ok(WebSearchConfig::default());
    };
    let mut cfg = WebSearchConfig::default();
    if let Some(v) = dict
        .get_item("provider")?
        .and_then(|v| v.extract::<String>().ok())
    {
        cfg.provider = v;
    }
    if let Some(v) = dict
        .get_item("base_url")?
        .and_then(|v| v.extract::<String>().ok())
    {
        cfg.base_url = v;
    }
    if let Some(v) = dict
        .get_item("api_key")?
        .and_then(|v| v.extract::<String>().ok())
    {
        cfg.api_key = Some(v);
    }
    if let Some(v) = dict
        .get_item("max_results")?
        .and_then(|v| v.extract::<usize>().ok())
    {
        cfg.max_results = v;
    }
    if let Some(v) = dict
        .get_item("fetch_timeout_secs")?
        .and_then(|v| v.extract::<u64>().ok())
    {
        cfg.fetch_timeout_secs = v;
    }
    if let Some(v) = dict
        .get_item("max_fetch_chars")?
        .and_then(|v| v.extract::<usize>().ok())
    {
        cfg.max_fetch_chars = v;
    }
    Ok(cfg)
}

/// Opaque wrapper for a Rust-native `Tool`.
///
/// Exposes `name` and `description` as read-only properties. The tool itself
/// is not callable from Python — it is meant to be registered on a
/// `HarnessBuilder` via `.tool(native_tool)`.
#[pyclass(name = "NativeTool")]
pub struct PyNativeTool {
    pub(crate) tool: Arc<dyn Tool>,
}

#[pymethods]
impl PyNativeTool {
    #[getter]
    fn name(&self) -> &str {
        self.tool.name()
    }

    #[getter]
    fn description(&self) -> &str {
        self.tool.description()
    }

    fn __repr__(&self) -> String {
        format!("NativeTool(name={:?})", self.tool.name())
    }
}

/// Create a `web_search` tool backed by the given config (or defaults).
#[pyfunction]
#[pyo3(signature = (config=None))]
pub fn create_web_search_tool<'py>(
    py: Python<'py>,
    config: Option<Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyNativeTool>> {
    let cfg = parse_config(config.as_ref())?;
    let tool: Arc<dyn Tool> = Arc::new(WebSearchTool::with_config(cfg));
    Py::new(py, PyNativeTool { tool }).map(|p| p.into_bound(py))
}

/// Create a `web_fetch` tool backed by the given config (or defaults).
#[pyfunction]
#[pyo3(signature = (config=None))]
pub fn create_web_fetch_tool<'py>(
    py: Python<'py>,
    config: Option<Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyNativeTool>> {
    let cfg = parse_config(config.as_ref())?;
    let tool: Arc<dyn Tool> = Arc::new(WebFetchTool::with_config(cfg));
    Py::new(py, PyNativeTool { tool }).map(|p| p.into_bound(py))
}

/// Create a `WebToolsPlugin` aggregating `web_search` + `web_fetch`.
#[pyfunction]
#[pyo3(signature = (config=None))]
pub fn create_web_tools_plugin<'py>(
    py: Python<'py>,
    config: Option<Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let cfg = parse_config(config.as_ref())?;
    let plugin: Arc<dyn llm_harness_agent::Plugin> = Arc::new(WebToolsPlugin::new(cfg));
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}

/// Create a `code_exec` tool that runs Python/bash/JavaScript in a temp dir.
///
/// If `timeout_secs` is given, the tool kills the subprocess after that many
/// seconds; otherwise it defaults to 30 s.
#[pyfunction]
#[pyo3(signature = (timeout_secs=None))]
pub fn create_code_exec_tool<'py>(
    py: Python<'py>,
    timeout_secs: Option<u64>,
) -> PyResult<Bound<'py, PyNativeTool>> {
    if let Some(0) = timeout_secs {
        return Err(PyTypeError::new_err("timeout_secs must be > 0"));
    }
    let tool: Arc<dyn Tool> = match timeout_secs {
        Some(secs) => Arc::new(CodeExecTool::with_timeout(std::time::Duration::from_secs(
            secs,
        ))),
        None => Arc::new(CodeExecTool::new()),
    };
    Py::new(py, PyNativeTool { tool }).map(|p| p.into_bound(py))
}
