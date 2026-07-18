# Senza (森座) — Python SDK 设计文档

> Senza = "森座" — oh-my-harness runtime 的 Python 发行包。
> 本仓库从 `llm-harness-py-wheels` 改名为 Senza，定位为 **runtime + agent 两层能力的 Python 分发与示例仓库**。

---

> **spawn 机制更新**（2026-07-14）
>
> runtime commit `2baeda7` 重构了 spawn 模块。旧 `SyncSpawnAgentTool`（同步阻塞）+ peer.rs + async_spawn.rs 多模块设计已删除，替换为 MessageBus 统一架构 + 7 个异步通信 tool。本文档 §5/§7/§9 已同步更新。
>
> **架构变更说明**（2026-07-13）
>
> **CFFI 已全删，替换为 PyO3。** 旧 `llm-harness-ffi` crate（`extern "C"` + cffi `binding.py`）已从 runtime 仓库移除，替换为 `llm-harness-py` crate（PyO3 0.29，`#[pyclass]` + `#[pyfunction]`）。本文档已据此完全重写。
>
> PyO3 的优势：
> - 原生 Python 类型，无需手动 cdef / JSON 序列化
> - 原生 `#[pyclass]`，Python 侧直接 `import`，有真正的类方法
> - 异步回调支持（`async def` tool/hook/judge/executor）
> - maturin 构建，abi3-py39 一个 wheel 覆盖 Python 3.9–3.14+
> - 编译时类型安全（Rust trait ↔ Python class）

---

## 1. 层级定位

oh-my-harness 分三层，依赖只能向下：

```
┌──────────────────────────────────────────────┐
│  agent 层 (eda-agent / coding-agent / ...)    │
│  领域专属工具 + system prompt + CLI           │
└──────────────────┬───────────────────────────┘
                   │ 依赖
┌──────────────────▼───────────────────────────┐
│  runtime 层 (llm-harness-runtime, 14 crate)   │
│  WorkflowEngine + AgentHarness + TaskStore    │
│  + Sandbox + ToolRegistry + Budget            │
│  + llm-harness-py (PyO3 SDK)                  │
└──────────────────┬───────────────────────────┘
                   │ 依赖
┌──────────────────▼───────────────────────────┐
│  adapter 层 (llm-api-adapter)                 │
│  多 provider wire 格式归一化                  │
└──────────────────────────────────────────────┘
```

### Python SDK 暴露的类与函数

PyO3 module 名：`senza`（已从 `llm_harness_py` 改名）。

#### Agent 层

| Python 类 / 函数 | Rust 来源 | 说明 |
|------------------|-----------|------|
| `HarnessBuilder` | `HarnessBuilder` (`llm-harness-runtime`) | Fluent API 构建 AgentHarness |
| `AgentHarness` | `AgentHarness` (`llm-harness-agent`) | 单轮 LLM prompt → streaming events；tool calling；abort |
| `create_tool()` | `PyTool` → `Tool` trait | 从 Python callable 创建 Tool（支持 sync/async） |
| `create_sync_tool()` | 同上（别名） | 显式同步 tool |
| `create_openai_provider()` | `OpenAIProvider` | 创建 OpenAI 兼容 provider |
| `create_anthropic_provider()` | `AnthropicProvider` | 创建 Anthropic provider |
| `create_plugin()` | `PyPlugin` → `Plugin` trait | 从 tools + hooks 组装 plugin |
| `create_event_channel()` | `EventStream` + `WaitForExternalEventTool` | Human-in-the-loop 事件通道 |

#### Runtime 层

| Python 类 / 函数 | Rust 来源 | 说明 |
|------------------|-----------|------|
| `WorkflowEngine` | `WorkflowEngine` (`llm-harness-runtime`) | 多步 workflow 编排；条件路由；崩溃恢复；事件流 |
| `create_judge()` | `PyJudge` → `StepTransitionJudge` trait | 从 Python callable 创建 judge |
| `create_executor()` | `PyExecutor` → `StepExecutor` trait | 从 Python callable 创建 executor |
| `Judge` / `Executor` | wrapper class | 持有已创建的 judge/executor 供注册 |

#### Hooks（11 种）

| 函数 | Hook 类型 | callback 签名 |
|------|-----------|--------------|
| `create_before_turn_hook()` | `BeforeTurnHook` | `callback(ctx: dict) -> None` |
| `create_after_turn_hook()` | `AfterTurnHook` | `callback(ctx: dict) -> None` |
| `create_before_run_hook()` | `BeforeRunHook` | `callback(ctx: dict) -> None` |
| `create_after_provider_response_hook()` | `AfterProviderResponseHook` | `callback(ctx: dict) -> None` |
| `create_before_provider_request_hook()` | `BeforeProviderRequestHook` | `callback(ctx: dict) -> None` |
| `create_before_tool_call_hook()` | `BeforeToolCallHook` | `callback(ctx: dict) -> str \| None` |
| `create_after_tool_call_hook()` | `AfterToolCallHook` | `callback(ctx: dict) -> str \| dict` |
| `create_should_stop_hook()` | `ShouldStopHook` | `callback(ctx: dict) -> bool` |
| `create_before_compact_hook()` | `BeforeCompactHook` | `callback(ctx: dict) -> str \| dict` |
| `create_transform_context_hook()` | `TransformContextHook` | `callback(ctx: dict) -> dict` |
| `create_prepare_next_turn_hook()` | `PrepareNextTurnHook` | `callback(ctx: dict) -> dict \| None` |

