//! PyO3 SDK 验证 crate。

use std::sync::Arc;

use llm_harness_runtime::workflow::executor::{HttpCallExecutor, HttpCallPolicy, ShellExecutor};
use llm_harness_runtime_sandbox_os::OsEnv;
use pyo3::prelude::*;

pub mod event_stream;
pub mod pyagent;
pub mod pybudget;
pub mod pybuilder;
pub mod pyerror;
pub mod pyeventstream;
pub mod pyharness;
pub mod pyhooks;
pub mod pylogging;
pub mod pyloop;
pub mod pymcp;
pub mod pyplugin;
pub mod pypricing;
pub mod pyprovider;
pub mod pyresponseformat;
pub mod pyrules;
pub mod pyskills;
pub mod pytool;
pub mod pyviewer;
pub mod pyworkflow;
pub mod value_conv;

/// PyO3 module entry point.
#[pymodule]
fn senza(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    // 桥接 Rust tracing → Python logging：用户 `logging.basicConfig(level=DEBUG)`
    // 即可看到 Rust 底座日志，级别/handler/格式完全由 Python 侧控制。
    pylogging::init_logging();
    m.add("RustPanicError", py.get_type::<pyerror::RustPanicError>())?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(set_event_loop, m)?)?;
    m.add_function(wrap_pyfunction!(to_json, m)?)?;
    m.add_function(wrap_pyfunction!(pyviewer::read_sessions, m)?)?;
    m.add_function(wrap_pyfunction!(pyviewer::viewer_html, m)?)?;
    m.add_function(wrap_pyfunction!(from_json, m)?)?;
    // `PyAgent`'s `#[new]` uses `MockLlmClient` (test-only). Gating the
    // class registration behind `test-utils` keeps it out of production
    // wheels, where it would be visible via `dir(senza)` yet raise
    // `TypeError: cannot create 'Agent' instances`. Production callers
    // use `HarnessBuilder` → `AgentHarness` instead.
    #[cfg(feature = "test-utils")]
    m.add_class::<pyagent::PyAgent>()?;
    m.add_class::<event_stream::PyEventIterator>()?;
    m.add_class::<pyworkflow::PyJudgeWrapper>()?;
    m.add_class::<pyworkflow::PyCompositeJudge>()?;
    m.add_class::<pyworkflow::PyExecutorWrapper>()?;
    m.add_class::<pyworkflow::PyEnvWrapper>()?;
    m.add_class::<pyhooks::PyHookWrapper>()?;
    m.add_class::<pytool::PyToolWrapper>()?;
    m.add_class::<pytool::PyToolContext>()?;
    m.add_function(wrap_pyfunction!(create_sync_tool, m)?)?;
    m.add_function(wrap_pyfunction!(create_tool, m)?)?;
    m.add_function(wrap_pyfunction!(create_judge, m)?)?;
    m.add_function(wrap_pyfunction!(create_composite_judge, m)?)?;
    m.add_function(wrap_pyfunction!(create_executor, m)?)?;
    m.add_function(wrap_pyfunction!(create_shell_executor, m)?)?;
    m.add_function(wrap_pyfunction!(create_http_executor, m)?)?;
    m.add_function(wrap_pyfunction!(create_os_env, m)?)?;
    m.add_function(wrap_pyfunction!(create_fs_tools_plugin, m)?)?;
    m.add_function(wrap_pyfunction!(create_before_turn_hook, m)?)?;
    m.add_class::<pyeventstream::PyEventStreamHandle>()?;
    m.add_class::<pyeventstream::PyWaitForExternalEventTool>()?;
    m.add_function(wrap_pyfunction!(pyeventstream::create_event_channel, m)?)?;
    m.add_function(wrap_pyfunction!(create_after_turn_hook, m)?)?;
    m.add_function(wrap_pyfunction!(create_before_run_hook, m)?)?;
    m.add_function(wrap_pyfunction!(create_after_provider_response_hook, m)?)?;
    m.add_function(wrap_pyfunction!(create_before_provider_request_hook, m)?)?;
    m.add_function(wrap_pyfunction!(create_before_tool_call_hook, m)?)?;
    m.add_function(wrap_pyfunction!(create_after_tool_call_hook, m)?)?;
    m.add_function(wrap_pyfunction!(create_should_stop_hook, m)?)?;
    m.add_function(wrap_pyfunction!(create_before_compact_hook, m)?)?;
    m.add_function(wrap_pyfunction!(create_transform_context_hook, m)?)?;
    m.add_function(wrap_pyfunction!(create_prepare_next_turn_hook, m)?)?;
    m.add_class::<pybuilder::PyHarnessBuilder>()?;
    m.add_class::<pyplugin::PyPluginWrapper>()?;
    m.add_function(wrap_pyfunction!(create_plugin, m)?)?;
    m.add_class::<pyresponseformat::PyResponseFormat>()?;
    m.add_function(wrap_pyfunction!(
        pyresponseformat::create_json_object_format,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        pyresponseformat::create_json_schema_format,
        m
    )?)?;
    m.add_class::<pyprovider::PyProvider>()?;
    m.add_function(wrap_pyfunction!(pyprovider::create_openai_provider, m)?)?;
    m.add_function(wrap_pyfunction!(pyprovider::create_anthropic_provider, m)?)?;
    m.add_class::<pypricing::PyPricingProvider>()?;
    m.add_function(wrap_pyfunction!(pypricing::create_pricing_provider, m)?)?;
    m.add_function(wrap_pyfunction!(
        pypricing::create_pricing_provider_callback,
        m
    )?)?;
    m.add_class::<pybudget::PyBudgetExceededHook>()?;
    m.add_function(wrap_pyfunction!(pybudget::create_budget_exceeded_hook, m)?)?;
    m.add_class::<pyrules::PyPredicate>()?;
    m.add_class::<pyrules::PyRuleChain>()?;
    m.add_class::<pyrules::PyRuleChainBuilder>()?;
    m.add_function(wrap_pyfunction!(pyrules::create_rule_chain, m)?)?;
    m.add_function(wrap_pyfunction!(pyrules::create_contains_predicate, m)?)?;
    m.add_function(wrap_pyfunction!(pyrules::create_regex_field_predicate, m)?)?;
    m.add_function(wrap_pyfunction!(pyrules::create_number_range_predicate, m)?)?;
    m.add_function(wrap_pyfunction!(pyrules::create_rate_limit_predicate, m)?)?;
    m.add_function(wrap_pyfunction!(pyrules::create_rule_approval_hook, m)?)?;
    m.add_class::<pyskills::PySkill>()?;
    m.add_function(wrap_pyfunction!(pyskills::load_skills, m)?)?;
    m.add_class::<pyharness::PyAgentHarness>()?;
    m.add_class::<pyharness::PyHarnessEventIterator>()?;
    m.add_class::<pyworkflow::PyWorkflowEngine>()?;
    m.add_class::<pyworkflow::PyWorkflowEventIterator>()?;
    m.add_class::<pymcp::PyMcpServerConfig>()?;
    m.add_class::<pymcp::PyMcpManager>()?;
    Ok(())
}

