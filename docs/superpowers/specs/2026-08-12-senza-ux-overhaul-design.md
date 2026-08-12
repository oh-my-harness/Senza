# Senza UX 系统性提升设计

> 日期: 2026-08-12
> 状态: Draft
> 范围: Senza SDK 全量 UX 提升（错误体验、Pythonic 便利层、可调试性、API 组织、异步支持）

---

## 1. 背景

Senza 是 oh-my-harness Rust runtime 的 Python SDK（PyO3 构建），定位为生产级 Agent 运行时。底层 runtime 闭源，用户只能通过 Senza Python API 接触系统能力。

### 核心矛盾

闭源 runtime + Python SDK = 黑盒问题。用户遇到非预期行为时，不能读 Rust 源码理解原因。这是 Senza 与 LangGraph/CrewAI/AutoGen 最本质的体验差距——那些框架用户可以直接跳进源码看个究竟。Senza 必须用其他方式补偿这个差距。

### 现状诊断

从代码审查中提取的五个结构性问题：

1. **错误体验**：只有 `RustPanicError`（panic）+ `PyRuntimeError`（其他一切）。runtime 侧已有完善的 typed enum（`thiserror::Error`），但 Senza 绑定层通过 `e.to_string()` 压成字符串，类型信息全部丢失。
2. **Python 层太薄**：`__init__.py` 仅 156 行。`create_tool` 要求 `json.dumps()` 而非 dict，tool 返回值结构冗长，没有从普通函数创建 tool 的快捷方式。
3. **可调试性**：tracing→Python logging 桥接存在但默认 WARN 级别；session viewer 是事后查看；workflow 卡住时缺少实时内省手段。
4. **API 扁平化**：209 个签名堆在一个命名空间，没有分组，认知负担重。
5. **异步缺口**：`WorkflowEngine.run()` 只有同步阻塞版本（缺口表 P2 待做）。

### 约束

- runtime 改动不受限（只要设计需要，可以改）
- 完全接受破坏性变更（Senza 还在早期，趁现在把 API 设计对）
- 实现策略：混合方案——每层做它最擅长的事

---

## 2. 架构决策：混合方案

| 方向 | 实现层 | 理由 |
|------|--------|------|
| A. 错误 | Rust（runtime 暴露 typed enum）→ PyO3 映射为 Python 异常类 | 字符串匹配不可接受，类型安全是根本 |
| B. 便利 | Python wrapper | 迭代快、灵活、用户体验问题不需要编译 Rust |
| C. 调试 | Rust（runtime 补 tracing span）+ Python（默认日志配置、内省 helper） | span 在 Rust 侧补，配置和呈现是 Python 侧 |
| D. 组织 | Python 子模块 | 纯 Python 机制，不需要改 Rust |
| E. 异步 | Python（`asyncio.to_thread`） | `run()` 底层已 async，Python 侧包装最简 |

runtime 侧改动为增量式（加 enum variant、加 tracing span），不涉及架构变更。

---

## 3. 详细设计

### 3.1 错误体验（A）

#### 3.1.1 现状

runtime 侧有完善的 typed enum（全部 `#[derive(thiserror::Error)]`）：