所有 hook 均支持 `async def` 回调。

---

## 2. 当前状态

### 已有

- **PyO3 crate** (`src/`)：11 个源文件，~1300 行 Rust 代码
  - `lib.rs` — module 入口，注册所有 class + function
  - `pyharness.rs` — `AgentHarness` Python 类
  - `pyworkflow.rs` — `WorkflowEngine` Python 类 + judge/executor wrapper
  - `pybuilder.rs` — `HarnessBuilder` Python 类
  - `pytool.rs` — `create_tool()` / Tool trait 实现
  - `pyprovider.rs` — `create_openai_provider()` / `create_anthropic_provider()`
  - `pyhooks.rs` — 11 种 hook 创建函数
  - `pyplugin.rs` — `create_plugin()`
  - `pyeventstream.rs` — `create_event_channel()` + human-in-the-loop
  - `pyagent.rs` — `Agent` 类（仅 test-utils feature）
  - `event_stream.rs` — Agent 事件转 Python dict
  - `value_conv.rs` — Python ↔ serde_json::Value 转换
- **maturin 构建**：`pyproject.toml` 配置 `abi3-py39`，一个 wheel 覆盖 Python 3.9–3.14+
- **测试**：22 个测试文件（3 个 Rust 集成测试 + 19 个 Python 测试）
- **stub 验证**：`scripts/check_stubs.py` 对比 `.pyi` 与运行时 `__text_signature__`，112 个签名零偏差

### 缺口（2026-07-14 更新）

| ID | 问题 | 严重度 | 状态 |
|----|------|--------|------|
| — | ~~`WorkflowEngine` 缺 `restore()` Python 包装~~ | ~~**P0**~~ | ✅ 已暴露 |
| — | ~~PyO3 crate 无 docstring~~ PyO3 0.29 自动导出 doc comments 为 `__doc__`，全部已覆盖 | ~~**P0**~~ | ✅ 已验证 |
| — | 无自动化 wheel 构建 CI | **P0** | ✅ `build-wheel.yml` 已建 |
| — | ~~`WorkflowEngine` 缺 `state()`/`pause()`/`resume()`/`cancel()`/`checkpoint()`/`total_cost()`~~ | ~~P1~~ | ✅ 已暴露 |
| — | ~~`WorkflowEngine` 缺 `current_step()`/`step_history()`/`with_task_store()`/`with_max_steps()`/`with_max_retries()`~~ | ~~P2~~ | ✅ 已暴露 |
| — | ~~`AgentHarness` 缺动态配置方法（set_model/set_system_prompt/set_temperature/set_thinking_level/set_tools 等）~~ | ~~P1~~ | ✅ 已暴露 |
| — | ~~`AgentHarness` 缺 steering 方法（steer/follow_up/next_turn/continue_run）~~ | ~~P1~~ | ✅ 已暴露 |
| — | ~~`AgentHarness` 缺 usage/reset_usage/wait_for_idle/wait_for_settled~~ | ~~P1~~ | ✅ 已暴露 |
| — | ~~`AgentHarness` 缺 context manager~~ `__enter__`/`__exit__` 已添加 | ~~P1~~ | ✅ 已实现 |
| — | ~~eda-agent-py 仍引用旧 `llm_harness_sdk`~~ **已迁移到 PyO3**（commit efba9a1） | ✅ | ✅ |
| — | ~~`ShellExecutor` / `HttpCallExecutor` 未暴露~~ `create_shell_executor()` / `create_http_executor()` 已添加（不自动注册，安全设计） | ~~P2~~ | ✅ 已实现 |
| — | `WorkflowEngine.run()` 是同步阻塞，无 async 版本 | P2 | ❌ 待做 |
| — | ~~compaction 配置、active_tools、queue 清除、session/branch 管理~~ | ~~P2~~ | ✅ 已完成 |
| — | ~~PyO3 module 名为 `llm_harness_py`，需改名为 `senza`~~ | ~~P0~~ | ✅ 已完成 |
| — | ~~Senza 仓库缺 `pyproject.toml`，无法 `pip install senza-sdk`~~ | ~~P0~~ | ✅ 已完成 |
| — | ~~wheel 从未成功构建~~ | ~~P0~~ | ✅ 已完成 |
| — | ~~HarnessBuilder 缺 budget/pricing/skills/compaction_model/should_stop_hook/hooks/retry/model_info/final_answer_mode/stream_options/queue_capacity/disable_skill_read_tool~~ | ~~P1~~ | ✅ 已暴露 |
| — | ~~PricingProvider 未暴露~~ `create_pricing_provider(dict)` / `create_pricing_provider_callback(cb)` 已添加 | ~~P1~~ | ✅ 已实现 |
| — | ~~BudgetExceededHook 未暴露~~ `create_budget_exceeded_hook(cb)` + `builder.budget()` 已添加 | ~~P1~~ | ✅ 已实现 |
| — | ~~Rules 审批系统未暴露~~ `create_*_predicate` + `RuleChainBuilder` + `create_rule_approval_hook()` 已添加 | ~~P1~~ | ✅ 已实现 |
| — | ~~Skills 加载未暴露~~ `load_skills(path)` + `builder.skill()/skills()` 已添加 | ~~P2~~ | ✅ 已实现 |
| — | stub 数从 112 增至 138 | — | ✅ 已验证 |

