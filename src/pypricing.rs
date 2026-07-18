//! PricingProvider 的 Python 包装。
//!
//! 两种构造方式：
//! - `create_pricing_provider(table: dict)` — 静态定价表
//! - `create_pricing_provider_callback(callback)` — 动态定价回调

use std::collections::HashMap;
use std::sync::Arc;

use llm_harness_types::{PricingProvider, TokenPrice};
use pyo3::prelude::*;
use pyo3::types::PyDict;
/// 从 Python dict 构造 `TokenPrice`。
///
/// 缺失的字段默认为 0.0（允许只提供 input/output 的简化定价表）。
fn dict_to_token_price(d: &Bound<'_, PyDict>) -> PyResult<TokenPrice> {
    fn get_f64(d: &Bound<'_, PyDict>, key: &str) -> PyResult<f64> {
        Ok(d.get_item(key)?.and_then(|v| v.extract::<f64>().ok()).unwrap_or(0.0))
    }
    Ok(TokenPrice {
        input_per_mtok: get_f64(d, "input_per_mtok")?,
        output_per_mtok: get_f64(d, "output_per_mtok")?,
        cache_read_per_mtok: get_f64(d, "cache_read_per_mtok")?,
        cache_write_per_mtok: get_f64(d, "cache_write_per_mtok")?,
    })
}

// ── 静态定价表实现 ─────────────────────────────────────────────────────────

struct DictPricingProvider {
    table: HashMap<String, TokenPrice>,
}

impl PricingProvider for DictPricingProvider {
    fn price_for(&self, model: &str, _provider: &str) -> Option<TokenPrice> {
        self.table.get(model).cloned()
    }
}

// ── 回调定价实现 ───────────────────────────────────────────────────────────

struct CallbackPricingProvider {
    callback: Py<PyAny>,
}

impl PricingProvider for CallbackPricingProvider {
    fn price_for(&self, model: &str, provider: &str) -> Option<TokenPrice> {
        Python::attach(|py| {
            match self.callback.bind(py).call1((model, provider)) {
                Ok(result) => {
                    if result.is_none() {
                        return None;
                    }
                    let dict = result.cast::<PyDict>().ok()?;
                    dict_to_token_price(dict).ok()
                }
                Err(e) => {
                    tracing::warn!(
                        "pricing callback for model '{}' failed: {}",
                        model,
                        e
                    );
                    None
                }
            }
        })
    }
}

// ── Python 包装类 ──────────────────────────────────────────────────────────

/// 定价 provider handle（通过 `create_pricing_provider` 创建）。
#[pyclass(name = "PricingProvider")]
pub struct PyPricingProvider {
    pub(crate) provider: Arc<dyn PricingProvider>,
}

impl PyPricingProvider {
    pub fn new(provider: Arc<dyn PricingProvider>) -> Self {
        Self { provider }
    }
}

/// 从 dict 构造静态定价表 provider。
///
/// `table` 格式：
/// ```python
/// {
///     "gpt-4o": {
///         "input_per_mtok": 2.5,
///         "output_per_mtok": 10.0,
///         "cache_read_per_mtok": 1.25,
///         "cache_write_per_mtok": 2.5,
///     },
/// }
/// ```
#[pyfunction]
#[pyo3(text_signature = "(table)")]
pub fn create_pricing_provider<'py>(
    py: Python<'py>,
    table: &Bound<'py, PyDict>,
) -> PyResult<Bound<'py, PyPricingProvider>> {
    let mut map = HashMap::new();
    for (k, v) in table {
        let key: String = k.extract()?;
        let d = v.cast::<PyDict>()?;
        map.insert(key, dict_to_token_price(d)?);
    }
    let provider: Arc<dyn PricingProvider> = Arc::new(DictPricingProvider { table: map });
    Py::new(py, PyPricingProvider::new(provider)).map(|p| p.into_bound(py))
}

/// 从 callback 构造动态定价 provider。
///
/// `callback(model: str, provider: str) -> Optional[dict]`
/// 返回 None 表示该模型无定价信息。
#[pyfunction]
#[pyo3(text_signature = "(callback)")]
pub fn create_pricing_provider_callback<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, PyPricingProvider>> {
    let provider: Arc<dyn PricingProvider> = Arc::new(CallbackPricingProvider { callback });
    Py::new(py, PyPricingProvider::new(provider)).map(|p| p.into_bound(py))
}