| Rust enum | 关键 variant | 文件 |
|-----------|-------------|------|
| `ToolError` | `InvalidArguments(String)`, `Aborted`, `Execution(String)`, `Other(anyhow)` | `llm-harness-types/src/errors.rs:58` |
| `AgentError` | `Provider(String)`, `Tool{tool_name, message}`, `FinalAnswerRejected{code, message}`, `Aborted`, `NotIdle`, `InvalidInput(String)`, `Internal(String)`, `ResourceLimitExceeded(String)`, `StreamIdle{timeout_ms}` | `llm-harness-types/src/errors.rs:74` |
| `HarnessError` | `NotIdle(HarnessPhase)`, `SkillNotFound`, `Agent(AgentError)`, `Session`, `Compaction`, `Env`, `Template` | `llm-harness-types/src/errors.rs:199` |
| `WorkflowError` | `Validation`, `AlreadyRunning`, `InvalidStatus`, `WorkflowNotFound`, `StepTimeout{id, timeout_ms}`, `StepExhausted{id, max_attempts, source}`, `StepFailed{id, source}`, `ExecutorNotFound{name}`, `StoreError`, `Factory`, `Internal`, `TaskFailed`, `Harness`, `Paused`, `Io` | `llm-harness-runtime/src/workflow/error.rs:90` |
| `TaskError` | `AuthError`, `Cancelled`, `Paused`, `BudgetExceeded{limit, spent}`, `RetriesExhausted{max}`, `Internal` | `llm-harness-runtime/src/lifecycle/task.rs:14` |
| `HarnessBuildError` | `NoProvider`, `ToolNameConflict(String)`, `NoMatchingProvider{model}` | `llm-harness-runtime/src/builder.rs:90` |
| `LlmError` | `InvalidRequest`, `Unauthorized`, `Forbidden`, `RateLimit{retry_after}`, `Overloaded{retry_after}`, `ServerError`, `Timeout`, `Stream`, `Network`, `Decode`, `Provider{code, message}` | `llm-api-adapter/src/error.rs:9` |

**问题不在 runtime——typed enum 已存在。** 问题在 Senza 绑定层：所有错误通过 `e.to_string()` 压成字符串，包成 `PyRuntimeError`。唯一的例外是 `workflow_error_to_pyerr()`（`src/runtime/pyworkflow.rs:1123`），但它只做了 `Validation→ValueError`、`NotFound→KeyError`、其余全 `RuntimeError` 的粗粒度映射。

**额外发现**：`LlmError`（`llm-api-adapter/src/error.rs`）有丰富 variant（`RateLimit{retry_after}`, `Timeout`, `Overloaded{retry_after}` 等），但在 runtime 内部被压成 `AgentError::Provider(String)`，类型信息在到达 Senza 之前已丢失。

#### 3.1.2 runtime 侧改动

**改动 1：`AgentError::Provider` 携带结构化信息**

当前 `AgentError::Provider(String)` 丢失了 `LlmError` 的 variant 信息。改为：

```rust
// llm-harness-types/src/errors.rs
pub enum AgentError {
    Provider(String),                          // 保留，向后兼容内部代码
    ProviderTyped {
        message: String,
        kind: ProviderErrorKind,               // 新增
    },
    // ... 其余不变
}

// 新增 enum
pub enum ProviderErrorKind {
    InvalidRequest,
    Unauthorized,
    Forbidden,
    RateLimit { retry_after: Option<Duration> },
    Overloaded { retry_after: Option<Duration> },
    ServerError,
    Timeout,
    Stream,
    Network,
    Decode,
    Other { code: String },
}
```

runtime 在 `loop_fn.rs` 中将 `LlmError` 映射为 `AgentError::ProviderTyped` 而非 `AgentError::Provider(e.to_string())`。

**改动 2：确保所有错误 enum 的 `pub` 可见性**

检查 `WorkflowError`、`TaskError`、`HarnessBuildError` 是否在各自 crate 的 `lib.rs` 中 re-export，使 Senza 能直接 import。

#### 3.1.3 Senza 侧改动

**`src/shared/pyerror.rs`：统一错误映射层**