---

## 3. Senza 仓库结构

```
senza/                           # 本仓库 (github.com/oh-my-harness/Senza)
├── Cargo.toml                   # 独立 crate，git 依赖 runtime（rev=PLACEHOLDER）
├── build.rs                     # PyO3 build script
├── pyproject.toml               # package name = "senza-sdk"，maturin 后端
├── README.md                    # 面向用户：pip install senza-sdk + 快速上手
├── DEVELOPMENT.md               # 面向贡献者：dev_setup.sh + 本地测试
├── SENZA_DESIGN.md              # 本文档
├── src/                         # ← PyO3 crate 源码（从 runtime 仓库迁入）
│   ├── lib.rs                   # module 入口
│   ├── pyharness.rs             # AgentHarness
│   ├── pyworkflow.rs            # WorkflowEngine
│   ├── pybuilder.rs             # HarnessBuilder
│   ├── pytool.rs                # create_tool / Tool trait
│   ├── pyprovider.rs            # provider 创建
│   ├── pyhooks.rs               # 11 种 hook
│   ├── pyplugin.rs              # create_plugin
│   ├── pyeventstream.rs         # 事件通道
│   ├── pyagent.rs               # Agent 类（test-utils only）
│   ├── event_stream.rs          # 事件转 dict
│   └── value_conv.rs            # Python ↔ Value 转换
├── senza-pkg/
│   ├── runtime.lock             # runtime crate 固定 SHA（唯一真实来源）
│   └── senza/
│       └── __init__.pyi         # 手写 .pyi type stubs（112 签名）
├── tests/                       # 3 个 .rs 集成测试 + 19 个 .py 测试
├── scripts/
│   ├── build_wheel.sh           # 注入 SHA → maturin build → 恢复 Cargo.toml
│   ├── dev_setup.sh             # 建 venv → 安装 maturin/pytest → 构建+安装 wheel
│   └── check_stubs.py           # .pyi vs 运行时 __text_signature__ 验证
├── .github/
│   └── workflows/
│       └── build-wheel.yml      # CI：注入 rev → maturin build → stub 检查 → PyPI
├── skills/                      # AI 助手过程性知识包（3 个 SKILL.md）
│   ├── senza-agent/
│   ├── senza-workflow/
│   └── senza-advanced/
└── examples/
    ├── agent/                   # agent 层示例（HarnessBuilder + AgentHarness）
    │   ├── 01_basic_prompt.py
    │   ├── 02_tool_calling.py
    │   ├── 03_streaming.py
    │   ├── 04_dynamic_config.py
    │   └── 05_multi_provider.py
    └── runtime/                 # runtime 层示例（WorkflowEngine）
        ├── 01_linear_workflow.py
        ├── 02_conditional_routing.py
        ├── 03_executor_steps.py
        ├── 04_crash_recovery.py
        ├── 05_pause_cancel.py
        ├── 06_human_in_the_loop.py
        ├── 07_shell_executor.py
        ├── 08_http_executor.py
        └── 09_composite_judge.py
```

### 与旧 cffi 架构的区别

| 项 | cffi (旧) | PyO3 (新) |
|----|-----------|-----------|
| Python binding | `binding.py` 手写 cdef + JSON 序列化 | `#[pyclass]` + `#[pyfunction]` 自动生成 |
| 数据传递 | 所有参数/返回值 JSON 序列化 | 原生 Python 类型（dict/list/str/int/bool） |
| 构建 | `cargo build` + 手动 copy `.so` + `setup.py` | `maturin build` 一步到位 |
| Wheel | 平台特定 + Python 版本特定 | `abi3-py39` 一个 wheel 覆盖 3.9–3.14+ |
| 异步 | 不支持 async callback | 支持 `async def` tool/hook/judge/executor |
| Type safety | cdef 手动维护，易错 | 编译时 Rust trait 约束 |
| Senza 仓库职责 | 打包 `.so` + `binding.py` + 高层封装 | PyO3 crate 源码 + wheel 构建 + examples + skills |

### 包名

- PyPI 包名：`senza-sdk`（import 名 `senza`）
- import 名：`senza`（PEP 8 小写）
- 用户代码：`from senza import HarnessBuilder, AgentHarness, WorkflowEngine, ...`

---

## 4. API 参考

### 4.1 Provider 创建

```python
import senza

# OpenAI 兼容（含 DeepSeek、本地模型等）
provider = senza.create_openai_provider(
    api_key="sk-...",
    base_url="https://api.openai.com",       # 可选，空则用默认
    parse_reasoning_content=True,              # 解析 DeepSeek reasoning_content
    tolerant_keepalive=True,                   # 容忍 keepalive 消息
)

# Anthropic
provider = senza.create_anthropic_provider(
    api_key="sk-ant-...",
    base_url="https://api.anthropic.com",    # 可选
)
```

### 4.2 HarnessBuilder + AgentHarness（Agent 层）

