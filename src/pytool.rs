//! Python callable 包装为 `Tool` trait 实现。
//!
//! 验证风险点：`Py<PyAny>` 持有 Python callable、`spawn_blocking` +
//! `Python::attach` + `call1` 调用 Python 函数、`ToolResult` 从 Python
//! dict 解析的完整路径。

use std::sync::Arc;

use futures::future::BoxFuture;
use llm_harness_types::{
    ContentBlock, Tool, ToolContext, ToolError, ToolExecutionMode, ToolResult,
};
#[cfg(feature = "test-utils")]
use llm_harness_types::{RunContext, RunRequest};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde_json::Value;
use tokio_util::sync::CancellationToken;

use crate::value_conv::{pyobject_to_value, value_to_pyobject};
/// Python callable 包装为 `Tool` trait。
pub struct PyTool {
    name: String,
    description: String,
    schema: Value,
    callback: Arc<Py<PyAny>>,
    is_async: bool,
}

impl PyTool {
    pub fn new(name: String, description: String, schema: Value, callback: Py<PyAny>) -> Self {
        let is_async = Python::attach(|py| {
            let inspect = pyo3::types::PyModule::import(py, "inspect")?;
            let is_coro: bool = inspect
                .call_method1("iscoroutinefunction", (callback.bind(py),))?
                .extract()?;
            Ok::<_, PyErr>(is_coro)
        })
        .unwrap_or_else(|e| {
            tracing::debug!("failed to detect async callback, assuming sync: {e}");
            false
        });
        Self {
            name,
            description,
            schema,
            callback: Arc::new(callback),
            is_async,
        }
    }
}

impl Tool for PyTool {
    fn name(&self) -> &str {
        &self.name
    }

    fn description(&self) -> &str {
        &self.description
    }
    fn execute<'a>(
        &'a self,
        args: Value,
        ctx: &'a ToolContext,
    ) -> BoxFuture<'a, Result<ToolResult, ToolError>> {
        let callback = Arc::clone(&self.callback);
        let is_async = self.is_async;
        let abort = ctx.abort.clone();
        let update_tx = ctx.update_tx.clone();
        Box::pin(async move {
            let result = tokio::task::spawn_blocking(move || {
                Python::attach(|py| {
                    let cb = callback.bind(py);
                    let py_args = value_to_pyobject(py, &args)?;
                    let py_ctx = PyToolContext::new(abort.clone(), update_tx.clone());

                    if is_async {
                        // async: schedule the coroutine on the user's main
                        // event loop when possible (issue #13), falling
                        // back to asyncio.run().
                        let coro = cb.call1((py_args, py_ctx))?;
                        let raw = crate::pyloop::run_coro(py, &coro)?;
                        parse_tool_result(&raw)
                    } else {
                        // sync: 直接调用
                        let raw = cb.call1((py_args, py_ctx))?;
                        parse_tool_result(&raw)
                    }
                })
            })
            .await
            .map_err(|e| ToolError::Execution(format!("callback join failed: {e}")))?
            .map_err(|e: PyErr| ToolError::Execution(e.to_string()))?;
            Ok(result)
        })
    }

    fn parameters_schema(&self) -> &Value {
        &self.schema
    }

    fn execution_mode(&self) -> ToolExecutionMode {
        ToolExecutionMode::Parallel
    }
}

/// 解析 Python 返回值为 `ToolResult`。
///
/// 期望 dict 形如：
/// ```python
/// {"content": [{"type": "text", "text": "..."}], "details": ..., "terminate": False}
/// ```
fn parse_tool_result(obj: &Bound<'_, PyAny>) -> PyResult<ToolResult> {
    // Accept plain string as shorthand for {"content": [{"type": "text", "text": <str>}]}
    if let Ok(s) = obj.extract::<String>() {
        return Ok(ToolResult {
            content: vec![ContentBlock::Text { text: s }],
            details: Value::Null,
            terminate: false,
        });
    }
    let dict = obj.cast::<PyDict>()?;

    // content: 可选，缺省或 None → 空列表
    let content_vec = match dict.get_item("content")? {
        Some(v) if !v.is_none() => {
            let content_list = v.cast::<PyList>()?;
            let mut blocks = Vec::with_capacity(content_list.len());
            for item in content_list {
                let item_dict = item.cast::<PyDict>()?;
                let block_type: String = item_dict
                    .get_item("type")?
                    .ok_or_else(|| {
                        pyo3::exceptions::PyValueError::new_err("content block missing 'type'")
                    })?
                    .extract()?;
                match block_type.as_str() {
                    "text" => {
                        let text: String = item_dict
                            .get_item("text")?
                            .ok_or_else(|| {
                                pyo3::exceptions::PyValueError::new_err(
                                    "text content block missing 'text'",
                                )
                            })?
                            .extract()?;
                        blocks.push(ContentBlock::Text { text });
                    }
                    other => {
                        return Err(pyo3::exceptions::PyValueError::new_err(format!(
                            "unsupported content block type: {other}"
                        )));
                    }
                }
            }
            blocks
        }
        _ => vec![],
    };

    // details: 可选，缺省或 None → Null
    let details = match dict.get_item("details")? {
        Some(v) if !v.is_none() => pyobject_to_value(&v)?,
        _ => Value::Null,
    };

    // terminate: 可选，缺省或 None → false
    let terminate = dict
        .get_item("terminate")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(false);

    Ok(ToolResult {
        content: content_vec,
        details,
        terminate,
    })
}