```rust
use pyo3::create_exception;

// Python 异常层级
create_exception!(senza, SenzaError, PyRuntimeError);
create_exception!(senza, ProviderError, SenzaError);
create_exception!(senza, RateLimitError, ProviderError);      // 携带 retry_after
create_exception!(senza, ProviderTimeoutError, ProviderError);
create_exception!(senza, ToolError, SenzaError);
create_exception!(senza, ToolArgumentError, ToolError);
create_exception!(senza, ToolAbortedError, ToolError);
create_exception!(senza, ToolExecutionError, ToolError);
create_exception!(senza, BudgetExceededError, SenzaError);    // 携带 limit, spent
create_exception!(senza, WorkflowError, SenzaError);
create_exception!(senza, StepTimeoutError, WorkflowError);    // 携带 step_id, timeout_ms
create_exception!(senza, StepFailedError, WorkflowError);     // 携带 step_id
create_exception!(senza, WorkflowPausedError, WorkflowError);
create_exception!(senza, ValidationError, pyo3::exceptions::PyValueError);
create_exception!(senza, HarnessStateError, SenzaError);
create_exception!(senza, CompactionError, SenzaError);
create_exception!(senza, StreamIdleTimeoutError, SenzaError);
// RustPanicError 已有，保持

// 映射函数
pub fn agent_error_to_pyerr(e: AgentError) -> PyErr { ... }
pub fn harness_error_to_pyerr(e: HarnessError) -> PyErr { ... }
pub fn workflow_error_to_pyerr(e: WorkflowError) -> PyErr { ... }  // 扩展现有
pub fn task_error_to_pyerr(e: TaskError) -> PyErr { ... }
pub fn build_error_to_pyerr(e: HarnessBuildError) -> PyErr { ... }
```

**结构化属性**：每个异常携带 typed 属性，不仅消息字符串：

- `BudgetExceededError.limit: float`, `.spent: float`
- `StepTimeoutError.step_id: str`, `.timeout_ms: int`
- `RateLimitError.retry_after: float | None`
- `ToolArgumentError.tool_name: str | None`

**替换散落各处的 `PyRuntimeError::new_err(e.to_string())`**：

| 文件 | 当前模式 | 改为 |
|------|---------|------|
| `src/core/pyharness.rs:414,647,652,654,756,829,836,843` | `PyRuntimeError::new_err(e.to_string())` | `agent_error_to_pyerr(e)` 或 `harness_error_to_pyerr(e)` |
| `src/runtime/pyworkflow.rs:1123-1131` | `workflow_error_to_pyerr` 粗粒度 | 扩展为完整映射 |
| `src/core/pyagent.rs:97` | `PyRuntimeError::new_err(e.to_string())` | `agent_error_to_pyerr(e)` |
| `src/core/pytool.rs:259` | `PyRuntimeError::new_err(e.to_string())` | 保持（非 runtime 错误） |
| `src/shared/event_stream.rs:240` | `err.to_string()` | 在事件 dict 中附加 `error_type` 字段 |

**`src/lib.rs`**：注册所有新异常类到 module。

**`senza-pkg/senza/__init__.pyi`**：声明完整异常层级和属性。

#### 3.1.4 Python 侧使用示例

```python
import senza

try:
    engine.run()
except senza.BudgetExceededError as e:
    print(f"Budget exceeded: spent ${e.spent:.2f} of ${e.limit:.2f}")
except senza.StepTimeoutError as e:
    print(f"Step '{e.step_id}' timed out after {e.timeout_ms}ms")
except senza.RateLimitError as e:
    if e.retry_after:
        print(f"Rate limited, retry after {e.retry_after}s")
except senza.WorkflowError as e:
    print(f"Workflow failed: {e}")
```

---

### 3.2 Pythonic 便利层（B）

#### 3.2.1 现状痛点

```python
import json

# Tool 创建：手动 json.dumps + 冗长返回结构
tool = senza.create_tool(
    name="search",
    description="Search the web",
    parameters_schema=json.dumps({
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }),
    callback=lambda args, ctx: {
        "content": [{"type": "text", "text": f"Results for {args['query']}"}],
        "terminate": False,
    },
)

# 事件消费：手动 for 循环 + 类型判断
events = harness.prompt_and_collect("Hello", timeout_ms=30000)
text = ""
for event in events:
    if event["type"] == "text_delta":
        text += event.get("text", "")
```

#### 3.2.2 Rust 侧改动（PyO3 绑定层）

**`parameters_schema` 接受 `dict | str`**：

`src/lib.rs` 的 `create_tool` 函数：传入 dict 时内部 `serde_json::to_string`，传入 str 时保持现状。使用 PyO3 的 `extract` 尝试两种类型。

