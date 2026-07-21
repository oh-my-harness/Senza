//! 事件流——`broadcast::Receiver<Arc<AgentEvent>>` → Python 同步迭代器。
//!
//! 验证风险点：
//! - `AgentEvent` 不可直接 Serialize（`ToolError`/`AgentError` 含 `anyhow::Error`）。
//!   本模块手动逐变体转换为 Python dict，对非 Serialize 的错误类型使用 `to_string()`。
//! - `tokio::sync::broadcast::Receiver` 暴露为 Python sync iterator。
//! - `py.detach()` 释放 GIL 后阻塞等待事件，避免 GIL 死锁。

use std::sync::Arc;

use llm_harness_types::{AgentEvent, AgentMessage, ContentBlock, ToolResult};
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::value_conv::value_to_pyobject;

/// 将 `ToolResult` 转换为扁平化的 Python dict（事件流用）。
///
/// 与 `pyhooks::tool_result_to_dict` 不同，此函数将 content 拼接为
/// 单个 `text` 字符串，便于事件流消费者直接读取。
fn tool_result_to_flat_dict(py: Python<'_>, result: &ToolResult) -> PyResult<Py<PyAny>> {
    let dict = PyDict::new(py);
    dict.set_item("terminate", result.terminate)?;

    // content: 提取文本块拼接，其余块序列化为 JSON
    let texts: Vec<String> = result
        .content
        .iter()
        .filter_map(|b| match b {
            ContentBlock::Text { text } => Some(text.clone()),
            _ => None,
        })
        .collect();
    dict.set_item("text", texts.join("\n"))?;

    // details: serde_json::Value → Python
    dict.set_item("details", value_to_pyobject(py, &result.details)?)?;

    Ok(dict.into_any().unbind())
}

/// 将 `AgentMessage` 转换为 Python dict。
///
/// `AgentMessage` derive 了 `Serialize`，但直接 `serde_json::to_value` 会产生
/// tagged enum 结构。这里提取角色 + 文本以便 Python 侧简单消费。
fn agent_message_to_dict(py: Python<'_>, msg: &AgentMessage) -> PyResult<Py<PyAny>> {
    let dict = PyDict::new(py);
    let (role, text) = match msg {
        AgentMessage::User(m) => ("user", {
            let texts: Vec<String> = m
                .content
                .iter()
                .filter_map(|b| match b {
                    ContentBlock::Text { text } => Some(text.clone()),
                    _ => None,
                })
                .collect();
            texts.join("\n")
        }),
        AgentMessage::Assistant(m) => ("assistant", m.text_content()),
        AgentMessage::ToolResult(m) => {
            let texts: Vec<String> = m
                .content
                .iter()
                .filter_map(|b| match b {
                    ContentBlock::Text { text } => Some(text.clone()),
                    _ => None,
                })
                .collect();
            ("tool_result", texts.join("\n"))
        }
        AgentMessage::BranchSummary(m) => ("branch_summary", m.summary.clone()),
        AgentMessage::CompactionSummary(m) => ("compaction_summary", m.summary.clone()),
        AgentMessage::Custom(m) => ("custom", serde_json::to_string(&m.data).unwrap_or_default()),
    };
    dict.set_item("role", role)?;
    dict.set_item("text", text)?;
    Ok(dict.into_any().unbind())
}

