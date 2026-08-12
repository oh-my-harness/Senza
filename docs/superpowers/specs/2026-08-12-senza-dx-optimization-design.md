# Senza SDK 开发者体验优化设计

> **日期**: 2026-08-12
> **状态**: Draft
> **范围**: P0 文档修复 + P1 API 人体工学 + P2 会话持久化 & FinalAnswerValidator

---

## 1. 背景与动机

两份独立审计（developer-experience-review.md、senza-capability-audit.md）一致指出：Senza 的 Rust 内核能力一流，但 Python 侧的"第一公里体验"在劝退新用户。核心矛盾是 API 表达力与文档质量不匹配内核设计能力。

**核心问题**：

1. **文档与运行时 API 全面脱节**：README/api-reference/providers.md 使用已删除的 `create_*` API，用户复制第一行代码就 `AttributeError`
2. **API 人体工学粗糙**：事件是裸 dict 无类型安全、`chat()` 便捷方法缺失、命名不一致、无 `__all__`/`__doc__`
3. **功能缺口**：单 agent 会话无法持久化（H1）、无法校验最终回答（H2）

## 2. 目标

- 用户从 README 复制第一行代码即可跑通，零 `AttributeError`
- 最常见任务（发 prompt → 拿文本）一步完成
- 事件类型有类型安全（常量 + TypedDict），拼错可被 IDE/mypy 捕获
- 单 agent 会话可持久化到磁盘，支持崩溃恢复
- 业务用户可在最终回答提交前校验/拒绝

## 3. 需求

### 3.1 P0 — 文档同步（零代码改动）

- 同步 README.md、docs/api-reference.md、docs/providers.md、SENZA_DESIGN.md 到子模块 API
- 修复 api-reference.md 中 `parameters_schema` 文档（接受 dict 或 JSON 字符串）
- README 新增"API 结构"小节，说明顶层 vs 子模块划分规则
- README/api-reference 新增 `@senza.tool` 装饰器作为推荐的工具创建方式

### 3.2 P1 — API 人体工学（纯 Python 层 + 极少量 Rust）

- `harness.chat(text) -> str` 便捷方法
- `senza.EventType` 常量 + `SenzaEvent` TypedDict
- 统一 `parameters` vs `parameters_schema` 命名（`parameters` 为主名，`parameters_schema` 为兼容别名）
- `create_tool` 接受 dict schema 并自动 `json.dumps`
- `HarnessBuilder.tools([list])` 复数方法
- `senza.__all__` + `senza.__doc__`
- `create_tool` 回调签名修复（单参数回调可用）
- `HarnessBuilder.__init__` / `WorkflowEngine.__init__` 的 `__text_signature__` 修复
- `prompt()` docstring 补充顺序陷阱警告
- 同步更新 `__init__.pyi` stub

### 3.3 P2 — 会话持久化（Rust 绑定）

- 暴露 `JsonlSessionRepo`：`senza.knowledge.jsonl_session_repo(root_dir)`
- `HarnessBuilder.session_repo(repo, session_id=None)` builder 方法
- 有 `session_id` 时恢复已有会话，无 `session_id` 时新建持久化会话
- 无 `session_repo` 时走现有 `build(env)` 内存 session 路径（行为不变）

### 3.4 P2 — FinalAnswerValidator（Rust 绑定）

- `senza.hooks.final_answer_validator(callback)` 工厂函数
- `HarnessBuilder.final_answer_validator(validator)` builder 方法
- callback 签名：`callback(ctx: dict) -> None | str | dict`
- 返回 None 通过；返回 str/dict 拒绝并让 loop 重试
- 被拒绝的回答产生 `AgentError::FinalAnswerRejected`，已有错误映射不变

### 3.5 非目标

- Sandbox 网络白名单（H3）— 用户未选
- `ConvertToLlmHook` / `CustomMessageConverter`（H4）— 用户未选
- 统一 `HarnessBuilder.tool()` vs `WorkflowEngine.with_tool()` 命名（P3）
- MCP 凭据作用域 / 版本策略（P3）
- 自定义 `MemoryStore` 后端（P3）
- `sqlite-bundled` feature（P3）
- `harness.stream(text)` 方法（E6，设计原因正当，文档说明即可）
- `total_cost_usd()` 方法（E7）

## 4. 设计

### 4.1 方案选择：分层渐进

三层独立交付，每层可独立测试和验证：