/// Return the SDK version string.
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// Register the user's asyncio event loop for async callback scheduling.
///
/// When set, `async def` tool/hook/budget callbacks are scheduled onto the
/// registered loop via `asyncio.run_coroutine_threadsafe`, instead of
/// `asyncio.run()` (which creates a throwaway loop).  This lets callbacks
/// share loop-bound resources (sessions, locks, queues) with the caller.
///
/// The loop must be running on another thread; otherwise a deadlock will
/// occur because the blocking thread waits for a result the loop cannot
/// produce.
#[pyfunction]
#[pyo3(text_signature = "(loop)")]
fn set_event_loop(loop_obj: Py<PyAny>) {
    pyloop::set_event_loop(loop_obj);
}

/// Convert a Python object to a JSON string.
#[pyfunction]
fn to_json(obj: &Bound<'_, PyAny>) -> PyResult<String> {
    let value = crate::value_conv::pyobject_to_value(obj)?;
    Ok(value.to_string())
}

/// Parse a JSON string into a Python object.
#[pyfunction]
fn from_json(py: Python<'_>, json_str: &str) -> PyResult<Py<PyAny>> {
    let value: serde_json::Value = serde_json::from_str(json_str)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    crate::value_conv::value_to_pyobject(py, &value)
}

/// 从 Python callable 创建一个同步 `Tool`。
///
/// 此函数是 `create_tool` 的别名——`create_tool` 已自动检测 `async def`
/// 回调并正确处理。保留此名称以简化从旧 API 的迁移。
#[pyfunction]
fn create_sync_tool<'py>(
    py: Python<'py>,
    name: &str,
    description: &str,
    parameters_schema: &str,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pytool::PyToolWrapper>> {
    create_tool(py, name, description, parameters_schema, callback)
}

