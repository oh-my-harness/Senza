//! `serde_json::Value` ↔ Python 对象双向转换。

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList, PyString};
use serde_json::Value;

/// 将 `serde_json::Value` 转换为 Python 对象。
pub fn value_to_pyobject(py: Python<'_>, value: &Value) -> PyResult<Py<PyAny>> {
    let obj = match value {
        Value::Null => py.None(),
        Value::Bool(b) => (*b).into_pyobject(py)?.to_owned().into_any().unbind(),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                i.into_pyobject(py)?.into_any().unbind()
            } else if let Some(f) = n.as_f64() {
                f.into_pyobject(py)?.into_any().unbind()
            } else {
                py.None()
            }
        }
        Value::String(s) => PyString::new(py, s).into_any().unbind(),
        Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(value_to_pyobject(py, item)?)?;
            }
            list.into_any().unbind()
        }
        Value::Object(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, value_to_pyobject(py, v)?)?;
            }
            dict.into_any().unbind()
        }
    };
    Ok(obj)
}

/// 将 Python 对象转换为 `serde_json::Value`。
pub fn pyobject_to_value(obj: &Bound<'_, PyAny>) -> PyResult<Value> {
    if obj.is_none() {
        return Ok(Value::Null);
    }
    if let Ok(b) = obj.extract::<bool>() {
        return Ok(Value::Bool(b));
    }
    // Try i64 first, then u64 (for ints > i64::MAX), then f64.
    if let Ok(i) = obj.extract::<i64>() {
        return Ok(serde_json::Number::from(i).into());
    }
    if let Ok(u) = obj.extract::<u64>() {
        return Ok(serde_json::Number::from(u).into());
    }
    if let Ok(f) = obj.extract::<f64>() {
        if let Some(n) = serde_json::Number::from_f64(f) {
            return Ok(n.into());
        }
        // from_f64 returns None for NaN/Infinity
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "cannot convert non-finite float ({f}) to JSON value"
        )));
    }
    if let Ok(s) = obj.extract::<String>() {
        return Ok(Value::String(s));
    }
    // bytes → base64-encoded string
    if let Ok(bytes) = obj.cast::<PyBytes>() {
        use base64::Engine;
        let encoded = base64::engine::general_purpose::STANDARD.encode(bytes.as_bytes());
        return Ok(Value::String(encoded));
    }
    if let Ok(list) = obj.cast::<PyList>() {
        let mut arr = Vec::with_capacity(list.len());
        for item in list {
            arr.push(pyobject_to_value(&item)?);
        }
        return Ok(Value::Array(arr));
    }
    if let Ok(dict) = obj.cast::<PyDict>() {
        let mut map = serde_json::Map::new();
        for (k, v) in dict {
            let key = k.extract::<String>()?;
            map.insert(key, pyobject_to_value(&v)?);
        }
        return Ok(Value::Object(map));
    }
    Err(pyo3::exceptions::PyTypeError::new_err(format!(
        "cannot convert {} to JSON value",
        obj.get_type().name()?
    )))
}
