//! Rust `tracing` → Python `logging` 桥接。
//!
//! 实现 `tracing_subscriber::Layer`，把 Rust 侧的 tracing 事件转发到
//! Python 标准库 `logging` 模块（logger 名 `"senza"`）。这样用户在
//! Python 端 `logging.basicConfig(level=logging.DEBUG)` 即可看到 Rust
//! 底座的 Debug 日志，级别 / handler / 格式化完全由 Python 侧控制。
//!
//! GIL 策略：`on_event` 在 tracing subscriber 线程上调用，通过
//! `Python::attach` 获取 GIL 后调用 Python `logging`。若 GIL 不可用
//! （解释器未初始化），静默跳过——日志不应导致 panic。

use std::sync::OnceLock;

use pyo3::prelude::*;
use pyo3::types::PyModule;
use tracing::{
    Event, Subscriber,
    field::{Field, Visit},
};
use tracing_subscriber::prelude::*;
use tracing_subscriber::{Layer, layer::Context};

/// Python logger 对象缓存（`logging.getLogger("senza")`），避免每次
/// 事件都走一次属性查找。
static PY_LOGGER: OnceLock<Py<PyAny>> = OnceLock::new();

/// 获取缓存的 Python logger，首次调用时通过 `logging.getLogger("senza")`
/// 创建并缓存。
fn get_logger(py: Python<'_>) -> PyResult<Py<PyAny>> {
    if let Some(logger) = PY_LOGGER.get() {
        return Ok(logger.clone_ref(py));
    }
    let logging = PyModule::import(py, "logging")?;
    let logger = logging.call_method1("getLogger", ("senza",))?.unbind();
    // OnceLock::get_or_init 不可用（需 GIL 内闭包返回 PyResult），用
    // get_or_try_init 风格的手动竞态处理。
    let _ = PY_LOGGER.set(logger.clone_ref(py));
    Ok(logger)
}

/// 把 tracing `Level` 映射到 Python logging 级别数字。
fn level_to_python(level: &tracing::Level) -> i32 {
    use tracing::Level;
    match *level {
        Level::ERROR => 40, // logging.ERROR
        Level::WARN => 30,  // logging.WARNING
        Level::INFO => 20,  // logging.INFO
        Level::DEBUG => 10, // logging.DEBUG
        Level::TRACE => 10, // Python 没有 TRACE，降级到 DEBUG
    }
}

/// 收集 tracing 事件的字段值到一个消息字符串。
struct ValueVisitor {
    fields: Vec<(String, String)>,
}

impl ValueVisitor {
    fn new() -> Self {
        Self { fields: Vec::new() }
    }
}

impl Visit for ValueVisitor {
    fn record_debug(&mut self, field: &Field, value: &dyn std::fmt::Debug) {
        self.fields
            .push((field.name().to_string(), format!("{value:?}")));
    }

    fn record_str(&mut self, field: &Field, value: &str) {
        self.fields
            .push((field.name().to_string(), value.to_string()));
    }
}

/// 桥接 layer：把 tracing 事件转发到 Python `logging`。
pub struct PythonLoggingLayer;

impl<S> Layer<S> for PythonLoggingLayer
where
    S: Subscriber,
{
    fn on_event(&self, event: &Event<'_>, _ctx: Context<'_, S>) {
        // 提取消息字段
        let mut visitor = ValueVisitor::new();
        event.record(&mut visitor);

        // 构造消息：优先用 "message" 字段，否则拼接所有字段
        let message = visitor
            .fields
            .iter()
            .find(|(k, _)| k == "message")
            .map(|(_, v)| v.clone())
            .unwrap_or_else(|| {
                visitor
                    .fields
                    .iter()
                    .map(|(k, v)| format!("{k}={v}"))
                    .collect::<Vec<_>>()
                    .join(" ")
            });

        let py_level = level_to_python(event.metadata().level());
        let target = event.metadata().target();

        let full_msg = if target.is_empty() || target == "senza" {
            message
        } else {
            format!("[{target}] {message}")
        };

        // 尝试获取 GIL 并转发到 Python logging；失败则静默降级到 stderr。
        let _ = Python::attach(|py| {
            let logger = get_logger(py)?;
            let logger = logger.bind(py);
            // logger.log(level, msg, *args)
            logger.call_method1("log", (py_level, full_msg))?;
            Ok::<_, PyErr>(())
        });
    }
}

/// 初始化日志桥接：安装 `PythonLoggingLayer` 到全局 tracing subscriber。
///
/// 使用 `EnvFilter` 从 `SENZA_LOG` / `RUST_LOG` 环境变量读取过滤规则，
/// 默认级别 WARN。若已有全局 subscriber（其他库先初始化了 tracing），
/// 打印一次 warning 到 stderr 而非静默失败。
pub fn init_logging() {
    use tracing_subscriber::EnvFilter;

    let filter = EnvFilter::try_from_env("SENZA_LOG")
        .or_else(|_| EnvFilter::try_from_env("RUST_LOG"))
        .unwrap_or_else(|_| {
            EnvFilter::builder()
                .with_default_directive(tracing::level_filters::LevelFilter::WARN.into())
                .from_env_lossy()
        });

    let result = tracing_subscriber::registry()
        .with(filter)
        .with(PythonLoggingLayer)
        .try_init();

    if let Err(e) = result {
        // 已有全局 subscriber——不 panic，打一次 stderr 提示。
        eprintln!(
            "senza: tracing subscriber already initialized, Python logging bridge not installed: {e}"
        );
    }
}