1. **P0 文档层**：批量替换旧 API，零风险
2. **P1 Python 人体工学层**：在 `__init__.py`/`__init__.pyi` 中添加，零 Rust 改动（`tools()` 和 `__text_signature__` 除外，需极少量 Rust）
3. **P2 Rust 绑定层**：两处 Rust 改动（会话持久化 + FinalAnswerValidator）

### 4.2 P0 — 文档修复

**改动文件**：

| 文件 | 改动 |
|------|------|
| `README.md` | 全部 `create_*` 旧 API → 子模块 API；新增"API 结构"小节；新增 `@senza.tool` 装饰器推荐用法 |
| `docs/api-reference.md` | 同上 + 修复 `parameters_schema` 文档（接受 dict 或 JSON 字符串） |
| `docs/providers.md` | `create_openai_provider`/`create_anthropic_provider` → `providers.openai`/`providers.anthropic` |
| `SENZA_DESIGN.md` | §4 API 参考中的旧 API 同步 |

**替换映射**：

| 旧 API | 新 API |
|--------|--------|
| `senza.create_openai_provider(...)` | `senza.providers.openai(...)` |
| `senza.create_anthropic_provider(...)` | `senza.providers.anthropic(...)` |
| `senza.create_*_hook(cb)` | `senza.hooks.<name>(cb)` |
| `senza.create_*_plugin()`（strategy） | `senza.strategy.<name>()` |
| `senza.create_local_knowledge_source(...)` | `senza.knowledge.local_source(...)` |
| `senza.create_knowledge_plugin(...)` | `senza.knowledge.plugin(...)` |
| `senza.create_in_memory_store(...)` | `senza.knowledge.memory_store(...)` |
| `senza.create_memory_plugin(...)` | `senza.knowledge.memory_plugin(...)` |
| `senza.create_*_predicate(...)` | `senza.rules.<name>(...)` |
| `senza.create_rule_chain()` | `senza.rules.chain()` |
| `senza.create_jsonl_audit_sink` | `senza.infra.jsonl_audit_sink` |
| `senza.create_seatbelt_sandbox(...)` | `senza.infra.seatbelt_sandbox(...)` |
| `senza.create_bwrap_sandbox(...)` | `senza.infra.bwrap_sandbox(...)` |

**参考基准**：`docs/decision-tree.md` 已使用正确子模块 API。

**API 结构说明**（README 新增小节）：

> Senza 的公开 API 分为两层：
> - **顶层高频**：`HarnessBuilder`、`create_tool`、`create_judge`、`create_plugin` 等每个 Agent 都可能用到的构造函数。
> - **子模块分组**：按功能域组织的低频 API：`senza.providers`、`senza.hooks`、`senza.strategy`、`senza.knowledge`、`senza.rules`、`senza.infra`。

### 4.3 P1 — API 人体工学

#### 4.3.1 `harness.chat(text) -> str`

```python
def _harness_chat(self, text: str, timeout_ms: int = 30000) -> str:
    """Send a prompt and return the concatenated text response.

    Convenience wrapper: extract_text(prompt_and_collect(text)).
    """
    events = self.prompt_and_collect(text, timeout_ms)
    return extract_text(events)

AgentHarness.chat = _harness_chat
```

异步版本 `chat_async` 用 `asyncio.to_thread` 包装。在 `prompt()` 的 Python docstring wrapper 中补充顺序陷阱警告：`prompt()` 后调 `collect_until_settled()` 返回空列表。

#### 4.3.2 事件类型常量 + TypedDict

```python
class EventType:
    TEXT_DELTA = "text_delta"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    TOOL_RESULT = "tool_result"
    MESSAGE_END = "message_end"
    THINKING_DELTA = "thinking_delta"
    ERROR = "error"
    AGENT_END = "agent_end"
    SETTLED = "settled"
    ABORTED = "aborted"
    # ... 全部 15+ 种

class TextDeltaEvent(TypedDict):
    type: Literal["text_delta"]
    text: str
    message_id: str

class ToolCallStartEvent(TypedDict):
    type: Literal["tool_call_start"]
    tool_name: str
    tool_call_id: str
    # ... 每种事件一个 TypedDict

SenzaEvent = Union[TextDeltaEvent, ToolCallStartEvent, ...]
```

运行时事件仍为 dict（零破坏性）。`EventType` 常量消除魔法字符串，TypedDict 让 IDE/mypy 理解事件结构。

#### 4.3.3 统一 `parameters` 命名 + dict 支持

在 Python 层包装 `create_tool`：