/// 从 Python callable 创建一个 `Tool`（统一入口，支持 sync 与 async 回调）。
///
/// 若 `callback` 是 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行——`select()` 内部释放 GIL，无需独立事件循环线程。
#[pyfunction]
#[pyo3(text_signature = "(name, description, parameters_schema, callback)")]
fn create_tool<'py>(
    py: Python<'py>,
    name: &str,
    description: &str,
    parameters_schema: &str,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pytool::PyToolWrapper>> {
    let schema: serde_json::Value = serde_json::from_str(parameters_schema)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let tool = pytool::PyTool::new(name.to_string(), description.to_string(), schema, callback);
    let wrapper = pytool::PyToolWrapper {
        tool: Arc::new(tool),
    };
    Py::new(py, wrapper).map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `StepTransitionJudge`。
///
/// callback 签名：`callback(ctx: dict) -> str`
/// 返回值编码：`"to:<step_id>"`, `"retry"`, `"fail:<reason>"`, `"abort:<reason>"`
#[pyfunction]
fn create_judge<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyworkflow::PyJudgeWrapper>> {
    let judge = pyworkflow::PyJudge::new(callback);
    let wrapper = pyworkflow::PyJudgeWrapper {
        judge: Arc::new(judge)
            as Arc<dyn llm_harness_runtime::workflow::judge::StepTransitionJudge>,
    };
    Py::new(py, wrapper).map(|p| p.into_bound(py))
}

/// 创建一个 CompositeJudge，支持按节点注册独立路由函数。
///
/// 用法：
/// ```python
/// judge = senza.create_composite_judge()
/// judge.on("step1", lambda ctx: "to:step2")
/// judge.on("step2", lambda ctx: "abort:done" if ctx["output"] else "retry")
/// judge.fallback(lambda ctx: "abort:done")  # 可选
/// engine = senza.WorkflowEngine(workflow, provider, model, judge)
/// ```
///
/// 未注册 `.on()` 的 step 会依次尝试：用户 fallback → 声明式边 (Expr/Label) → Abort。
/// 如果 workflow 有声明式条件边 (Expr 或 Label)，引擎会自动注入 EdgeConditionJudge 作为 fallback。
#[pyfunction]
fn create_composite_judge<'py>(
    py: Python<'py>,
) -> PyResult<Bound<'py, pyworkflow::PyCompositeJudge>> {
    Py::new(py, pyworkflow::PyCompositeJudge::new()).map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `StepExecutor`。
///
/// callback 签名：`callback(ctx: dict) -> dict`
/// 返回 dict 须含 `"output"` (str)，可选 `"structured"` (dict)。
#[pyfunction]
fn create_executor<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyworkflow::PyExecutorWrapper>> {
    let executor = pyworkflow::PyExecutor::new(callback);
    let wrapper = pyworkflow::PyExecutorWrapper {
        executor: Arc::new(executor),
    };
    Py::new(py, wrapper).map(|p| p.into_bound(py))
}

/// Create a ShellExecutor with a command allowlist.
///
/// `commands` is a list of allowed command names (e.g. ["echo", "python"]).
/// `default_timeout_ms` overrides the default timeout per shell call (default 30000).
/// `max_output_bytes` caps stdout/stderr capture (default 1 MiB).
///
/// The executor is NOT registered by default — register with
/// `engine.with_executor("shell", shell_executor)`.
#[pyfunction]
#[pyo3(signature = (commands, default_timeout_ms=30000, max_output_bytes=1048576))]
fn create_shell_executor<'py>(
    py: Python<'py>,
    commands: Vec<String>,
    default_timeout_ms: u64,
    max_output_bytes: usize,
) -> PyResult<Bound<'py, pyworkflow::PyExecutorWrapper>> {
    let exec = ShellExecutor::new(commands)
        .with_default_timeout(std::time::Duration::from_millis(default_timeout_ms))
        .with_max_output_bytes(max_output_bytes);
    let wrapper = pyworkflow::PyExecutorWrapper {
        executor: Arc::new(exec),
    };
    Py::new(py, wrapper).map(|p| p.into_bound(py))
}

