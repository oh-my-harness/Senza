//! `InMemoryTraceExporter` PyO3 binding.
//!
//! Wraps `llm_harness_runtime_trace_otel::InMemoryTraceExporter`,
//! exposing span retrieval as Python dicts.

use llm_harness_runtime::observability::tracer::{AttributeValue, SpanEvent, SpanKind, SpanStatus};
use llm_harness_runtime_trace_otel::InMemoryTraceExporter;
use pyo3::prelude::*;

/// Convert a `SpanKind` to its string representation.
fn span_kind_str(kind: &SpanKind) -> &'static str {
    match kind {
        SpanKind::Internal => "internal",
        SpanKind::Client => "client",
        SpanKind::Server => "server",
        SpanKind::Producer => "producer",
        SpanKind::Consumer => "consumer",
    }
}

/// Convert a `SpanStatus` to a Python-compatible value.
///
/// `Ok` → `"ok"`, `Unset` → `"unset"`, `Error(msg)` → `{"error": msg}`.
fn span_status_to_py(py: Python<'_>, status: &SpanStatus) -> PyResult<Py<PyAny>> {
    match status {
        SpanStatus::Ok => Ok(py.None().into_bound(py).into()),
        SpanStatus::Unset => Ok(py.None().into_bound(py).into()),
        SpanStatus::Error(msg) => {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("error", msg.clone())?;
            Ok(dict.into())
        }
    }
}

/// Convert an `AttributeValue` to a Python object.
fn attribute_value_to_py(py: Python<'_>, val: &AttributeValue) -> PyResult<Py<PyAny>> {
    match val {
        AttributeValue::String(s) => Ok(s.clone().into_pyobject(py)?.into()),
        AttributeValue::Int(i) => Ok(i.into_pyobject(py)?.into()),
        AttributeValue::Float(f) => Ok(f.into_pyobject(py)?.into()),
        AttributeValue::Bool(b) => Ok((*b).into_pyobject(py)?.to_owned().into_any().unbind()),
        AttributeValue::Array(arr) => {
            let list = pyo3::types::PyList::empty(py);
            for item in arr {
                list.append(attribute_value_to_py(py, item)?)?;
            }
            Ok(list.into())
        }
    }
}

/// Convert a `SpanEvent` to a Python dict.
fn span_event_to_dict(py: Python<'_>, event: &SpanEvent) -> PyResult<Py<PyAny>> {
    let dict = pyo3::types::PyDict::new(py);

    dict.set_item("span_id", event.span_id.0.to_string())?;
    dict.set_item("trace_id", event.trace_id.0.to_string())?;
    dict.set_item(
        "parent_span_id",
        event
            .parent_span_id
            .map(|id| id.0.to_string())
            .unwrap_or_default(),
    )?;
    dict.set_item("name", event.name.clone())?;
    dict.set_item("kind", span_kind_str(&event.kind))?;
    dict.set_item("start_time", event.start_time.to_rfc3339())?;
    dict.set_item("end_time", event.end_time.to_rfc3339())?;

    // attributes: HashMap<String, AttributeValue> → dict
    let attrs = pyo3::types::PyDict::new(py);
    for (k, v) in &event.attributes {
        attrs.set_item(k, attribute_value_to_py(py, v)?)?;
    }
    dict.set_item("attributes", attrs)?;

    dict.set_item("status", span_status_to_py(py, &event.status)?)?;

    Ok(dict.into())
}

/// Python-side wrapper for `InMemoryTraceExporter`.
///
/// An in-memory trace exporter that accumulates `SpanEvent` values for
/// testing. `exported_spans()` returns accumulated spans as dicts;
/// `exported_span_count()` returns the count.
#[pyclass(name = "InMemoryTraceExporter")]
pub struct PyInMemoryTraceExporter {
    inner: InMemoryTraceExporter,
}

#[pymethods]
impl PyInMemoryTraceExporter {
    /// Create a new empty exporter.
    #[new]
    fn new() -> Self {
        Self {
            inner: InMemoryTraceExporter::new(),
        }
    }

    /// Return all spans exported so far, as a list of dicts.
    ///
    /// Each dict has keys: `span_id`, `trace_id`, `parent_span_id`,
    /// `name`, `kind`, `start_time`, `end_time`, `attributes`, `status`.
    fn exported_spans(&self, py: Python<'_>) -> PyResult<Vec<Py<PyAny>>> {
        let spans = self.inner.exported_spans();
        spans.iter().map(|s| span_event_to_dict(py, s)).collect()
    }

    /// Return the number of spans exported so far.
    fn exported_span_count(&self) -> usize {
        self.inner.exported_spans().len()
    }
}