```python
def create_tool(name, description, parameters=None, parameters_schema=None, callback=None):
    """Create a Tool from a callback.

    parameters (dict or JSON str): JSON Schema for the tool's parameters.
    """
    schema = parameters if parameters is not None else parameters_schema
    if schema is None:
        raise TypeError("Missing required argument: 'parameters'")
    if isinstance(schema, dict):
        schema = json.dumps(schema)
    return _create_tool_rust(name, description, schema, callback)
```

`parameters` 为推荐参数名，`parameters_schema` 保持兼容。dict 自动 `json.dumps`，解决 attachment-1 §1.2。

#### 4.3.4 `HarnessBuilder.tools([list])`

在 `src/core/pybuilder.rs` 中添加：

```rust
#[pyo3(text_signature = "($self, tools)")]
fn tools<'a>(
    mut slf: PyRefMut<'a, Self>,
    tools: Vec<Bound<'py, crate::core::pytool::PyToolWrapper>>,
) -> PyRefMut<'a, Self> {
    if let Some(b) = slf.builder.take() {
        for tool in tools {
            let tool_arc: Arc<dyn Tool> = /* extract from wrapper */;
            b = b.tool(tool_arc);
        }
        slf.builder = Some(b);
    }
    slf
}
```

与 `.hooks([list])` / `.skills([list])` 一致。需极少量 Rust 改动。

#### 4.3.5 `__all__` + `__doc__`

```python
"""Senza — Python SDK for llm-harness runtime."""

__all__ = [
    "HarnessBuilder", "AgentHarness", "WorkflowEngine",
    "create_tool", "create_sync_tool", "create_judge",
    "create_composite_judge", "create_plugin", "create_fs_tools_plugin",
    "create_os_env", "create_event_channel", "create_executor",
    "create_shell_executor", "create_http_executor",
    "create_pricing_provider", "create_pricing_provider_callback",
    "create_budget_exceeded_hook", "create_json_object_format",
    "create_json_schema_format", "create_timer_stream",
    "create_heartbeat_stream", "create_shell_monitor_stream",
    "load_skills", "UsageLedger",
    "providers", "hooks", "strategy", "knowledge", "infra", "rules",
    "EventType", "SenzaEvent", "tool",
    "extract_text", "stream_prompt", "stream_events", "stream_run",
    "enable_debug", "disable_debug", "set_event_loop",
    "to_json", "from_json", "version",
    # 异常类
    "SenzaError", "ProviderError", "RateLimitError", ...
]
```

#### 4.3.6 `create_tool` 回调签名修复

```python
import inspect

def _wrap_tool_callback(callback):
    """Allow single-argument callbacks (args only) by ignoring ctx."""
    try:
        sig = inspect.signature(callback)
        params = [p for p in sig.parameters.values()
                  if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)]
        if len(params) <= 1:
            return lambda args, ctx: callback(args)
    except (ValueError, TypeError):
        pass
    return callback
```

在 `create_tool` 的 Python 包装中调用。`@senza.tool` 装饰器已有类似逻辑，统一到此处。

#### 4.3.7 `__text_signature__` 修复

在 `src/core/pybuilder.rs` 和 `src/runtime/pyworkflow.rs` 中：

```rust
#[pymethods]
impl PyHarnessBuilder {
    #[new]
    #[pyo3(text_signature = "(model)")]
    fn new(model: &str) -> Self { ... }
}
```

`WorkflowEngine` 同理。这样 `help(HarnessBuilder.__init__)` 显示 `(model)` 而非 `(*args, **kwargs)`。

#### 4.3.8 更新 `.pyi` stub

所有新 API（`chat`、`EventType`、`SenzaEvent` TypedDict、`tools` 复数方法、`create_tool` 新签名、`__all__`）同步写入 `__init__.pyi`。运行 `scripts/check_stubs.py` 验证 stub 与运行时零偏差。

### 4.4 P2 — 会话持久化

#### 4.4.1 暴露 `JsonlSessionRepo`

在 `src/knowledge/pysessionrecall.rs` 中添加：

```rust
#[pyfunction]
#[pyo3(text_signature = "(root_dir)")]
pub fn create_jsonl_session_repo<'py>(
    py: Python<'py>,
    root_dir: &str,
) -> PyResult<Bound<'py, PySessionRepo>> {
    let repo: Arc<dyn llm_harness_agent::SessionRepo> =
        Arc::new(llm_harness_agent::JsonlSessionRepo::new(root_dir));
    Ok(Py::new(py, PySessionRepo { repo })?.into_bound(py))
}
```

`PySessionRepo` wrapper 已存在，只需新增工厂函数。在 `lib.rs` 的 `#[pymodule]` 中注册。

