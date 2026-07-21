//! PyO3 bindings for the session-viewer crate.
//!
//! Exposes `read_sessions(dir)` which returns a Python dict matching the
//! `ViewerData` JSON shape. The Python `senza.viewer` module uses this to
//! avoid duplicating the JSONL parsing logic in Python.

use pyo3::prelude::*;
use pyo3::types::PyString;

use crate::value_conv::value_to_pyobject;

/// Read all sessions under `dir` and return a Python dict.
///
/// `dir` may be a sessions root (containing `<session_id>/` subdirs) or a
/// single session directory (containing `meta.json` + `entries.jsonl`).
///
/// Returns a dict with shape:
///   {"root": str, "sessions": [{"meta": {...}, "entries": [...], ...}, ...]}
#[pyfunction]
#[pyo3(text_signature = "(dir)")]
pub fn read_sessions(py: Python<'_>, dir: &str) -> PyResult<Py<PyAny>> {
    let data = session_viewer::read_sessions(std::path::Path::new(dir))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    // Serialize to serde_json::Value, then convert to Python objects via
    // the shared value_conv (handles datetime strings, nested dicts, etc.).
    let value: serde_json::Value = serde_json::to_value(&data)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    value_to_pyobject(py, &value)
}

/// Return the bundled viewer HTML (with the `__VIEWER_DATA_JSON__` placeholder).
#[pyfunction]
#[pyo3(text_signature = "()")]
pub fn viewer_html(py: Python<'_>) -> PyResult<Py<PyString>> {
    Ok(PyString::new(py, session_viewer::VIEWER_HTML).unbind())
}