**callback 返回值宽容化**：

`src/core/pytool.rs` 的 callback 调用路径上，接受三种返回：
- `str` → 自动包装为 `{"content": [{"type": "text", "text": <str>}], "terminate": false}`
- `dict` 含 `content` key → 透传（向后兼容）
- `dict` 不含 `content` key → 包装为 `{"content": [{"type": "text", "text": json.dumps(<dict>)}], "terminate": false}`

#### 3.2.3 Python 侧改动

**`@senza.tool` 装饰器**——从类型注解自动推导 JSON Schema：

```python
@senza.tool
def search(query: str, limit: int = 10) -> str:
    """Search the web."""
    return f"Results for {query} (top {limit})"
```

实现：Python 标准库 `typing.get_type_hints()` + 类型映射表：

| Python 类型 | JSON Schema type |
|-------------|-----------------|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list` | `array` |
| `dict` | `object` |

docstring 作为 description。有默认值的参数标为 optional（不在 `required` 中）。`async def` 自动检测，走底层已有的 async 路径。

**`senza.tool()` 函数形式**（不想用装饰器时）：

```python
tool = senza.tool(
    name="search",
    description="Search the web",
    parameters={"query": {"type": "string"}},  # dict，不用 json.dumps
    callback=lambda args: f"Results for {args['query']}",  # str 返回
)
```

**`senza.extract_text(events)` helper**：

```python
text = senza.extract_text(events)  # 一行替代 for 循环
```

从事件列表中提取所有 `text_delta` 事件的 `text` 字段拼接。

#### 3.2.4 不做的事

- 不改 builder 链（已够 Pythonic）
- 不自动推导 async tool（底层已支持，`@senza.tool` 检测 `async def` 即可）
- 不引入 "从函数签名推导 tool" 之外的高层抽象（YAGNI）

#### 3.2.5 改动范围

| 文件 | 改动 |
|------|------|
| Senza `src/lib.rs` | `create_tool` 的 `parameters_schema` 参数接受 dict |
| Senza `src/core/pytool.rs` | callback 返回值宽容化 |
| Senza `senza-pkg/senza/__init__.py` | `tool` 装饰器、`extract_text` helper |
| Senza `senza-pkg/senza/__init__.pyi` | stub 更新 |
| runtime | 零改动 |

---

### 3.3 可调试性（C）

#### 3.3.1 现状

三个组件已存在但各自不足：

1. **tracing → Python logging 桥接**（`src/shared/pylogging.rs`）：默认级别 WARN——太晚。用户不知道 `SENZA_LOG=senza=debug`。
2. **事件流**（`src/shared/event_stream.rs`）：Agent 事件丰富（15+ 类型），Workflow 事件只有 6 种，缺少 step 内部细节。
3. **session viewer**（`senza-pkg/senza/viewer.py`）：事后查看，不能实时内省。

#### 3.3.2 默认日志体验

**默认级别 WARN→INFO**（`src/shared/pylogging.rs`）：

INFO 级别下用户能看到：workflow step 开始/结束、tool 调用、provider 请求、compaction 触发。

**Python 侧便利函数**（`senza-pkg/senza/__init__.py`）：

```python
senza.enable_debug()     # logging.getLogger("senza").setLevel(DEBUG)
senza.disable_debug()    # logging.getLogger("senza").setLevel(INFO)
```

纯 Python，不改 Rust。

#### 3.3.3 runtime 侧 tracing span 补全

在 runtime 关键路径补 `#[tracing::instrument]`，预期需要检查和补充的点：

- `WorkflowEngine::run()` — 是否有 instrument
- 每个 step 执行 — `step_started`/`step_finished` 事件已有，tracing span 可能缺失
- `AgentHarness::prompt()` — provider 请求的 span（请求/响应耗时、token 数）
- Tool 执行 — `tool_call_start`/`tool_call_end` 事件已有，tracing span 可能缺失
- Compaction 触发和完成

