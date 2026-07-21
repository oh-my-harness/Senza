//! `PyAgent` — 包装 `Agent` + 全局 tokio runtime。
//!
//! 验证风险点：
//! - 全局 tokio runtime 使用 `PyOnceLock` 初始化（非 `Lazy`/`LazyLock`，
//!   后者在 pytest 下可能产生双向死锁）。
//! - `Agent::prompt()` 的 async 驱动：`py.detach()` 释放 GIL 后，
//!   `runtime.block_on()` 运行 agent loop。
//! - 事件流从 Rust broadcast 到 Python 消费者的链路（通过 `subscribe`）。

#[cfg(feature = "test-utils")]
use std::sync::Arc;

#[cfg(feature = "test-utils")]
use llm_harness_agent::Agent;
#[cfg(feature = "test-utils")]
use llm_harness_agent::AgentOptions;
#[cfg(feature = "test-utils")]
use llm_harness_loop::test_utils::{MockLlmClient, MockResponse};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;

/// 全局 tokio runtime——所有 `PyAgent` 实例共享。
///
/// 使用 `PyOnceLock`（PyO3 0.29 中 `GILOnceCell` 的替代品）确保初始化
/// 在持有 GIL 时进行，避免 `Lazy`/`LazyLock` 在 pytest 下可能产生的
/// 双向死锁（线程 A 持有静态初始化锁等待 GIL，线程 B 持有 GIL 等待
/// 静态初始化锁）。
static RT: PyOnceLock<tokio::runtime::Runtime> = PyOnceLock::new();
/// 获取或初始化全局 tokio runtime。
pub(crate) fn runtime(py: Python<'_>) -> &'static tokio::runtime::Runtime {
    RT.get_or_init(py, || {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("failed to build tokio runtime")
    })
}

/// Python 侧的 `Agent` 包装类。
///
/// 整个类（struct + impl + pymethods）门控在 `test-utils` 后：
/// `#[new]` 用 `MockLlmClient`（test-only），生产 wheel 不应暴露。
/// 门控 `#[pyclass]` 本身（而非仅 `add_class`）确保 stub 生成器
/// 在生产构建中看不到 `Agent` 类，避免 .pyi 与运行时漂移。
#[cfg(feature = "test-utils")]
#[pyclass(name = "Agent")]
pub struct PyAgent {
    agent: Arc<Agent>,
}
#[cfg(feature = "test-utils")]
impl PyAgent {
    /// 从已有 `Arc<Agent>` 构造 `PyAgent`（供 builder 等内部路径使用）。
    pub fn from_agent(agent: Arc<Agent>) -> Self {
        Self { agent }
    }
}

#[cfg(feature = "test-utils")]
#[pymethods]
impl PyAgent {
    /// 创建一个使用 `MockLlmClient` 的 Agent（仅供测试）。
    ///
    /// `model` 参数仅用于标识，不影响 mock 响应。
    /// 生产环境请使用 `HarnessBuilder` 构建真实 provider 的 Agent。
    #[cfg(feature = "test-utils")]
    #[new]
    #[pyo3(signature = (model="mock-model"))]
    fn new(model: &str) -> PyResult<Self> {
        let client = Arc::new(MockLlmClient::new(vec![
            MockResponse::text("hello from mock"),
            MockResponse::text("hello from mock"),
            MockResponse::text("hello from mock"),
            MockResponse::text("hello from mock"),
        ]));
        let opts = AgentOptions::new(model.to_string());
        let agent = Arc::new(Agent::new(client, opts));
        Ok(Self { agent })
    }

    /// 同步执行 prompt，阻塞直到完成。
    ///
    /// 通过 `py.detach()` 释放 GIL，让 tokio worker 线程在需要时
    /// 能 acquire GIL（例如执行 Python tool callback）。
    fn prompt(&self, py: Python<'_>, text: &str) -> PyResult<String> {
        let agent = self.agent.clone();
        let text = text.to_string();
        let rt = runtime(py);

        // 释放 GIL + panic 隔离：Rust panic 转为 RustPanicError 而非崩溃。
        crate::pyerror::detach_catch_panic_result(py, move || {
            rt.block_on(async move { agent.prompt(text).await })
        })?;

        // 返回最后一条 assistant 消息的文本内容。
        let state = self.agent.state();
        let last = state.messages.last();
        let response = match last {
            Some(llm_harness_types::AgentMessage::Assistant(msg)) => msg.text_content(),
            _ => String::new(),
        };
        Ok(response)
    }

    /// 获取当前 agent 状态中的消息数量。
    fn message_count(&self) -> usize {
        self.agent.state().messages.len()
    }

    /// 获取当前 phase（"idle" / "running"）。
    fn phase(&self) -> &'static str {
        match self.agent.state().phase {
            llm_harness_agent::AgentPhase::Idle => "idle",
            llm_harness_agent::AgentPhase::Running => "running",
        }
    }

    /// 返回事件迭代器。`timeout_ms` 为单次 `__next__` 等待超时（毫秒）。
    ///
    /// 典型用法：`for event in agent.events(timeout_ms=5000): ...`
    #[pyo3(signature = (timeout_ms=5000, max_consecutive_timeouts=1))]
    fn events(
        &self,
        py: Python<'_>,
        timeout_ms: u64,
        max_consecutive_timeouts: u32,
    ) -> PyResult<Py<crate::event_stream::PyEventIterator>> {
        let rx = self.agent.subscribe();
        let handle = runtime(py).handle().clone();
        let iter = crate::event_stream::PyEventIterator::new(
            rx,
            timeout_ms,
            max_consecutive_timeouts,
            handle,
        );
        Py::new(py, iter)
    }

    /// 取消当前正在运行的 prompt（如果有）。不阻塞。
    fn abort(&self) {
        self.agent.abort();
    }
}
