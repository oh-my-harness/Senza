//! `ResponseFormat` 的 Python 包装。
//!
//! 两种构造方式：
//! - `create_json_object_format()` — 要求模型输出合法 JSON object
//! - `create_json_schema_format(name, schema, strict=None)` — 要求模型输出符合 JSON Schema 的 JSON

use llm_harness_loop::ResponseFormat;
use pyo3::prelude::*;
use pyo3::types::PyAny;

/// 不透明的 `ResponseFormat` 包装。
#[pyclass(name = "ResponseFormat")]
pub struct PyResponseFormat {
    pub fmt: ResponseFormat,
}

impl PyResponseFormat {
    pub fn new(fmt: ResponseFormat) -> Self {
        Self { fmt }
    }
}

/// 创建一个 `JsonObject` response format——要求模型输出合法 JSON object。
#[pyfunction]
pub fn create_json_object_format<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyResponseFormat>> {
    Py::new(py, PyResponseFormat::new(ResponseFormat::JsonObject)).map(|p| p.into_bound(py))
}

/// 创建一个 `JsonSchema` response format——要求模型输出符合指定 JSON Schema 的 JSON。
///
/// - `name` — schema 的逻辑名（OpenAI wire format 要求）。
/// - `schema` — JSON Schema 对象（dict 或 JSON 字符串）。
/// - `strict=None` — `Some(True)` 要求模型严格遵循 schema。
#[pyfunction]
#[pyo3(signature = (name, schema, strict=None))]
pub fn create_json_schema_format<'py>(
    py: Python<'py>,
    name: &str,
    schema: &Bound<'py, PyAny>,
    strict: Option<bool>,
) -> PyResult<Bound<'py, PyResponseFormat>> {
    // 接受 dict 或 JSON 字符串
    let schema_val = if let Ok(s) = schema.extract::<String>() {
        serde_json::from_str(&s).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("invalid JSON schema string: {e}"))
        })?
    } else {
        crate::value_conv::pyobject_to_value(schema)?
    };
    Py::new(
        py,
        PyResponseFormat::new(ResponseFormat::JsonSchema {
            name: name.to_string(),
            schema: schema_val,
            strict,
        }),
    )
    .map(|p| p.into_bound(py))
}
