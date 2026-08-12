//! `JsonlAuditSink` PyO3 binding.
//!
//! Wraps `llm_harness_runtime_audit_jsonl::JsonlAuditSink`, exposing
//! construction and the async `validate` class method as a synchronous
//! Python call (blocking on the global tokio runtime with panic isolation).

use std::path::PathBuf;

use llm_harness_runtime_audit_jsonl::JsonlAuditSink;
use pyo3::prelude::*;

use crate::core::pyagent::runtime;
use crate::shared::pyerror::detach_catch_panic_result;

/// Python-side wrapper for `JsonlAuditSink`.
///
/// A JSONL file-backed audit sink with SHA-256 hash-chain integrity.
/// `validate(path)` checks the hash chain and returns the count of valid
/// entries.
#[pyclass(name = "JsonlAuditSink")]
pub struct PyJsonlAuditSink {
    #[allow(dead_code)]
    inner: JsonlAuditSink,
}

#[pymethods]
impl PyJsonlAuditSink {
    /// Create a new `JsonlAuditSink` writing to `path` (opened lazily).
    #[new]
    fn new(path: &str) -> Self {
        Self {
            inner: JsonlAuditSink::new(PathBuf::from(path)),
        }
    }

    /// Validate the hash chain of a JSONL audit log.
    ///
    /// Returns the number of valid entries, or raises `RuntimeError` on
    /// the first broken link / parse error / I/O error.
    #[staticmethod]
    fn validate(py: Python<'_>, path: &str) -> PyResult<usize> {
        let path = PathBuf::from(path);
        let rt = runtime(py);
        detach_catch_panic_result(py, move || {
            rt.block_on(async move { JsonlAuditSink::validate(&path).await })
        })
    }
}