```python
# 创建 harness
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("gpt-*", provider)
    .system_prompt("You are a helpful assistant.")
    .max_tokens(1024)
    .temperature(0.7)
    .tool(my_tool)           # create_tool() 创建的 Tool
    .plugin(my_plugin)       # create_plugin() 创建的 Plugin
    .build()
)

# 发送 prompt
harness.prompt("Hello!")

# 收集事件直到 settled
events = harness.prompt_and_collect("Hello!", timeout_ms=30000)
for event in events:
    print(event["type"], event.get("text", ""))

# 或逐个迭代事件
for event in harness.events(timeout_ms=5000):
    if event["type"] in ("settled", "aborted"):
        break
    print(event)

# 获取状态
print(harness.phase())          # "idle" / "turning" / "compacting" / "branching"
print(harness.message_count())  # 消息数

# 取消
harness.abort()
```

**AgentHarness 方法**：

| 方法 | 签名 | 说明 |
|------|------|------|
| `prompt_and_collect(text, timeout_ms=30000)` | `str, int → list[dict]` | 发送 prompt 并收集事件（推荐用法） |
| `prompt(text)` | `str → None` | 同步执行 prompt，阻塞直到完成（需配合线程收集事件） |
| `events(timeout_ms=5000)` | `int → Iterator[dict]` | 返回事件迭代器 |
| `collect_until_settled(timeout_ms=30000)` | `int → list[dict]` | 收集事件直到 settled/aborted |
| `message_count()` | `→ int` | 当前消息数 |
| `phase()` | `→ str` | "idle"/"turning"/"compacting"/"branching" |
| `abort()` | `→ None` | 取消当前 prompt |

### 4.3 Tool 创建

```python
import json

# 同步 tool
my_tool = senza.create_tool(
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

# 异步 tool
async def async_search(args, ctx):
    results = await some_async_api(args["query"])
    return {"content": [{"type": "text", "text": results}], "terminate": False}

my_async_tool = senza.create_tool(
    name="async_search",
    description="Async web search",
    parameters_schema=json.dumps({...}),
    callback=async_search,
)
```

### 4.4 WorkflowEngine（Runtime 层）

```python
# 创建 workflow dict
workflow = {
    "entry_step": "step1",
    "steps": [
        # LLM step
        {"id": "step1", "name": "分析", "prompt": "分析数据", "allowed_tools": ["search"]},
        # Executor step
        {"id": "step2", "name": "转换", "executor": "transform", "executor_config": {"fields": {"result": "/output"}}},
    ],
    "edges": [
        {"from": "step1", "to": "step2"},
        {"from": "step2", "to": "step1", "condition": {"op": "eq", "pointer": "/status", "value": "retry"}},
    ],
}

# 创建 judge
judge = senza.create_judge(lambda ctx: "to:step2" if ctx.get("structured", {}).get("ok") else "retry")

# 创建 executor
executor = senza.create_executor(lambda ctx: {"output": "done", "structured": {"status": "ok"}})

# 创建 engine
engine = (
    senza.WorkflowEngine(workflow, provider, "gpt-4o", judge)
    .with_tool(my_tool)
    .with_executor("transform", executor)
    .with_hooks([before_turn_hook, after_turn_hook])
    .with_step_plugin("step1", my_plugin)
    .with_max_tokens(4096)
)

# 设置 context 变量
engine.set_context_variable("user_input", "hello")
engine.set_context_variable("count", 42)

# 订阅事件流
event_iter = engine.subscribe(timeout_ms=5000)

# 运行
engine.run()

# 获取 task ID
print(engine.task_id())  # "task-<uuid>"
```

**WorkflowEngine 方法**：

| 方法 | 签名 | 说明 |
|------|------|------|
| `__new__(workflow_dict, provider, model, judge, session_base_dir="sessions")` | — | 构造引擎 |
| `with_tool(tool)` | `Tool → self` | 注册额外 tool（链式） |
| `with_external_tool(tool)` | `WaitForExternalEventTool → self` | 注册外部事件 tool（链式） |
| `with_executor(name, executor)` | `str, Executor → self` | 注册命名 executor（链式） |
| `with_hooks(hooks_list)` | `list[Hook] → self` | 注入 hooks（链式） |
| `with_step_plugin(step_id, plugin)` | `str, Plugin → self` | 为指定 step 注册 plugin（链式） |
| `with_max_tokens(tokens)` | `int? → self` | 设置每步最大输出 token（链式） |
| `set_context_variable(key, value)` | `str, Any → None` | 设置 workflow context 变量 |
| `run()` | `→ None` | 启动/恢复执行，阻塞直到完成 |
| `task_id()` | `→ str` | 返回 task ID（"task-<uuid>"） |
| `subscribe(timeout_ms=5000)` | `int → WorkflowEventIterator` | 订阅事件流 |

### 4.5 Judge callback

```python
def my_judge(ctx: dict) -> str:
    # ctx 包含: step_id, output, structured, step_count
    structured = ctx.get("structured") or {}
    if structured.get("status") == "ok":
        return "to:next_step"
    elif structured.get("retry_needed"):
        return "retry"
    else:
        return "fail:quality gate failed"

judge = senza.create_judge(my_judge)
```