/// 将 `AgentEvent` 转换为 Python dict。
///
/// 逐变体处理；对非 Serialize 的 `ToolError`/`AgentError` 使用 `to_string()`。
/// 每个返回的 dict 都含 `"type"` 字段标识事件类型。
pub fn agent_event_to_dict(py: Python<'_>, event: &AgentEvent) -> PyResult<Py<PyAny>> {
    let dict = PyDict::new(py);
    match event {
        AgentEvent::AgentStart => {
            dict.set_item("type", "agent_start")?;
        }
        AgentEvent::AgentEnd { new_messages } => {
            dict.set_item("type", "agent_end")?;
            dict.set_item("new_messages_count", new_messages.len())?;
            // 转换消息列表
            let msgs: PyResult<Vec<Py<PyAny>>> = new_messages
                .iter()
                .map(|m| agent_message_to_dict(py, m))
                .collect();
            dict.set_item("new_messages", msgs?)?;
        }
        AgentEvent::TurnStart { index } => {
            dict.set_item("type", "turn_start")?;
            dict.set_item("index", index)?;
        }
        AgentEvent::TurnEnd {
            index,
            message,
            tool_results,
        } => {
            dict.set_item("type", "turn_end")?;
            dict.set_item("index", index)?;
            dict.set_item("message_text", message.text_content())?;
            // tool_results: Vec<(String, Result<ToolResult, ToolError>)>
            let results = PyDict::new(py);
            for (id, res) in tool_results {
                match res {
                    Ok(tr) => {
                        results.set_item(id, tool_result_to_flat_dict(py, tr)?)?;
                    }
                    Err(e) => {
                        let err_dict = PyDict::new(py);
                        err_dict.set_item("ok", false)?;
                        err_dict.set_item("error", e.to_string())?;
                        results.set_item(id, err_dict)?;
                    }
                }
            }
            dict.set_item("tool_results", results)?;
        }
        AgentEvent::MessageStart { message_id } => {
            dict.set_item("type", "message_start")?;
            dict.set_item("message_id", message_id)?;
        }
        AgentEvent::MessageUpdate {
            message_id,
            partial,
        } => {
            dict.set_item("type", "message_update")?;
            dict.set_item("message_id", message_id)?;
            dict.set_item("text", partial.text_content())?;
        }
        AgentEvent::MessageEnd {
            message_id,
            message,
        } => {
            dict.set_item("type", "message_end")?;
            dict.set_item("message_id", message_id)?;
            dict.set_item("text", message.text_content())?;
        }
        AgentEvent::TextDelta { message_id, text } => {
            dict.set_item("type", "text_delta")?;
            dict.set_item("message_id", message_id)?;
            dict.set_item("text", text)?;
        }
        AgentEvent::ThinkingDelta {
            message_id,
            thinking,
            signature,
        } => {
            dict.set_item("type", "thinking_delta")?;
            dict.set_item("message_id", message_id)?;
            dict.set_item("thinking", thinking)?;
            if let Some(sig) = signature {
                dict.set_item("signature", sig)?;
            }
        }
        AgentEvent::ToolCallStart {
            message_id,
            tool_use_id,
            name,
        } => {
            dict.set_item("type", "tool_call_start")?;
            dict.set_item("message_id", message_id)?;
            dict.set_item("tool_use_id", tool_use_id)?;
            dict.set_item("name", name)?;
        }
        AgentEvent::ToolCallArgsDelta {
            tool_use_id,
            partial_input,
        } => {
            dict.set_item("type", "tool_call_args_delta")?;
            dict.set_item("tool_use_id", tool_use_id)?;
            dict.set_item("partial_input", partial_input)?;
        }
        AgentEvent::ToolCallEnd { tool_use_id, args } => {
            dict.set_item("type", "tool_call_end")?;
            dict.set_item("tool_use_id", tool_use_id)?;
            dict.set_item("args", value_to_pyobject(py, args)?)?;
        }
        AgentEvent::ToolExecutionStart {
            tool_use_id,
            tool_name,
            args,
        } => {
            dict.set_item("type", "tool_execution_start")?;
            dict.set_item("tool_use_id", tool_use_id)?;
            dict.set_item("tool_name", tool_name)?;
            dict.set_item("args", value_to_pyobject(py, args)?)?;
        }
        AgentEvent::ToolExecutionUpdate {
            tool_use_id,
            partial,
        } => {
            dict.set_item("type", "tool_execution_update")?;
            dict.set_item("tool_use_id", tool_use_id)?;
            dict.set_item("result", tool_result_to_flat_dict(py, partial)?)?;
        }
        AgentEvent::ToolExecutionEnd {
            tool_use_id,
            result,
        } => {
            dict.set_item("type", "tool_execution_end")?;
            dict.set_item("tool_use_id", tool_use_id)?;
            match result {
                Ok(tr) => {
                    dict.set_item("ok", true)?;
                    dict.set_item("result", tool_result_to_flat_dict(py, tr)?)?;
                }
                Err(e) => {
                    dict.set_item("ok", false)?;
                    dict.set_item("error", e.to_string())?;
                }
            }
        }
        AgentEvent::Error(err) => {
            dict.set_item("type", "error")?;
            dict.set_item("message", err.to_string())?;
        }
        AgentEvent::RetryAttempt {
            attempt,
            max_retries,
            delay_ms,
            error,
        } => {
            dict.set_item("type", "retry_attempt")?;
            dict.set_item("attempt", attempt)?;
            dict.set_item("max_retries", max_retries)?;
            dict.set_item("delay_ms", delay_ms)?;
            dict.set_item("error", error)?;
        }
    }
    Ok(dict.into_any().unbind())
}