增量式添加，不改逻辑。需要逐文件检查后补充。

#### 3.3.4 实时内省 helper

**`harness.inspect()` → dict**（Python 侧聚合现有方法）：

```python
{
    "phase": "idle",
    "turn_index": 3,
    "message_count": 7,
    "usage": {"total_input_tokens": 1234, "total_output_tokens": 567},
    "active_tools": ["search", "write"],
    "queued_messages": 0,
}
```

当前用户要拼凑 `harness.usage()` + `harness.get_messages()` + `harness.has_queued_messages()` 等多个调用。

**`engine.inspect()` → dict**：

```python
{
    "state": "running",
    "current_step": "reviewer",
    "step_count": 3,
    "total_cost": 0.0234,
    "retry_count": 0,
}
```

当前要拼凑 `engine.state()` + `engine.current_step()` + `engine.step_history()` + `engine.total_cost()`。

两个 `inspect()` 在 Python 侧实现（聚合现有方法调用），不需要改 Rust。

#### 3.3.5 不做的事

- 不做实时 Web dashboard（session viewer 已覆盖事后查看）
- 不做 workflow 事件流扩展（增加事件类型需要 runtime 改动且影响序列化格式，收益不如 tracing + inspect()）

#### 3.3.6 改动范围

| 文件 | 改动 |
|------|------|
| Senza `src/shared/pylogging.rs` | 默认级别 WARN→INFO |
| Senza `senza-pkg/senza/__init__.py` | `enable_debug()`, `disable_debug()`, `inspect()` |
| Senza `senza-pkg/senza/__init__.pyi` | stub 更新 |
| runtime | 关键路径补 `#[tracing::instrument]`（增量式） |

---

### 3.4 API 组织（D）

#### 3.4.1 现状

209 个签名全部平铺在 `senza` 命名空间。

#### 3.4.2 Python 子模块分组

在 `senza-pkg/senza/__init__.py` 中建子模块，作为命名空间分组。底层 PyO3 函数不动——子模块只是 re-export。

```python
# senza.providers
senza.providers.openai(api_key=...)           # = create_openai_provider
senza.providers.anthropic(api_key=...)        # = create_anthropic_provider

# senza.hooks  (11 个)
senza.hooks.before_turn(cb)                   # = create_before_turn_hook
senza.hooks.after_turn(cb)                    # = create_after_turn_hook
senza.hooks.should_stop(cb)                   # = create_should_stop_hook
# ...

# senza.strategy  (12 个)
senza.strategy.safety_defaults()              # = create_safety_defaults_plugin
senza.strategy.loop_safety(config=None)       # = create_loop_safety_plugin
senza.strategy.memory_defense()               # = create_memory_defense_plugin
# ...

# senza.knowledge
senza.knowledge.local_source(path=...)        # = create_local_knowledge_source
senza.knowledge.plugin(sources=...)           # = create_knowledge_plugin
senza.knowledge.memory_store(...)             # = create_in_memory_store

# senza.infra
senza.infra.jsonl_audit_sink(path=...)        # 对应 JsonlAuditSink
senza.infra.seatbelt_sandbox(config=None)     # = create_seatbelt_sandbox

# senza.rules
senza.rules.chain()                           # = create_rule_chain()
senza.rules.contains(allowed)                 # = create_contains_predicate
```

**命名简化**：子模块中去掉 `create_` 前缀和 `_plugin`/`_hook`/`_provider` 后缀——上下文已由子模块名提供。`create_openai_provider` → `senza.providers.openai`，信息零损失，噪音减半。

#### 3.4.3 顶层保留高频 API

最高频 API 保留在顶层：

```python
senza.HarnessBuilder       # 保留
senza.AgentHarness         # 保留
senza.WorkflowEngine       # 保留
senza.tool                 # Section B 装饰器
senza.create_tool          # 保留
senza.create_plugin        # 保留
senza.create_judge         # 保留
senza.stream_prompt        # 保留
senza.stream_events        # 保留
senza.stream_run           # 保留
senza.extract_text         # Section B helper
```