在 `__init__.py` 的 `knowledge` 子模块中添加：
```python
_knowledge.jsonl_session_repo = create_jsonl_session_repo
```

#### 4.4.2 `HarnessBuilder.session_repo()` builder 方法

在 `src/core/pybuilder.rs` 中：

- `PyHarnessBuilder` 结构体新增 `session_repo: Option<Arc<dyn SessionRepo>>` 和 `session_id: Option<String>` 字段
- 新增 `session_repo()` 方法设置这两个字段
- `build()` 方法中：若 `session_repo` 已设置，走 `build_with_session(env, session)` 路径

```rust
#[pyo3(text_signature = "($self, repo, session_id=None)")]
#[pyo3(signature = (repo, session_id=None))]
fn session_repo<'a>(
    mut slf: PyRefMut<'a, Self>,
    repo: &Bound<'_, PySessionRepo>,
    session_id: Option<String>,
) -> PyRefMut<'a, Self> {
    slf.session_repo = Some(repo.borrow().repo.clone());
    slf.session_id = session_id;
    slf
}
```

`build()` 中的分支逻辑：

```rust
if let Some(repo) = self.session_repo.take() {
    let storage = if let Some(id) = self.session_id.take() {
        rt.block_on(async move { repo.open(&id).await })
    } else {
        rt.block_on(async move {
            repo.create(CreateSessionOptions::default()).await
        })
    }?;
    let session = llm_harness_agent::Session::new(storage);
    // build_with_session 是同步的
    builder.build_with_session(env, session)
} else {
    // 现有路径：rt.block_on(async { builder.build(env).await })
}
```

#### 4.4.3 Python 侧用法

```python
# 新建持久化会话
repo = senza.knowledge.jsonl_session_repo("./sessions")
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .session_repo(repo)
    .build()
)

# 恢复已有会话
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .session_repo(repo, session_id="019f2b12-...")
    .build()
)
```

#### 4.4.4 不变项

- `InMemorySessionRepo` 的现有 API 不变
- `PySessionRepo` wrapper 结构不变
- 无 `session_repo` 时 `build()` 路径完全不变
- 与 `senza.viewer` 兼容：`python -m senza.viewer ./sessions` 可浏览 JSONL 会话

### 4.5 P2 — FinalAnswerValidator

#### 4.5.1 `PyFinalAnswerValidatorWrapper`

在 `src/core/pyhooks.rs` 中新增，模式与现有 11 个 hook wrapper 完全一致：

```rust
use llm_harness_types::{
    FinalAnswerValidationCtx, FinalAnswerValidationError, FinalAnswerValidator,
};

pub struct PyFinalAnswerValidatorWrapper {
    callback: Arc<Py<PyAny>>,
}

impl FinalAnswerValidator for PyFinalAnswerValidatorWrapper {
    fn validate<'a>(
        &'a self,
        ctx: FinalAnswerValidationCtx<'a>,
    ) -> BoxFuture<'a, Result<(), FinalAnswerValidationError>> {
        let cb = self.callback.clone();
        Box::pin(async move {
            // 1. 将 candidate 序列化为 owned dict（与现有 hook wrapper 相同模式）
            // 2. spawn_blocking + Python::attach 调用 callback
            // 3. 解析返回值：
            //    - None → Ok(())
            //    - str → Err(code="rejected", message=str)
            //    - dict → Err(code=dict["code"], message=dict["message"])
            // 4. async def callback 通过 pyloop::run_coro 调度
        })
    }
}
```

**Callback 签名**：

```python
def my_validator(ctx: dict) -> None | str | dict:
    """
    ctx keys:
        - candidate: dict  — 候选最终回答（AssistantMessage 序列化）
        - turn_index: int
    返回值：
        - None → 通过
        - str → 拒绝，message = 返回值，code = "rejected"
        - dict → 拒绝，需含 "code" 和 "message"
    """
```

`ctx` 中不含 `RunContext`（无法安全序列化），只传 `candidate` 和 `turn_index`。

#### 4.5.2 工厂函数与注册

在 `src/lib.rs` 中注册 `create_final_answer_validator` 工厂函数。

在 `src/core/pybuilder.rs` 中添加 `final_answer_validator()` 方法。由于 `HarnessBuilder.hooks` 字段是私有的，通过 `HarnessBuilder::hooks()` 方法注入：构造一个只含 `final_answer_validator` 的 `HarnessHooks`，调用 `builder.hooks(harness_hooks)` 合并（push 语义，与现有 `should_stop_hook()` 等方法一致）。