返回值编码：
- `"to:<step_id>"` → 跳到指定步骤
- `"retry"` → 重跑当前步
- `"fail:<reason>"` → 标记流程失败
- `"abort:<reason>"` → 终止流程（正常结束）

### 4.6 Executor callback

```python
def my_executor(ctx: dict) -> dict:
    # ctx 包含: step_id, step_name, config, prev_output, context
    return {
        "output": "处理完成",
        "structured": {"status": "ok", "result": 42},
    }

executor = senza.create_executor(my_executor)
```

### 4.7 Human-in-the-loop（Event Channel）

```python
# 创建事件通道
handle, wait_tool = senza.create_event_channel("review-task")

# 注册 wait_tool 到 engine（LLM 可调用它等待外部事件）
engine = (
    senza.WorkflowEngine(workflow, provider, "gpt-4o", judge)
    .with_external_tool(wait_tool)
)

# 在另一个线程/协程中推送事件
handle.submit("审核通过", {"approved": True, "reviewer": "alice"})
```

---

## 5. Workflow JSON Schema

> 来源：`pyworkflow.rs` `dict_to_workflow()` + `model.rs`

### Workflow dict

```python
{
    "entry_step": "step1",
    "steps": [...],
    "edges": [...],
}
```

### Step

```python
# LLM step
{"id": "step1", "name": "分析", "prompt": "请分析...", "allowed_tools": ["search", "spawn_agent"]}

# Executor step
{"id": "step2", "name": "转换", "executor": "transform", "executor_config": {"fields": {"result": "/output"}}}
```

**判断逻辑**（`dict_to_workflow`）：step dict 含 `"executor"` 键 → Executor step；否则 → LLM step。

| 字段 | 类型 | LLM | Executor | 说明 |
|------|------|:---:|:--------:|------|
| `id` | str | ✅ | ✅ | 步骤唯一标识 |
| `name` | str | ✅ | ✅ | 人类可读名称 |
| `prompt` | str | ✅ | — | LLM 指令 |
| `allowed_tools` | str[] | ✅ | — | 允许的工具集（空 = 不允许任何工具） |
| `executor` | str | — | ✅ | Executor 注册键 |
| `executor_config` | dict | — | ✅ | Executor 特定配置 |

### Edge

```python
{"from": "step1", "to": "step2"}                                          # 无条件
{"from": "step1", "to": "step2", "condition": "success"}                  # label（judge 解析）
{"from": "step1", "to": "step2", "condition": {"op": "eq", "pointer": "/status", "value": "ok"}}  # 声明式
```

### ConditionExpr（`op` tag）

| op | 参数 | 语义 |
|----|------|------|
| `exists` | `pointer` | structured 中该 JSON Pointer 路径存在 |
| `missing` | `pointer` | 不存在 |
| `eq` | `pointer`, `value` | == |
| `ne` | `pointer`, `value` | != |
| `gt` / `gte` / `lt` / `lte` | `pointer`, `value`(f64) | 数值比较 |

声明式条件自动启用：如果 edges 中有 `Expr` 条件且 judge 是 NoopJudge，引擎自动替换为 `EdgeConditionJudge`。

### spawn_agent + sub-agent 通信（7 个 tool）

LLM step 的 `allowed_tools` 含 `"spawn_agent"` 时，引擎自动注册 **7 个 LLM tool**（`engine.rs:1075`）+ MessageBus + AsyncSpawnHook + IdleWatcher + AbortCascadeHook。

**架构**：MessageBus 统一事件通道，main↔sub 双向异步通信。spawn 是异步的（不阻塞），sub-agent 完成后结果自动注入 main agent 对话。

| tool | 方向 | 参数 | 说明 |
|------|------|------|------|
| `spawn_agent` | main→sub | `prompt`(必填), `context`?, `provider`? | 异步派发 sub-agent，立即返回 agent_id |
| `message_subagent` | main→sub | `to`(必填), `message`(必填) | fire-and-forget 消息 |
| `await_subagent_reply` | main waits | `from`?, `timeout`?(默认120s) | 阻塞等待 sub-agent 消息/完成 |
| `query_subagent` | main→bus | `agent_id`? | 查询状态（running/done/aborted），省略则列全部 |
| `abort_subagent` | main→sub | `agent_id`(必填) | 取消 sub-agent |
| `message_main` | sub→main | `message`(必填) | sub-agent 主动汇报 |
| `await_main_message` | sub waits | `timeout`?(默认120s) | sub-agent 等待 main 指示 |

**关键机制**：
- `MessageBus` — `register`/`send`/`wait`/`query_status`/`abort_agent`/`take_event_rx`
- `AsyncSpawnHook`（ShouldStop hook）— sub-agent 完成事件注入 main agent 对话
- `IdleWatcher` — bus 无在途事件时触发 `harness.continue_run()`
- `AbortCascadeHook` — 级联取消所有 sub-agent（step abort 时）
- `SubAgentMessageConverter` — 把 sub-agent 消息转为 LLM CustomMessage

---

## 6. 事件类型参考

### AgentHarness 事件（`events()` / `collect_until_settled()`）

来源：`pyharness.rs` `harness_event_to_dict()` + `event_stream.rs` `agent_event_to_dict()`

**Agent 事件**（底层 `AgentEvent`）：