其余低频 API 只通过子模块暴露，从顶层移除。这是 breaking change。

#### 3.4.4 决策树文档

在 `docs/` 新增决策树文档，回答"什么时候用什么"：

```
要做什么？
├── 单轮对话 / 工具调用
│   → HarnessBuilder + AgentHarness
├── 多步流程 / 条素分支
│   → WorkflowEngine
├── 需要安全防护？
│   ├── bash 黑名单 + 路径穿越 → strategy.safety_defaults()
│   ├── 死循环 / 重复断路 → strategy.loop_safety()
│   └── 注入检测 → strategy.injection_filter()
├── 需要知识 / 记忆？
│   ├── 本地文档 RAG → knowledge.local_source() + knowledge.plugin()
│   ├── 长期记忆 → knowledge.memory_store() + knowledge.memory_plugin()
│   └── 会话历史召回 → knowledge.session_recall()
├── 需要预算管控？
│   → builder.budget(limit) + builder.pricing(provider)
└── 需要审计 / 沙箱？
    ├── 审计日志 → infra.jsonl_audit_sink()
    └── 命令沙箱 → infra.seatbelt_sandbox() / infra.bwrap_sandbox()
```

#### 3.4.5 不做的事

- 不做 PyO3 submodule（Python re-export 完全够用）
- 不按 crate 结构分组（用户不关心 Rust crate 划分，按用途分组更直观）

#### 3.4.6 改动范围

| 文件 | 改动 |
|------|------|
| Senza `senza-pkg/senza/__init__.py` | 新增子模块 re-export，顶层移除低频 API |
| Senza `senza-pkg/senza/__init__.pyi` | stub 同步重组 |
| Senza `docs/` | 新增决策树文档 |
| runtime | 零改动 |

---

### 3.5 异步支持（E）

#### 3.5.1 现状

- `WorkflowEngine.run()` 只有同步阻塞版本（缺口表 P2 待做）
- `AgentHarness` 已有 `stream_prompt`/`stream_events`/`stream_run` 三个 async generator
- `prompt_and_collect` / `prompt` 只有同步版本

#### 3.5.2 设计

选择 `asyncio.to_thread` 方案而非 PyO3 native async method。理由：

1. workflow `run()` 是长流程编排，不是高频调用，占一个线程可接受
2. `stream_run` 已存在——需要事件流的用户用 `stream_run`
3. `run_async` 的主要场景是"在 async 应用里不想阻塞 event loop"，`to_thread` 恰好解决
4. PyO3 native async method 需要处理 GIL/tokio/asyncio 三方交互，复杂度不对等

**`WorkflowEngine.run_async()`**：

```python
async def run_async(self, timeout_ms: int = 300000) -> list[dict]:
    """Async version of run(). Does not block the event loop."""
    return await asyncio.to_thread(self.run)
```

**`AgentHarness.prompt_async()`**：

```python
async def prompt_async(self, text: str, timeout_ms: int = 30000) -> list[dict]:
    """Async version of prompt_and_collect()."""
    return await asyncio.to_thread(self.prompt_and_collect, text, timeout_ms)
```

已有 `stream_prompt` 覆盖流式 async 场景，`prompt_async` 补齐非流式 async 场景。

#### 3.5.3 事件循环桥接文档

`senza.set_event_loop(loop)` 存在但文档不足。在 `docs/api-reference.md` 中补充：async 应用中使用 Senza 时，async tool/hook 回调需要共享事件循环的说明。

#### 3.5.4 不做的事

- 不做 PyO3 native async method（`to_thread` 方案足够）
- 不做 `collect_until_settled` 的 async 版（`stream_events` 已覆盖）
- 不做 async `restore()`（`restore()` 是瞬时操作，不阻塞）

#### 3.5.5 改动范围

