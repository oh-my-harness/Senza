//! MCP (Model Context Protocol) Python 绑定。
//!
//! 暴露 MCP client 侧 API：`McpServerConfig` 配置构造、`McpManager`
//! 多服务器生命周期管理。所有 async 方法用 `block_on` 同步桥接，
//! 与 Senza 现有的 `harness.prompt()` / `builder.build()` 一致。

use std::collections::HashMap;
use std::sync::Arc;

use llm_harness_runtime_mcp::config::{McpConfigFile, McpServerConfig};
use llm_harness_runtime_mcp::manager::{ConnectionStatus, McpManager};
use pyo3::prelude::*;

use crate::pyagent::runtime;

// ── PyMcpServerConfig ───────────────────────────────────────────────────────

/// MCP server 配置。
///
/// 三种构造方式：
/// - `McpServerConfig.stdio(command="npx", args=[...])`
/// - `McpServerConfig.http(url="https://...")`
/// - `McpServerConfig.sse(url="https://...")`
#[pyclass(name = "McpServerConfig")]
pub struct PyMcpServerConfig {
    pub(crate) inner: McpServerConfig,
}

#[pymethods]
impl PyMcpServerConfig {
    /// 创建 stdio server 配置。
    #[staticmethod]
    #[pyo3(signature = (command, args=None, env=None, cwd=None, timeout=None))]
    fn stdio(
        command: String,
        args: Option<Vec<String>>,
        env: Option<HashMap<String, String>>,
        cwd: Option<String>,
        timeout: Option<u64>,
    ) -> Self {
        Self {
            inner: McpServerConfig::Stdio {
                command,
                args: args.unwrap_or_default(),
                env: env.unwrap_or_default(),
                cwd: cwd.map(std::path::PathBuf::from),
                timeout,
            },
        }
    }

    /// 创建 HTTP server 配置。
    #[staticmethod]
    #[pyo3(signature = (url, headers=None, timeout=None))]
    fn http(url: String, headers: Option<HashMap<String, String>>, timeout: Option<u64>) -> Self {
        Self {
            inner: McpServerConfig::HttpOrSse {
                url,
                transport_type: None,
                headers: headers.unwrap_or_default(),
                timeout,
            },
        }
    }

    /// 创建 SSE server 配置（legacy，显式指定 SSE 传输）。
    #[staticmethod]
    #[pyo3(signature = (url, headers=None, timeout=None))]
    fn sse(url: String, headers: Option<HashMap<String, String>>, timeout: Option<u64>) -> Self {
        Self {
            inner: McpServerConfig::HttpOrSse {
                url,
                transport_type: Some("sse".into()),
                headers: headers.unwrap_or_default(),
                timeout,
            },
        }
    }

    fn __repr__(&self) -> String {
        match &self.inner {
            McpServerConfig::Stdio { command, .. } => {
                format!("McpServerConfig.stdio(command={command:?})")
            }
            McpServerConfig::HttpOrSse { url, .. } => {
                format!("McpServerConfig.http(url={url:?})")
            }
        }
    }
}

// ── PyMcpManager ────────────────────────────────────────────────────────────

/// MCP 多服务器生命周期管理器。
///
/// 管理多个 MCP server 的连接、工具发现和重连。
/// 所有 async 方法同步执行（block_on 桥接），与 Senza 现有 API 一致。
#[pyclass(name = "McpManager")]
pub struct PyMcpManager {
    pub(crate) inner: Arc<McpManager>,
}

#[pymethods]
impl PyMcpManager {
    #[new]
    fn new() -> Self {
        Self {
            inner: Arc::new(McpManager::new()),
        }
    }

    /// 添加并连接一个 MCP server。阻塞直到连接完成或失败。
    fn add_server(&self, py: Python<'_>, name: String, config: &PyMcpServerConfig) -> PyResult<()> {
        let manager = self.inner.clone();
        let config = config.inner.clone();
        let rt = runtime(py);
        crate::pyerror::detach_catch_panic_result(py, move || {
            rt.block_on(async move {
                manager
                    .add_server(name, config)
                    .await
                    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
            })
        })
    }

    /// 从 mcp.json 文件加载并连接所有 server。
    fn load_config_file(&self, py: Python<'_>, path: String) -> PyResult<()> {
        let manager = self.inner.clone();
        let rt = runtime(py);
        crate::pyerror::detach_catch_panic_result(py, move || {
            rt.block_on(async move {
                let config = McpConfigFile::from_file(std::path::Path::new(&path))
                    .await
                    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
                manager
                    .discover_and_connect(config.mcp_servers)
                    .await
                    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
            })
        })
    }

    /// 获取所有已连接 server 的工具名列表。
    /// 工具名格式：`mcp__<server_name>__<tool_name>`
    fn list_tools(&self) -> Vec<String> {
        self.inner
            .get_tools()
            .iter()
            .map(|t| t.full_name.clone())
            .collect()
    }

    /// 获取 server 连接状态。
    /// 返回 "connected" / "connecting" / "disconnected"。
    fn get_status(&self, name: String) -> String {
        match self.inner.get_connection_status(&name) {
            ConnectionStatus::Connected => "connected",
            ConnectionStatus::Connecting => "connecting",
            ConnectionStatus::Disconnected => "disconnected",
        }
        .to_string()
    }

    /// 重连指定 server。
    fn reconnect(&self, py: Python<'_>, name: String) -> PyResult<()> {
        let manager = self.inner.clone();
        let rt = runtime(py);
        crate::pyerror::detach_catch_panic_result(py, move || {
            rt.block_on(async move {
                manager
                    .reconnect(&name)
                    .await
                    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
            })
        })
    }

    /// 断开指定 server。
    fn disconnect_server(&self, py: Python<'_>, name: String) -> PyResult<()> {
        let manager = self.inner.clone();
        let rt = runtime(py);
        crate::pyerror::detach_catch_panic_result(py, move || {
            rt.block_on(async move {
                manager
                    .disconnect_server(&name)
                    .await
                    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
            })
        })
    }

    /// 断开所有 server。
    fn disconnect_all(&self, py: Python<'_>) -> PyResult<()> {
        let manager = self.inner.clone();
        let rt = runtime(py);
        crate::pyerror::detach_catch_panic_result(py, move || {
            rt.block_on(async move {
                manager
                    .disconnect_all()
                    .await
                    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
            })
        })
    }

    /// 返回所有 server 的错误信息。返回 dict[name, error_msg]。
    fn errors(&self) -> HashMap<String, String> {
        self.inner.errors()
    }

    fn __repr__(&self) -> String {
        let tools = self.inner.get_tools();
        format!(
            "McpManager(servers={}, tools={})",
            self.inner.sessions().len(),
            tools.len()
        )
    }
}