| type | 字段 | 说明 |
|------|------|------|
| `agent_start` | — | Agent 开始 |
| `agent_end` | `new_messages_count`, `new_messages` | Agent 一轮结束 |
| `turn_start` | `index` | Turn 开始 |
| `turn_end` | `index`, `message_text`, `tool_results` | Turn 结束 |
| `message_start` | `message_id` | 消息开始 |
| `message_update` | `message_id`, ... | 消息更新 |
| `message_end` | `message_id`, ... | 消息结束 |
| `text_delta` | `message_id`, `text` | 流式文本增量 |
| `thinking_delta` | `message_id`, `thinking` | 推理/思考增量 |
| `tool_call_start` | ... | 工具调用开始 |
| `tool_call_args_delta` | ... | 工具参数增量 |
| `tool_call_end` | ... | 工具调用结束 |
| `tool_execution_start` | ... | 工具执行开始 |
| `tool_execution_update` | ... | 工具执行进度 |
| `tool_execution_end` | ... | 工具执行结束 |
| `error` | `message` | 错误 |
| `retry_attempt` | ... | 重试 |

**Harness 级事件**（`AgentHarnessEvent` 非 Agent 变体）：

| type | 字段 | 说明 |
|------|------|------|
| `phase_change` | `from`, `to` | 阶段变更（idle/turning/compacting/branching） |
| `model_update` | `from`, `to` | 模型变更 |
| `thinking_level_update` | `from`, `to` | 思考级别变更 |
| `tools_update` | `added`, `removed` | 工具列表变更 |
| `active_tools_update` | `active` | 活跃工具子集变更 |
| `resources_update` | `skills`, `templates`, `diagnostics` | 资源加载变更 |
| `session_info_update` | `name` | Session 名称变更 |
| `compaction_start` | `estimated_tokens` | Compaction 开始 |
| `compaction_end` | `stats`, `error` | Compaction 结束 |
| `settled` | — | Agent loop 正常完成（终端事件） |
| `aborted` | — | 被 abort 中断（终端事件） |

### WorkflowEngine 事件（`subscribe()`）

来源：`pyworkflow.rs` `workflow_event_to_dict()`

| type | 字段 | 说明 |
|------|------|------|
| `step_started` | `step_id`, `step_name` | 步骤开始 |
| `step_finished` | `step_id`, `output`, `structured`, `tool_calls_count` | 步骤完成 |
| `paused` | `reason` | 暂停 |
| `resumed` | — | 恢复 |
| `cancelled` | `reason` | 取消 |
| `failed` | `error` | 失败 |

---

## 7. 编排能力总览

| 能力 | Rust 实现 | PyO3 暴露 | 说明 |
|------|-----------|----------|------|
| DAG workflow | `Workflow` | ✅ `WorkflowEngine(workflow_dict, ...)` | steps + edges + entry_step |
| LLM step | `Step::Llm` | ✅ dict 中无 `"executor"` 键 | prompt + allowed_tools |
| Executor step | `Step::Executor` | ✅ dict 中有 `"executor"` 键 | executor_name + config |
| 声明式条件边 (8 种 op) | `EdgeConditionJudge` | ✅ edge `"condition"` dict | 自动启用 |
| 自定义 judge 路由 | `StepTransitionJudge` | ✅ `create_judge()` | To/Retry/Fail/Abort |
| CompositeJudge 按节点分发 | `CompositeJudge` | ✅ `create_composite_judge()` + `.on()` + `.fallback()` | 未注册 step 自动 fallback 到 Expr 边 |
| 共享 context 黑板 | `WorkflowContext` | ✅ `set_context_variable()` | KV 黑板 |
| 崩溃恢复 | `restore()` + `TaskStore` | ✅ **已暴露** | ~~P0~~ |
| 事件流 subscribe | `subscribe()` | ✅ `engine.subscribe()` | 6 种 WorkflowEvent |
| Pause / Resume | `pause()` / `resume()` | ✅ **已暴露** | ~~P1~~ |
| Cancel | `cancel()` | ✅ **已暴露** | ~~P1~~ |
| Checkpoint | `checkpoint()` | ✅ **已暴露** | ~~P2~~ |
| Cost 追踪 | `total_cost()` | ✅ **已暴露** | ~~P2~~ |
| Step plugin | `with_step_plugin()` | ✅ `engine.with_step_plugin()` | 每步可注入 plugin |
| Hooks (11 种) | `with_hooks()` | ✅ `engine.with_hooks()` + 11 个 `create_*_hook()` | 全部暴露 |
| Extra tools | `with_tool()` | ✅ `engine.with_tool()` | 引擎级注入 |
| spawn_agent + 6 communication tools | `SpawnAgentTool` + 6 tools + MessageBus | ✅ LLM step 内部自动注册（7 个 tool 一组） | `allowed_tools` 含 `"spawn_agent"` |
| Human-in-the-loop | `WaitForExternalEventTool` | ✅ `create_event_channel()` | 外部事件注入 |
| 内置 executor (json_transform) | `builtin_executors()` | ✅ 自动注册 | 不再被 Python callback 覆盖 |
| max_tokens | `with_max_tokens()` | ✅ `engine.with_max_tokens()` | 每步最大输出 |
| max_steps / max_retries | `with_max_steps()` / `with_max_retries()` | ✅ 已暴露 | 每步步数/重试上限 |