/// Python 迭代器，包装 `broadcast::Receiver<Arc<AgentEvent>>`。
///
/// 实现 Python iterator protocol：`__iter__` 返回 self，`__next__`
/// 在释放 GIL 的情况下通过全局 tokio runtime 阻塞等待事件（带超时），
/// 超时或 channel 关闭时返回 `None` 终止迭代。
#[pyclass(name = "EventIterator")]
pub struct PyEventIterator {
    rx: Option<tokio::sync::broadcast::Receiver<Arc<AgentEvent>>>,
    timeout_ms: u64,
    max_consecutive_timeouts: u32,
    consecutive_timeouts: u32,
    handle: tokio::runtime::Handle,
}

impl PyEventIterator {
    /// 从 broadcast::Receiver 和 runtime handle 构造迭代器。
    pub fn new(
        rx: tokio::sync::broadcast::Receiver<Arc<AgentEvent>>,
        timeout_ms: u64,
        max_consecutive_timeouts: u32,
        handle: tokio::runtime::Handle,
    ) -> Self {
        Self {
            rx: Some(rx),
            timeout_ms,
            max_consecutive_timeouts,
            consecutive_timeouts: 0,
            handle,
        }
    }
}

#[pymethods]
impl PyEventIterator {
    fn __iter__(slf: Py<Self>) -> Py<Self> {
        slf
    }

    /// 阻塞等待下一个事件，channel 关闭时返回 None。
    ///
    /// 超时不终止迭代，而是发出 `{"type": "timeout"}` 事件后继续轮询。
    /// 调用者可根据 timeout 事件决定是否 break。通过 `py.detach()` 释放 GIL。
    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        let rx = match &mut self.rx {
            Some(rx) => rx,
            None => return Ok(None),
        };

        let timeout = std::time::Duration::from_millis(self.timeout_ms);
        let handle = self.handle.clone();

        // 释放 GIL 后在 tokio runtime 上阻塞等待 broadcast 事件。
        let recv_result = crate::pyerror::detach_catch_panic(py, move || {
            handle.block_on(async move { tokio::time::timeout(timeout, rx.recv()).await })
        })?;

        match recv_result {
            // 收到事件
            Ok(Ok(event)) => {
                self.consecutive_timeouts = 0;
                let dict = agent_event_to_dict(py, &event)?;
                Ok(Some(dict))
            }
            // broadcast Lagged：消费者太慢，跳过丢失的事件，继续迭代
            Ok(Err(tokio::sync::broadcast::error::RecvError::Lagged(n))) => {
                // 发出 warning event，继续迭代
                let warning = pyo3::types::PyDict::new(py);
                warning.set_item("type", "lagged")?;
                warning.set_item("skipped", n)?;
                Ok(Some(warning.into_any().unbind()))
            }
            // channel 关闭：迭代终止
            Ok(Err(tokio::sync::broadcast::error::RecvError::Closed)) => Ok(None),
            // timeout elapsed：达到 max_consecutive_timeouts 则终止，否则发出 timeout 事件继续
            Err(_) => {
                self.consecutive_timeouts += 1;
                if self.consecutive_timeouts >= self.max_consecutive_timeouts {
                    Ok(None)
                } else {
                    let timeout_event = pyo3::types::PyDict::new(py);
                    timeout_event.set_item("type", "timeout")?;
                    Ok(Some(timeout_event.into_any().unbind()))
                }
            }
        }
    }
}