/// Python 侧的 tool context，暴露 `is_cancelled` 和 `send_update`。
#[pyclass(name = "ToolContext")]
pub struct PyToolContext {
    abort: CancellationToken,
    update_tx: tokio::sync::mpsc::Sender<ToolResult>,
}

impl PyToolContext {
    pub fn new(abort: CancellationToken, update_tx: tokio::sync::mpsc::Sender<ToolResult>) -> Self {
        Self { abort, update_tx }
    }
}

#[pymethods]
impl PyToolContext {
    /// 返回当前是否已收到取消信号。
    fn is_cancelled(&self) -> bool {
        self.abort.is_cancelled()
    }

    /// 推送一个部分结果（Python dict），解析后发送到 update channel。
    fn send_update(&self, result: &Bound<'_, PyAny>) -> PyResult<()> {
        let parsed = parse_tool_result(result)?;
        self.update_tx
            .try_send(parsed)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    }
}

/// 持有 `PyTool` 的不透明 Python 包装，供 Python 侧引用已注册的 tool。
#[pyclass(name = "Tool")]
pub struct PyToolWrapper {
    pub tool: Arc<PyTool>,
}

#[pymethods]
impl PyToolWrapper {
    /// 返回 tool 的名称。
    #[getter]
    fn name(&self) -> &str {
        self.tool.name()
    }

    /// 返回 tool 的描述。
    #[getter]
    fn description(&self) -> &str {
        self.tool.description()
    }

    /// 同步驱动 tool.execute：在独立 tokio runtime 上运行 async future。
    ///
    /// 仅供测试/验证使用；真实场景由 agent loop 调用 `execute`。
    #[cfg(feature = "test-utils")]
    fn drive(&self, args: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = args.py();
        let args_val = crate::value_conv::pyobject_to_value(args)?;
        let tool = self.tool.clone();
        // 在 Python 释放 GIL 后运行 tokio runtime，避免 GIL 与 runtime 死锁。
        // panic 隔离：Rust panic 转为 RustPanicError。
        crate::pyerror::detach_catch_panic(py, move || {
            let rt = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .map_err(|e| {
                    pyo3::exceptions::PyRuntimeError::new_err(format!(
                        "failed to create runtime: {e}"
                    ))
                })?;
            rt.block_on(async move {
                let ctx = build_test_ctx();
                let result = tool
                    .execute(args_val, &ctx)
                    .await
                    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
                Python::attach(|py| toolresult_to_pyobject(py, &result))
            })
        })?
    }
}

/// 构造测试用 `ToolContext`（不依赖完整 agent loop）。
#[cfg(feature = "test-utils")]
fn build_test_ctx() -> ToolContext {
    use llm_harness_loop::test_utils::{NoOpEnv, test_assistant_message};
    ToolContext {
        run: Arc::new(RunContext::new(RunRequest::default())),
        env: Arc::new(NoOpEnv),
        abort: CancellationToken::new(),
        tool_use_id: "test".into(),
        turn_index: 0,
        assistant_message: Arc::new(test_assistant_message(vec![])),
        update_tx: tokio::sync::mpsc::channel(1).0,
    }
}

/// 将 `ToolResult` 转换为 Python dict。
#[cfg(feature = "test-utils")]
fn toolresult_to_pyobject(py: Python<'_>, result: &ToolResult) -> PyResult<Py<PyAny>> {
    let dict = pyo3::types::PyDict::new(py);
    // content: Vec<ContentBlock> → list of dicts（ContentBlock 实现了 Serialize）
    let content_list = pyo3::types::PyList::empty(py);
    for block in &result.content {
        let block_json: Value = serde_json::to_value(block)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        content_list.append(value_to_pyobject(py, &block_json)?)?;
    }
    dict.set_item("content", content_list)?;
    dict.set_item("details", value_to_pyobject(py, &result.details)?)?;
    dict.set_item("terminate", result.terminate)?;
    Ok(dict.into_any().unbind())
}