---

## 8. FFI 打磨清单

### P0：必须先做

#### 8.1 补 `WorkflowEngine.restore()` Python 包装

Rust `WorkflowEngine::restore()` 已实现（从 TaskStore 恢复），PyO3 `PyWorkflowEngine` 未暴露。

```python
# 目标 API
engine = WorkflowEngine.restore(
    task_id="task-abc123",
    provider=provider,
    model="gpt-4o",
    judge=judge,
    session_base_dir="sessions",
)
engine.with_executor("transform", executor)  # 需重新注册 executor
engine.run()  # 从断点续跑
```

#### 8.2 ~~Docstrings~~ 已完成

PyO3 0.29 自动导出 Rust doc comments 为 Python `__doc__`，全部 `#[pymethods]` 已覆盖。`#[pyo3(text_signature = "...")]` 已用于所有公开方法，`.pyi` stubs 与运行时 `__text_signature__` 通过 `check_stubs.py` 自动验证（112 签名零偏差）。

#### 8.3 ~~自动化 wheel 构建 CI~~ 已完成

`.github/workflows/build-wheel.yml` 已建：
1. push tag `v*` → trigger
2. 从 `senza-pkg/runtime.lock` 读取 SHA，注入 `Cargo.toml`
3. `maturin build --release`（用 `RUNTIME_PAT` 拉私有 runtime git 依赖）
4. 运行 `check_stubs.py` 验证
5. 上传 wheel 到 GitHub Release + PyPI

### P1：应做

#### 8.4 WorkflowEngine 缺失方法

| 方法 | Rust 来源 | 说明 |
|------|-----------|------|
| `state()` | `engine.state()` | 返回 WorkflowStatus + current_step + step_history_len |
| `get_var(key)` | `task_store.load_workflow_state()` | 读取 context 变量 |
| `pause(reason)` | `engine.pause()` | 非阻塞暂停 |
| `resume()` | `engine.resume()` | 从 Paused/Failed 恢复 |
| `cancel(reason)` | `engine.cancel()` | 取消执行 |
| `checkpoint(desc, payload)` | `engine.checkpoint()` | 保存检查点 |
| `total_cost()` | `engine.total_cost()` | 聚合开销 |

#### 8.5 AgentHarness 缺 context manager

当前无 `__enter__` / `__exit__` / `close()`。需要补充以支持 `with` 语法。

#### 8.6 ~~eda-agent-py 迁移~~ 已完成

eda-agent-py 已完成从 cffi `llm_harness_sdk` 到 PyO3 `llm_harness_py` 的迁移（commit `efba9a1`, 2026-07-13）。

迁移内容：
- `agent_call.py`：`Harness(**kwargs)` → `HarnessBuilder(model).provider(model, provider).max_tokens(n).system_prompt(sp).build()` + `collect_until_settled()`
- `config.py`：新增 `create_py_provider()` → `create_openai_provider()` / `create_anthropic_provider()`
- `ffi_bridge.py`：重写为 PyO3 路径，新增 `run_workflow()` 入口，用 `WorkflowEngine(workflow, provider, model, judge).with_executor(name, executor)` + `set_context_variable()` + `run()`
- `cli.py`：简化为 `run_workflow(pipeline, eda_config, llm_config, on_step=...)`
- `test_ffi_gaps.py`：从 cffi gap 测试重写为 PyO3 能力测试（12 个测试）
- 43/43 测试通过，33-stage E2E --no-llm pipeline 成功
- `llm_harness_sdk` 引用零残留

eda-agent-py 的 `import llm_harness_py` 已改为 `import senza`（commit 22555cc，2026-07-15）。43 测试通过。

### P2：可选

- `max_steps` / `max_retries` 配置暴露
- `ShellExecutor` / `HttpCallExecutor` 注册到 `builtin_executors()`
- `WorkflowEngine.run()` async 版本

---

## 9. Examples 规划

### Agent 层 (`examples/agent/`)

| 文件 | 内容 | 核心展示 |
|------|------|---------|
| `01_basic_prompt.py` | HarnessBuilder → build → prompt_and_collect | 最小可用示例 |
| `02_tool_calling.py` | create_tool → register → LLM 调 tool → 继续对话 | tool calling 闭环 |
| `03_streaming.py` | events() + threading 逐 token 流式输出 | streaming events |
| `04_dynamic_config.py` | set_model / set_system_prompt / set_temperature / set_thinking_level | 动态配置 |
| `05_multi_provider.py` | 多 provider glob 路由 | 多 provider |

### Runtime 层 (`examples/runtime/`)

| 文件 | 内容 | 核心展示 | 备注 |
|------|------|---------|------|
| `01_linear_workflow.py` | step A → step B → 完成 | 最简线性流程 | |
| `02_conditional_routing.py` | 自定义 judge 条件路由 | judge 路由 | |
| `03_executor_steps.py` | create_executor + executor step | `Step::Executor` | |
| `04_crash_recovery.py` | 崩溃 → restore() → 续跑 | 崩溃恢复 | |
| `05_pause_cancel.py` | pause → resume | 暂停恢复 | |
| `06_human_in_the_loop.py` | create_event_channel + wait_tool | 外部事件注入 | |
| `07_shell_executor.py` | Python callback executor + 命令白名单 | shell 执行 | |
| `08_http_executor.py` | create_http_executor + httpbin.org | HTTP 调用 | |
| `09_composite_judge.py` | create_composite_judge + .on() + edge fallback | 按节点路由 | |