/// Create an HttpCallExecutor with a host allowlist policy.
///
/// `allowed_hosts` is a list of allowed hostnames (e.g. ["api.example.com"]).
/// `allowed_schemes` defaults to ["https"]; pass ["http", "https"] to allow HTTP.
/// `max_timeout_ms` caps request duration (default 30000).
/// `allow_private_ip_targets` defaults to False (blocks localhost/10.x/172.16.x/192.168.x).
#[pyfunction]
#[pyo3(signature = (allowed_hosts, allowed_schemes=None, max_timeout_ms=30000, allow_private_ip_targets=false))]
fn create_http_executor<'py>(
    py: Python<'py>,
    allowed_hosts: Vec<String>,
    allowed_schemes: Option<Vec<String>>,
    max_timeout_ms: u64,
    allow_private_ip_targets: bool,
) -> PyResult<Bound<'py, pyworkflow::PyExecutorWrapper>> {
    let mut policy = HttpCallPolicy::new(allowed_hosts)
        .with_max_timeout(std::time::Duration::from_millis(max_timeout_ms));
    if let Some(schemes) = allowed_schemes {
        policy = policy.with_allowed_schemes(schemes);
    }
    policy = policy.allow_private_ip_targets(allow_private_ip_targets);
    let exec = HttpCallExecutor::new(policy);
    let wrapper = pyworkflow::PyExecutorWrapper {
        executor: Arc::new(exec),
    };
    Py::new(py, wrapper).map(|p| p.into_bound(py))
}

/// Create an OS-backed `ExecutionEnv` rooted at `working_dir`.
///
/// The returned env exposes the real filesystem and shell of the host.
/// Pass it to `WorkflowEngine(..., env=...)` so that executors such as
/// `create_shell_executor` can run real commands (subject to their own
/// allowlists). Without an env, the engine uses `UnsupportedEnv`, whose
/// `execute_shell` always returns an error.
///
/// SECURITY: This env executes real shell commands on the host. The
/// `ShellExecutor` command allowlist is the first line of defense, but
/// callers are responsible for the security of `working_dir` and the
/// surrounding runtime.
#[pyfunction]
#[pyo3(signature = (working_dir="."))]
fn create_os_env<'py>(
    py: Python<'py>,
    working_dir: &str,
) -> PyResult<Bound<'py, pyworkflow::PyEnvWrapper>> {
    let env: Arc<dyn llm_harness_types::ExecutionEnv> =
        Arc::new(OsEnv::new(std::path::PathBuf::from(working_dir)));
    Py::new(py, pyworkflow::PyEnvWrapper::new(env)).map(|p| p.into_bound(py))
}