在 `__init__.py` 的 `_hooks` SimpleNamespace 中添加 `final_answer_validator`。

#### 4.5.3 错误传播

被拒绝的回答产生 `AgentError::FinalAnswerRejected { code, message }`，已有 Rust→Python 错误映射（`pyerror.rs:242` → `ToolError`）。validator 拒绝后 loop 继续运行让模型重试，这是 runtime 侧已有行为，Senza 无需额外处理。

#### 4.5.4 Python 侧用法

```python
def no_pii(ctx):
    answer = ctx["candidate"]["content"][0]["text"]
    if "PII" in answer:
        return {"code": "pii_detected", "message": "Answer contains PII"}

harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .final_answer_validator(senza.hooks.final_answer_validator(no_pii))
    .build()
)
```

## 5. 错误处理

- P0 文档修复：零风险，纯文本替换
- P1 人体工学：Python 层包装在现有 Rust API 之上，不修改 Rust 行为（`tools()` 和 `__text_signature__` 除外，但改动极小）
- P2 会话持久化：`repo.open(id)` 失败返回 `SessionError::SessionNotFound`，映射为 `SenzaError`；`build_with_session` 路径已有 runtime 测试覆盖
- P2 FinalAnswerValidator：拒绝产生已有 `FinalAnswerRejected` 错误，映射不变

## 6. 测试

### 6.1 P0

- `grep -r "create_openai_provider\|create_anthropic_provider\|create_before_turn_hook\|create_safety_defaults_plugin" README.md docs/ SENZA_DESIGN.md` 返回零结果

### 6.2 P1

- `import senza; senza.__doc__; senza.__all__` 正常返回
- `senza.EventType.TEXT_DELTA == "text_delta"`
- `harness.chat("hello")` 返回 str
- `create_tool(name, desc, parameters={...}, callback=lambda args: ...)` 接受 dict schema 且单参数回调不报错
- `HarnessBuilder.tools([tool1, tool2])` 正常注册
- `help(HarnessBuilder.__init__)` 显示 `(model)`
- `scripts/check_stubs.py` 零偏差

### 6.3 P2 会话持久化

- 创建 repo → build → prompt → drop harness → 重新 open → 验证 context 保留
- `python -m senza.viewer ./sessions` 可浏览 JSONL 会话

### 6.4 P2 FinalAnswerValidator

- 注册拒绝含 "forbidden" 的 validator → prompt → 验证模型重试
- 注册通过的 validator → prompt → 正常返回

## 7. 实施顺序

1. P0 文档修复（独立交付，零依赖）
2. P1 API 人体工学（Python 层为主，`tools()` 和 `__text_signature__` 需 Rust）
3. P2 会话持久化（Rust 绑定）
4. P2 FinalAnswerValidator（Rust 绑定）

每层独立验证后再进入下一层。

## 8. 覆盖矩阵

| 报告条目 | 设计节 | 状态 |
|---|---|---|
| P0 文档脱节 | §4.2 | ✅ |
| P0 `api-reference.md:97` 过时 | §4.2 | ✅ |
| P0 API 归属规则未文档化 | §4.2 | ✅ |
| P0 `@senza.tool` 未写进文档 | §4.2 | ✅ |
| P1.1 事件裸 dict | §4.3.2 | ✅ |
| P1.2 `parameters_schema` 要 JSON 字符串 | §4.3.3 | ✅ |
| P1.3 构造函数签名不可内省 | §4.3.7 | ✅ |
| P1.4 无 `__all__`/`__doc__` | §4.3.5 | ✅ |
| P1.5 API 归属不一致 | §4.2（文档说明） | ✅ |
| E1 `chat()` 缺失 | §4.3.1 | ✅ |
| E2 事件 stringly-typed | §4.3.2 | ✅ |
| E3 `prompt()` 返回 None | §4.3.1（docstring） | ✅ |
| E4 注册动词不一致 | §4.3.4（`tools()` 复数） | ✅ 部分 |
| E5 `parameters` vs `parameters_schema` | §4.3.3 | ✅ |
| E6 streaming 模块级函数 | — | 跳过（低，设计原因正当） |
| E7 `total_cost()` 返回 dict | — | 跳过（低，用户未选） |
| E8 文档过时 | §4.2 | ✅ |
| E9 `create_tool` 回调签名 | §4.3.6 | ✅ |
| H1 会话持久化 | §4.4 | ✅ |
| H2 FinalAnswerValidator | §4.5 | ✅ |
| H3 sandbox 网络白名单 | — | 用户未选 |
| H4 ConvertToLlmHook | — | 用户未选 |