---

## 10. Skills（AI 助手过程性知识包）

> 除了静态 examples，Senza 还提供 3 个 Codex skill，帮助 AI 编码助手理解如何使用 SDK。
> Skills 安装到 `~/.codex/skills/` 后，Codex 在相关任务中自动触发。

### skill 清单

| Skill | 触发场景 | 覆盖内容 |
|-------|---------|---------|
| `senza-agent` | 单轮 LLM 调用、tool 注册、streaming、provider 创建 | HarnessBuilder 链式 API、create_tool、AgentHarness 方法、event 类型 |
| `senza-workflow` | 多步 workflow、条件路由、judge/executor、共享 context | workflow dict schema、edge condition、Transition 编码、WorkflowEngine 方法 |
| `senza-advanced` | sub-agent、hooks、human-in-the-loop、event streaming | 7 个 spawn tool + MessageBus、11 种 hook、create_event_channel、plugin |

### 目录结构

```
skills/
├── senza-agent/
│   └── SKILL.md          # Agent 层使用指南
├── senza-workflow/
│   └── SKILL.md          # Runtime 层编排指南
└── senza-advanced/
    └── SKILL.md          # 高级模式（spawn/hooks/human-in-loop）
```

### 与 examples 的关系

| | Examples | Skills |
|--|---------|--------|
| 形式 | `.py` 可执行文件 | `SKILL.md` 过程性知识 |
| 触发 | 用户手动运行 | AI 助手自动匹配触发 |
| 内容 | 完整可运行代码 | API 参考 + 决策树 + 常见模式 |
| 受众 | 人类开发者 | AI 编码助手（Codex / Claude Code 等） |

### 安装

```bash
# 从 Senza 仓库安装到 ~/.codex/skills/
cp -r skills/senza-* ~/.codex/skills/
# 或用 skill-installer
# codex skill install --repo oh-my-harness/senza --path skills/senza-agent
```

---

## 11. 执行顺序

1. ✅ **建 Senza 仓库结构** — pyproject.toml、目录骨架、skills/
2. ✅ **补 `restore()` PyO3 包装** — P0 缺口已补
3. ✅ **补 docstrings** — PyO3 0.29 自动导出 + `check_stubs.py` 验证
4. ✅ **写 examples** — agent 01-05 + runtime 01-09
5. ✅ **写 skills** — senza-agent / senza-workflow / senza-advanced
6. ✅ **CI wheel 构建** — `.github/workflows/build-wheel.yml`
7. ✅ **补 WorkflowEngine 缺失方法** — state/get_var/pause/resume/cancel/checkpoint/total_cost
8. ✅ **eda-agent-py 迁移** — 已改为 `import senza`
9. ✅ **Py crate 迁入 Senza 仓库** — 从 runtime 仓库 `crates/llm-harness-py/` 迁入，git 依赖 + rev pin
10. ⬜ **发布 v0.1.0** — PyPI `pip install senza-sdk`

---

## 12. 仓库改名

```
github.com/oh-my-harness/llm-harness-py-wheels  →  github.com/oh-my-harness/senza
```

PyPI 包名同步注册为 `senza-sdk`（import 名 `senza`）。

---

## 13. Python 版本矩阵

`pyproject.toml` 配置 `abi3-py39`（`pyo3/abi3-py39` feature），一个 wheel 覆盖：

| Python | 支持 |
|--------|------|
| 3.9 | ✅ abi3 下限 |
| 3.10 | ✅ |
| 3.11 | ✅ |
| 3.12 | ✅ |
| 3.13 | ✅ |
| 3.14 | ✅ eda-agent-py 运行环境 |

abi3 wheel 不依赖特定 CPython 版本，只需构建一次。

---

## 14. 构建方式

```bash
# 本地开发（一键搞定：建 venv → 安装依赖 → 注入 SHA → 构建 → 安装）
./scripts/dev_setup.sh

# 手动构建 wheel
./scripts/build_wheel.sh
# 产物：dist/senza_sdk-<version>-cp39-abi3-<platform>.whl
```

构建流程（`scripts/build_wheel.sh`）：
1. 从 `senza-pkg/runtime.lock` 读取固定 SHA
2. `perl` 原地替换 `Cargo.toml` 中的 `PLACEHOLDER` → SHA（备份 `.bak`）
3. `maturin build --release`（cargo 从 GitHub 拉取 runtime git 依赖）
4. `trap ... EXIT` 恢复 `Cargo.toml`（即使构建失败也恢复）

CI（`.github/workflows/build-wheel.yml`）：
- 从 `senza-pkg/runtime.lock` 读取 SHA，`sed` 注入 `Cargo.toml`
- 用 `RUNTIME_PAT` secret 配置 git 认证（拉私有 runtime 仓库）
- `maturin build --release` → `check_stubs.py` 验证 → twine 发布到 PyPI
- runner 是临时的，无需恢复 `Cargo.toml`