| 文件 | 改动 |
|------|------|
| Senza `senza-pkg/senza/__init__.py` | `run_async`, `prompt_async` |
| Senza `senza-pkg/senza/__init__.pyi` | stub |
| Senza `docs/api-reference.md` | 异步用法说明 + `set_event_loop` 文档 |
| runtime | 零改动 |

---

## 4. 依赖与顺序

五个方向的改动依赖关系：

```
A (错误) ────────────── 独立，可先做
B (便利层) ──────────── 独立，可先做
C (调试) ────────────── 独立，可先做
D (API 组织) ────────── 依赖 B（子模块需要 re-export B 的新函数）
E (异步) ────────────── 独立，可先做
```

A、B、C、E 可以并行推进。D 应在 B 完成后做（因为子模块需要 re-export `senza.tool`、`senza.extract_text` 等 B 新增的函数）。

runtime 侧改动（A 的 `AgentError::ProviderTyped` + C 的 tracing span）可以与 Senza 侧改动并行，最后统一更新 `Cargo.toml` 的 rev pin。

---

## 5. 改动总览

### Senza 仓库

| 文件 | A | B | C | D | E |
|------|---|---|---|---|---|
| `src/shared/pyerror.rs` | ✅ 新增映射层 + 异常注册 | | | | |
| `src/shared/pylogging.rs` | | | ✅ 默认 WARN→INFO | | |
| `src/core/pyharness.rs` | ✅ 替换错误映射 | | | | |
| `src/core/pytool.rs` | | ✅ 返回值宽容化 | | | |
| `src/runtime/pyworkflow.rs` | ✅ 扩展错误映射 | | | | |
| `src/core/pyagent.rs` | ✅ 替换错误映射 | | | | |
| `src/shared/event_stream.rs` | ✅ 附加 error_type | | | | |
| `src/lib.rs` | ✅ 注册异常类 | | | | |
| `senza-pkg/senza/__init__.py` | | ✅ tool 装饰器 + extract_text | ✅ enable_debug + inspect | ✅ 子模块分组 | ✅ run_async + prompt_async |
| `senza-pkg/senza/__init__.pyi` | ✅ 异常层级 | ✅ tool/extract_text | ✅ inspect/debug | ✅ 子模块 stub | ✅ async methods |
| `docs/api-reference.md` | ✅ 异常文档 | | | | ✅ 异步文档 |
| `docs/` 决策树 | | | | ✅ 新增 | |
| `examples/` | ✅ 错误处理示例 | ✅ tool 装饰器示例 | | ✅ 子模块用法示例 | ✅ async 示例 |

### runtime 仓库

| 文件 | 改动 | 方向 |
|------|------|------|
| `llm-harness-types/src/errors.rs` | 新增 `ProviderErrorKind` enum + `AgentError::ProviderTyped` variant | A |
| `llm-harness-agent/src/loop_fn.rs`（或等价文件） | `LlmError` → `AgentError::ProviderTyped` 映射 | A |
| `llm-harness-runtime/src/workflow/` | 关键路径补 `#[tracing::instrument]` | C |
| `llm-harness-agent/src/` | 关键路径补 `#[tracing::instrument]` | C |

---

## 6. 验证计划

| 方向 | 验证方式 |
|------|---------|
| A | 测试：触发每种错误类型，assert Python 异常类型和属性。覆盖 `BudgetExceededError.limit/.spent`、`StepTimeoutError.step_id`、`RateLimitError.retry_after` |
| B | 测试：`@senza.tool` 装饰器从类型注解生成正确 schema；`extract_text` 正确拼接；dict schema 和 str schema 都接受 |
| C | 测试：`enable_debug()` 后 logging 级别为 DEBUG；`inspect()` 返回正确快照 |
| D | 测试：子模块导入正确；顶层低频 API 已移除（ImportError） |
| E | 测试：`run_async` 不阻塞 event loop（`asyncio.run` 内可并发执行其他 task） |
| 全局 | `scripts/check_stubs.py` 通过（stub 与运行时签名一致） |
| 全局 | 现有 342 个测试通过（适配 breaking changes 后） |