/// 创建一个聚合 `bash`/`read`/`write`/`edit` 四件套的 `FsToolsPlugin`。
///
/// 四个工具通过共享的 `FileSnapshotStore` 耦合：`read` 记录文件快照并
/// 在输出中附加 `[PATH#TAG]` 锚点，`edit` 据此检测 stale 内容并拒绝
/// 对已过期快照的编辑；`write` 在覆写后使对应快照失效。
///
/// 这些工具通过 `ExecutionEnv` 执行真实文件系统 / shell 操作——
/// 必须在 `HarnessBuilder.env(create_os_env(...))` 或
/// `WorkflowEngine(..., env=create_os_env(...))` 提供真实 env 时才有意义。
/// 在 `UnsupportedEnv`（默认）下，`bash`/`read`/`write`/`edit` 会返回错误。
///
/// 用法：
/// ```python
/// plugin = lh.create_fs_tools_plugin()
/// harness = lh.HarnessBuilder("gpt-4o").plugin(plugin).env(lh.create_os_env()).build()
/// ```
#[pyfunction]
fn create_fs_tools_plugin<'py>(py: Python<'py>) -> PyResult<Bound<'py, pyplugin::PyPluginWrapper>> {
    let store = Arc::new(parking_lot::RwLock::new(
        llm_harness_runtime_tools::FileSnapshotStore::new(),
    ));
    let plugin: Arc<dyn llm_harness_agent::Plugin> =
        Arc::new(llm_harness_runtime_tools::FsToolsPlugin::new(Some(store)));
    Py::new(py, pyplugin::PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `BeforeTurnHook`。
///
/// callback 签名：`callback(ctx: dict) -> None`
/// 若 callback 为 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行。
#[pyfunction]
fn create_before_turn_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyhooks::PyHookWrapper>> {
    let hook = pyhooks::PyBeforeTurnHook::new(callback);
    Py::new(
        py,
        pyhooks::PyHookWrapper {
            kind: pyhooks::HookKind::BeforeTurn(Arc::new(hook)),
        },
    )
    .map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `AfterTurnHook`。
///
/// callback 签名：`callback(ctx: dict) -> None`
/// 若 callback 为 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行。
#[pyfunction]
fn create_after_turn_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyhooks::PyHookWrapper>> {
    let hook = pyhooks::PyAfterTurnHook::new(callback);
    Py::new(
        py,
        pyhooks::PyHookWrapper {
            kind: pyhooks::HookKind::AfterTurn(Arc::new(hook)),
        },
    )
    .map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `BeforeRunHook`。
///
/// callback 签名：`callback(ctx: dict) -> dict | None`
/// 返回 dict 可含 `additional_messages`（list[dict]）和 `system_prompt`（str | None）。
/// 若 callback 为 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行。
#[pyfunction]
fn create_before_run_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyhooks::PyHookWrapper>> {
    let hook = pyhooks::PyBeforeRunHook::new(callback);
    Py::new(
        py,
        pyhooks::PyHookWrapper {
            kind: pyhooks::HookKind::BeforeRun(Arc::new(hook)),
        },
    )
    .map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `AfterProviderResponseHook`。
///
/// callback 签名：`callback(info: dict) -> None`
/// 若 callback 为 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行。
#[pyfunction]
fn create_after_provider_response_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyhooks::PyHookWrapper>> {
    let hook = pyhooks::PyAfterProviderResponseHook::new(callback);
    Py::new(
        py,
        pyhooks::PyHookWrapper {
            kind: pyhooks::HookKind::AfterProviderResponse(Arc::new(hook)),
        },
    )
    .map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `BeforeProviderRequestHook`。
///
/// callback 签名：`callback(opts: dict) -> None`
/// 若 callback 为 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行。
#[pyfunction]
fn create_before_provider_request_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyhooks::PyHookWrapper>> {
    let hook = pyhooks::PyBeforeProviderRequestHook::new(callback);
    Py::new(
        py,
        pyhooks::PyHookWrapper {
            kind: pyhooks::HookKind::BeforeProviderRequest(Arc::new(hook)),
        },
    )
    .map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `BeforeToolCallHook`。
///
/// callback 签名：`callback(ctx: dict) -> str | dict`
/// 返回 `"allow"` 或 `{"action": "modify", "args": ...}` 或 `{"action": "deny", "result": ...}`。
/// 若 callback 为 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行。
#[pyfunction]
fn create_before_tool_call_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyhooks::PyHookWrapper>> {
    let hook = pyhooks::PyBeforeToolCallHook::new(callback);
    Py::new(
        py,
        pyhooks::PyHookWrapper {
            kind: pyhooks::HookKind::BeforeToolCall(Arc::new(hook)),
        },
    )
    .map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `AfterToolCallHook`。
///
/// callback 签名：`callback(ctx: dict) -> str | dict`
/// 返回 `"passthrough"` 或 `{"action": "patch", "content": ...}`。
/// 若 callback 为 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行。
#[pyfunction]
fn create_after_tool_call_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyhooks::PyHookWrapper>> {
    let hook = pyhooks::PyAfterToolCallHook::new(callback);
    Py::new(
        py,
        pyhooks::PyHookWrapper {
            kind: pyhooks::HookKind::AfterToolCall(Arc::new(hook)),
        },
    )
    .map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `ShouldStopHook`。
///
/// callback 签名：`callback(ctx: dict) -> bool`
/// 返回 `True` 停止 loop，`False` 强制再跑一轮。
/// 若 callback 为 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行。
#[pyfunction]
fn create_should_stop_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyhooks::PyHookWrapper>> {
    let hook = pyhooks::PyShouldStopHook::new(callback);
    Py::new(
        py,
        pyhooks::PyHookWrapper {
            kind: pyhooks::HookKind::ShouldStop(Arc::new(hook)),
        },
    )
    .map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `BeforeCompactHook`。
///
/// callback 签名：`callback(ctx: dict) -> str | dict`
/// 返回 `"proceed"` / `"skip"` / `"compact"` 或 `{"action": "override", "summary": <msg_dict>, "first_kept_entry": <str>}`。
/// `first_kept_entry` 必须是 `ctx["entry_ids"]` 中的一个值。
/// 可选字段 `tokens_before` (默认 `ctx["estimated_tokens"]`) 和 `tokens_after` (默认 0)。
/// 若 callback 为 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行。
#[pyfunction]
fn create_before_compact_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyhooks::PyHookWrapper>> {
    let hook = pyhooks::PyBeforeCompactHook::new(callback);
    Py::new(
        py,
        pyhooks::PyHookWrapper {
            kind: pyhooks::HookKind::BeforeCompact(Arc::new(hook)),
        },
    )
    .map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `TransformContextHook`。
///
/// callback 签名：`callback(ctx: dict) -> dict`
/// 返回 dict 须含 `system_prompt`（str | None）和 `messages`（list[dict]）。
/// 若 callback 为 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行。
#[pyfunction]
fn create_transform_context_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyhooks::PyHookWrapper>> {
    let hook = pyhooks::PyTransformContextHook::new(callback);
    Py::new(
        py,
        pyhooks::PyHookWrapper {
            kind: pyhooks::HookKind::TransformContext(Arc::new(hook)),
        },
    )
    .map(|p| p.into_bound(py))
}

/// 从 Python callable 创建一个 `PrepareNextTurnHook`。
///
/// callback 签名：`callback(ctx: dict) -> dict | None`
/// 返回 dict 可含 `model`（str）、`thinking_level`（str）、`temperature`（float | None）、
/// `active_tools`（list[str]）。返回 `None` 表示沿用当前值。
/// 若 callback 为 `async def`，其 coroutine 将在 `spawn_blocking` 线程上
/// 通过 `asyncio.run()` 执行。
#[pyfunction]
fn create_prepare_next_turn_hook<'py>(
    py: Python<'py>,
    callback: Py<PyAny>,
) -> PyResult<Bound<'py, pyhooks::PyHookWrapper>> {
    let hook = pyhooks::PyPrepareNextTurnHook::new(callback);
    Py::new(
        py,
        pyhooks::PyHookWrapper {
            kind: pyhooks::HookKind::PrepareNextTurn(Arc::new(hook)),
        },
    )
    .map(|p| p.into_bound(py))
}

/// 从 Python 侧配置创建一个 `Plugin`。
///
/// `tools` 为 `create_tool` 创建的 Tool 列表；
/// `hooks` 为 `create_*_hook` 创建的 Hook 列表。
#[pyfunction]
#[pyo3(signature = (name, tools=None, hooks=None))]
fn create_plugin<'py>(
    py: Python<'py>,
    name: &str,
    tools: Option<Vec<Bound<'py, pytool::PyToolWrapper>>>,
    hooks: Option<Vec<Bound<'py, pyhooks::PyHookWrapper>>>,
) -> PyResult<Bound<'py, pyplugin::PyPluginWrapper>> {
    let mut tool_vec: Vec<Arc<dyn llm_harness_types::Tool>> = vec![];
    if let Some(tools) = tools {
        for t in tools {
            let borrowed = t.try_borrow()?;
            tool_vec.push(borrowed.tool.clone());
        }
    }
    let mut hook_vec: Vec<pyhooks::HookKind> = vec![];
    if let Some(hooks) = hooks {
        for h in hooks {
            let borrowed = h.try_borrow()?;
            hook_vec.push(borrowed.kind.clone());
        }
    }
    let plugin: Arc<dyn llm_harness_agent::Plugin> = Arc::new(pyplugin::PyPlugin::new(
        name.to_string(),
        tool_vec,
        hook_vec,
    ));
    Py::new(py, pyplugin::PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
