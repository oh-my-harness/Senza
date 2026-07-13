# Senza (森座) — Python SDK 设计文档

> Senza = "森座" — oh-my-harness runtime 的 Python 发行包。
> 本仓库从 `llm-harness-py-wheels` 改名为 Senza，定位为 **runtime + agent 两层能力的 Python 分发与示例仓库**。

---

> **Review 修正记录**
>
> **第一轮**（2026-07-13）：经代码级逐条验证后修正了 10 项内容，见下方 §1–§10。
>
> **第二轮**（2026-07-13）：深入对照 `engine.rs`（3239 行）编排引擎后，发现设计文档遗漏大量 LangGraph 类似编排能力，spawn_agent 结论有误，新增以下内容：
> 1. 修正 §5 `06_sub_agent.py`：spawn_agent 对 LLM step 可用（引擎内部自动注册），删掉"依赖 FFI 扩展"的标注
> 2. 新增 §11：Workflow JSON Schema 完整参考（Step / Edge / ConditionExpr / Transition / StepResult / StepRecord / WorkflowState / TaskResult）
> 3. 新增 §12：LangGraph 类似编排能力总览（runtime 有 → FFI 暴露 → 设计文档提及 三列对照）
> 4. 新增 §13：FFI 暴露缺口补充（subscribe / pause / resume / cancel / checkpoint / total_cost 6 项）
> 5. 新增 §14：内置 executor 被 FFI 覆盖问题（json_transform / shell / http_call）
> 6. §5 examples 补充 `08_event_streaming.py`、`09_pause_resume.py`、`10_llm_step.py`、`11_builtin_executor.py`
> 7. 新增 §15：Harness Event 类型完整参考（text_delta / message_end / tool_start / tool_end / tool_update / agent_end / save_point / phase_change / settled / aborted / error / prompt_start）

---

## 1. 层级定位（已验证）

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
│  + Sandbox + ToolRegistry + Budget + FFI      │
└──────────────────┬───────────────────────────┘
                   │ 依赖
┌──────────────────▼───────────────────────────┐
│  adapter 层 (llm-api-adapter)                 │
│  多 provider wire 格式归一化                  │
└──────────────────────────────────────────────┘
```

### Python SDK 暴露的两个类，分别对应两个层级

| Python 类 | Rust 来源 | 层级定位 | 暴露的能力 |
|-----------|-----------|---------|-----------|
| `Harness` | `AgentHarness`（`llm-harness-agent` crate）经 `HarnessBuilder`（`llm-harness-runtime` crate）构建 | **agent 层** | 单轮 LLM prompt → streaming response；tool calling；abort；system_prompt |
| `WorkflowEngine` | `WorkflowEngine` + `TaskStore`（`llm-harness-runtime` crate） | **runtime 层** | 多步 workflow 编排；条件路由；executor/judge 回调；shared context；崩溃恢复 |

### 为什么 `Harness` 属于 agent 层？

`HarnessBuilder` 虽然定义在 `llm-harness-runtime` crate 的 `builder.rs` 中，但它的职责是**组装 runtime 基础设施**（provider、env、sandbox、tool registry）为一个 `AgentHarness` 实例。`AgentHarness` 本身来自 `llm-harness-agent` crate，封装的是 **agent loop**（prompt → think → tool call → respond）。

从 Python 用户视角：
- `Harness` = "给 LLM 发一个 prompt，拿回回复，中间可以调 tool" → **agent 能力**
- `WorkflowEngine` = "定义一个多步流程图，引擎驱动步骤执行、路由、崩溃恢复" → **runtime 能力**

### FFI 数据结构验证

```c
// agent 层 — ffi_harness_t 持有 AgentHarness
pub struct ffi_harness_t {
    shared: Arc<SharedState>,
    runtime: Arc<Runtime>,
    harness: Arc<AgentHarness>,        // ← 来自 llm-harness-agent crate
    event_forwarder_timeout: Option<Duration>,
    tools: Mutex<Vec<ToolRegistration>>,
}

// runtime 层 — ffi_workflow_t 持有 WorkflowEngine + TaskStore
pub struct ffi_workflow_t {
    runtime: Arc<Runtime>,
    engine: Option<WorkflowEngine>,     // ← 来自 llm-harness-runtime crate
    task_store: Arc<dyn TaskStoreTrait>, // ← 来自 llm-harness-runtime crate
}
```

### FFI 函数清单（已验证）

| 分类 | 数量 | 函数 |
|------|------|------|
| harness | 13 | `abi_version`, `version`, `error_code_callback`, `new`, `free`, `free_string`, `alloc_string`, `last_error`, `register_tool`, `prompt`, `abort`, `close`, `wait_event` |
| tool | 2 | `ffi_tool_is_cancelled`, `ffi_tool_send_update` |
| workflow | 7 | `new`, `restore`, `register_executor`, `run`, `state`, `get_var`, `free` |
| **合计** | **22** | |

---

## 2. 当前状态（已验证）

### 已有

- Rust FFI (`crates/llm-harness-ffi/src/lib.rs`)：22 个 extern "C" 函数（13 harness + 2 tool + 7 workflow），ABI v2
- Python SDK (`sdk-python/llm_harness_sdk/binding.py`，667 行)：cffi binding，`Harness` + `WorkflowEngine` 两个类
- 预编译 `.so` 已放在 `sdk-python/llm_harness_sdk/native/`
- **eda-agent-py 已通过 FFI WorkflowEngine 跑通生产路径**（`cli.py` 直接 `from llm_harness_sdk import WorkflowEngine`，G1/G2/G3/G4 全部修复，commit c416ee0, 2026-07-11）
- eda-agent-py 的 `agent_call.py` 通过 `Harness` 做 LLM 单次调用（system_prompt 已通过 FFI HarnessConfig 支持）
- eda-agent-py 的 `workflow_engine/` Python 镜像保留用于 mock 测试（不依赖真实 .so），**生产路径不走它**
- runtime 仓库已有 CI（`.github/workflows/ffi-sdk-wheels.yml`）：4 平台构建 wheel（Windows/Linux/macOS x64/macOS arm64），Python 3.11，上传为 artifact

### 缺口

| ID | 问题 | 严重度 |
|----|------|--------|
| — | `WorkflowEngine.restore()` Rust FFI 已有 `ffi_workflow_restore`，Python 类未包装 | **P0** |
| — | 几乎无 type hints、几乎无 docstrings（仅 3 处 docstring、WorkflowEngine.__init__ 有基本标注） | **P0** |
| F-03 | Tool 错误被拍平为 `{"error": str(exc)}`，丢失异常类型/code | P1 |
| F-06 | ToolContext 只有 `is_cancelled()` + `send_update()`，无 work_dir / 共享 context | P1 |
| F-10 | ~~无自动化 wheel 构建~~ **已有 CI（runtime 仓库 ffi-sdk-wheels.yml，4 平台）**，但仅上传 artifact，未发布到 PyPI / GitHub Release | P1 |
| — | `WorkflowEngine` 缺 `step_history()`（完整步骤列表，非长度）便捷查询 | P2 |
| — | `WorkflowEngine.run()` 是同步阻塞，无 async 版本 | P2 |
| F-20 | subscribe / pause / resume / cancel / checkpoint / total_cost 6 项编排能力 FFI 未暴露（见 §13） | P1 |
| F-21 | 内置 executor 被 FFI Python callback 覆盖（见 §14） | P1 |

### cffi vs PyO3

当前实现基于 **cffi**（`sdk-python/llm_harness_sdk/binding.py`）。README.md 提到 "PyO3 extension" 但实际代码是 cffi——README 需修正。

| | cffi (当前) | PyO3 (可选迁移) |
|---|---|---|
| 优点 | 简单，Rust 侧只管 `extern "C"`，Python 侧纯字符串 cdef | 原生 Python 类型，更好的错误处理，可直接定义 `#[pyclass]` |
| 缺点 | 无类型安全，cdef 和 Rust 签名手动同步，error handling 笨拙 | 需引入 `pyo3` 依赖，编译更复杂，ABI 耦合更深 |
| 建议 | **短期保留 cffi**，先补功能缺口 | 长期可迁移，但非当前优先级 |

---

## 3. Senza 仓库结构

```
senza/                           # 本仓库 (github.com/oh-my-harness/llm-harness-py-wheels → 改名)
├── README.md                    # 面向用户：pip install senza + 快速上手
├── SENZA_DESIGN.md              # 本文档
├── pyproject.toml               # package name = "senza", deps = ["cffi>=1.15"]
├── src/
│   └── senza/
│       ├── __init__.py          # 导出 Harness, WorkflowEngine, HarnessError, ...
│       ├── _binding.py          # cffi cdef + 低层 FFI 调用（从 runtime 仓库同步，见下方同步机制）
│       ├── binding.py           # 高层 API 封装（type hints + docstrings + restore() + 便捷方法，Senza 仓库维护）
│       ├── errors.py            # HarnessError（从 runtime 仓库同步）
│       └── native/
│           └── .gitkeep         # .so 在 build 时放入
├── examples/
│   ├── agent/                   # ← agent 层示例（用 Harness）
│   │   ├── 01_basic_prompt.py
│   │   ├── 02_tool_calling.py
│   │   ├── 03_system_prompt.py
│   │   ├── 04_streaming.py
│   │   └── 05_multi_harness.py
│   └── runtime/                 # ← runtime 层示例（用 WorkflowEngine）
│       ├── 01_linear_workflow.py
│       ├── 02_conditional_routing.py
│       ├── 03_executor_steps.py
│       ├── 04_shared_context.py
│       ├── 05_crash_recovery.py
│       ├── 06_sub_agent.py
│       ├── 07_mixed_llm_executor.py
│       ├── 08_event_streaming.py       # ← 依赖 FFI 扩展（subscribe），见 §13
│       ├── 09_pause_resume.py          # ← 依赖 FFI 扩展（pause/resume），见 §13
│       ├── 10_llm_step.py              # ← 展示 LLM step（kind: "llm"）
│       └── 11_builtin_executor.py      # ← 展示 json_transform 内置 executor
├── ci/
│   └── build_wheel.sh           # clone runtime → cargo build → copy .so → pip build
└── .github/
    └── workflows/
        └── build.yml            # tag push → build wheel → publish release
```

### binding.py 分层归属（解决原方案 A 的矛盾）

原方案 A 将 `binding.py` 源码全部留在 runtime 仓库，Senza build 时同步拷贝。但这与 §4 FFI 打磨清单矛盾——type hints、docstrings、`restore()` 包装、便捷方法都需要改 `binding.py`。

**修正方案：拆分为两层**

| 文件 | 归属 | 内容 | 同步方式 |
|------|------|------|---------|
| `_binding.py` | runtime 仓库（`crates/llm-harness-ffi/sdk-python/llm_harness_sdk/binding.py`） | cffi cdef、`_load_lib`、低层 FFI 调用、`_check_rc` 等 | build 时从 runtime 指定 commit 拷贝，Senza 仓库不直接改 |
| `binding.py` | Senza 仓库 | 高层 API：`Harness` / `WorkflowEngine` / `ToolContext` 类定义、type hints、docstrings、`restore()` classmethod、`step_history()` 等便捷方法 | Senza 仓库独立维护，import `_binding` |

```bash
# ci/build_wheel.sh 核心逻辑
RUNTIME_REV=<pinned commit>
git clone --depth 1 https://github.com/oh-my-harness/llm-harness-runtime.git /tmp/runtime
cd /tmp/runtime && cargo build -p llm-harness-ffi --release
cp /tmp/runtime/target/release/libllm_harness_ffi.so src/senza/native/
cp /tmp/runtime/crates/llm-harness-ffi/sdk-python/llm_harness_sdk/binding.py src/senza/_binding.py
cp /tmp/runtime/crates/llm-harness-ffi/sdk-python/llm_harness_sdk/errors.py src/senza/errors.py
python -m build
```

### 包名

- PyPI 包名：`senza`
- import 名：`senza`（PEP 8 小写）
- 用户代码：`from senza import Harness, WorkflowEngine`

---

## 4. FFI 打磨清单

### P0：必须先做

#### 4.1 补 `WorkflowEngine.restore()` Python 包装

Rust 侧 `ffi_workflow_restore` 已实现，cdef 已声明，但 Python `WorkflowEngine` 类没有对应的 classmethod。

**关键注意**：`ffi_workflow_restore` 只接收 `judge_callback`，**不接收 `executor_callback`**（与 `ffi_workflow_new` 不同）。`ffi_workflow_new` 会从 workflow steps 中提取 executor_name 自动注册，但 `restore` 不会。因此恢复后**必须手动调用 `register_executor()` 重新注册所有 executor**，否则 `run()` 会报 "no executor registered" 错误。

```python
# 目标 API
engine = WorkflowEngine.restore(
    task_id="task_abc123",
    config={...},
    judge_fn=my_judge,
)
# restore 不接收 executor_fn — 必须手动重新注册
engine.register_executor("my_executor", my_executor_fn)
engine.register_executor("json_transform", other_fn)
state = engine.state()  # 应恢复到崩溃前的 step
engine.run()            # 从断点续跑
```

#### 4.2 Type hints + docstrings

当前 `binding.py`（667 行）仅 3 处 docstring，仅 `WorkflowEngine.__init__` 有基本类型标注。需要补全：
- `Harness.__init__` 参数类型（provider/model/api_key/api_key_env/work_dir/max_tokens/base_url/chat_path/messages_path/event_queue_capacity/event_forwarder_timeout_secs/system_prompt/callback_timeout）
- `Harness.prompt` / `wait_event` / `register_tool` / `abort` / `close` 签名 + docstring
- `WorkflowEngine.__init__` / `run` / `state` / `get_var` / `register_executor` / `restore` 签名 + docstring
- event 类型文档（见 §15 完整列表）

#### 4.3 ~~`WorkflowEngine` 便捷查询方法~~ 已部分实现

`ffi_workflow_state` 已返回 `status` / `current_step` / `step_history_len` 三个字段（Rust 侧 `serde_json::json!` 序列化），Python `state()` 返回 parsed JSON 即可获取。只需在高层封装中增加便捷 property 即可，**无需新增 FFI 函数**。

真正缺的只有：
- `step_history()` — 返回完整步骤列表（非长度），需新增 FFI 函数

**优先级从 P0 降为 P2。**

### P1：应做

#### 4.4 Tool 错误结构化 (F-03)

当前 Python tool callback 抛异常 → Rust 侧拍平为 `{"error": str(exc)}`。改为：
```python
# tool callback 可返回结构化错误
return {
    "content": [],
    "details": {},
    "terminate": False,
    "error": {"message": "...", "type": "ValueError", "code": 42}
}
```

#### 4.5 ToolContext 增强 (F-06/F-12)

当前 `ToolContext` 只有 `is_cancelled()` + `send_update()`。增加：
- `work_dir` — 工作目录路径
- `get_var(key)` / `set_var(key, value)` — 读写 WorkflowContext 共享变量

#### 4.6 自动化 wheel 发布 (F-10 修正)

runtime 仓库已有 CI（`ffi-sdk-wheels.yml`）构建 4 平台 wheel 并上传 artifact。Senza 仓库需要：
1. 接收 runtime CI 的 wheel artifact（或自行 clone + build）
2. 发布到 GitHub Release（tag `v*` 触发）
3. 发布到 PyPI（`senza` 包名）

可选：直接复用 runtime 仓库的 CI 产物，Senza 仓库只做 Release + PyPI 发布。

#### 4.7 编排能力 FFI 暴露缺口 (F-20)

见 §13 详细列表。6 项编排能力在 Rust runtime 中已实现但 FFI 未暴露，需新增 FFI 函数。

#### 4.8 内置 executor 被 FFI 覆盖 (F-21)

见 §14。`ffi_workflow_new` 会用 Python callback 覆盖同名的内置 executor，导致用户无法通过 FFI 使用 `json_transform` 等内置 executor。

---

## 5. Examples 规划

### Agent 层 (`examples/agent/`) — 用 `Harness`

| 文件 | 内容 | 核心展示 |
|------|------|---------|
| `01_basic_prompt.py` | 创建 Harness → prompt → 收 events → 拿最终回复 | 最小可用示例 |
| `02_tool_calling.py` | 注册 tool → LLM 调 tool → 拿结果 → 继续对话 | tool calling 闭环 |
| `03_system_prompt.py` | 设置 system_prompt 定义 agent 角色 | system_prompt 参数 |
| `04_streaming.py` | 逐 token 流式输出，展示所有 event 类型 | streaming events（见 §15 完整列表） |
| `05_multi_harness.py` | 多个 Harness 实例并行 | 实例隔离性 |

### Runtime 层 (`examples/runtime/`) — 用 `WorkflowEngine`

| 文件 | 内容 | 核心展示 | 备注 |
|------|------|---------|------|
| `01_linear_workflow.py` | step A → step B → 完成 | 最简线性流程：workflow JSON + executor + judge | |
| `02_conditional_routing.py` | 结果合格 → 下一步，不合格 → 返工 | `EdgeCondition::Expr` 声明式条件边 | |
| `03_executor_steps.py` | 非 LLM 确定性步骤（json_transform + 自定义 executor） | `Step::Executor` 类型 | 注意 FFI 覆盖问题（§14） |
| `04_shared_context.py` | step 间通过 WorkflowContext 传数据 | `get_var()` / 共享 KV 黑板 | |
| `05_crash_recovery.py` | 跑到一半模拟崩溃 → `restore()` → `register_executor()` → 续跑 | **runtime 杀手级能力：崩溃恢复** | 注意 restore 后必须重新注册 executor |
| `06_sub_agent.py` | LLM step 中 LLM 调 `spawn_agent` tool 派发 sub-agent | `SyncSpawnAgentTool` | LLM step 的 `allowed_tools` 含 `"spawn_agent"` 时引擎自动注册。依赖 LLM step（eda-agent-py 目前全用 Executor step，此路径未经端到端验证） |
| `07_mixed_llm_executor.py` | LLM 步和 executor 步混合 | `Step::Llm` + `Step::Executor` 混合 | |
| `08_event_streaming.py` | subscribe 事件流，展示 WorkflowEvent 6 种类型 | StepStarted / StepFinished / Paused / Resumed / Cancelled / Failed | **依赖 FFI 扩展**（subscribe 未暴露，见 §13） |
| `09_pause_resume.py` | 运行中 pause → resume 续跑 | pause() / resume() | **依赖 FFI 扩展**（pause/resume 未暴露，见 §13） |
| `10_llm_step.py` | 最小 LLM step 示例 | `kind: "llm"` step + prompt + allowed_tools | 展示 LLM step 基础用法 |
| `11_builtin_executor.py` | 使用 `json_transform` 内置 executor | `executor_name: "json_transform"` | 注意 FFI 覆盖问题（§14），可能需要 Rust 侧修复 |

---

## 6. 执行顺序

1. **建 Senza 仓库结构** — pyproject.toml、目录骨架、build 脚本
2. **拆分 binding.py** — `_binding.py`（cdef 层，从 runtime 同步）+ `binding.py`（高层封装，Senza 维护）
3. **补 `restore()` Python 包装** — P0 缺口，examples 依赖它（注意 register_executor 步骤）
4. **打磨高层 binding.py** — type hints + docstrings + 便捷 property
5. **写 examples** — agent 层 01 → runtime 层 01 → 逐步到 05 crash recovery → 10 llm_step
6. **CI wheel 发布** — 复用或对接 runtime CI 产物 → GitHub Release → PyPI
7. **FFI 编排能力补全**（F-20）— subscribe / pause / resume / cancel / checkpoint / total_cost
8. **内置 executor 修复**（F-21）— 让 FFI 能使用 json_transform 等
9. **补 examples** — 08 event_streaming / 09 pause_resume / 11 builtin_executor
10. **发布 v0.1.0** — PyPI `pip install senza`

---

## 7. 仓库改名

```
github.com/oh-my-harness/llm-harness-py-wheels  →  github.com/oh-my-harness/senza
```

GitHub Settings → Repository name → `senza`。旧 URL 自动 redirect。

PyPI 包名同步注册为 `senza`。

---

## 8. 包名迁移影响清单

改名为 `senza` 后，eda-agent-py 中以下硬编码导入需要迁移：

| 文件 | 行 | 当前导入 | 迁移后 |
|------|-----|---------|--------|
| `eda_agent_py/cli.py` | 23 | `from llm_harness_sdk import WorkflowEngine as FfiWorkflowEngine` | `from senza import WorkflowEngine as FfiWorkflowEngine` |
| `eda_agent_py/cli.py` | 24 | `from llm_harness_sdk import HarnessError` | `from senza import HarnessError` |
| `eda_agent_py/agent_call.py` | 33 | `from llm_harness_sdk import Harness` | `from senza import Harness` |
| `eda_agent_py/agent_call.py` | 91 | `from llm_harness_sdk import Harness, HarnessError` | `from senza import Harness, HarnessError` |
| `tests/test_ffi_gaps.py` | — | `from llm_harness_sdk import ...` | `from senza import ...` |

**迁移方案**（二选一）：
- **方案 A（推荐）**：eda-agent-py 直接改导入为 `senza`，一次性完成
- **方案 B（过渡）**：Senza 包提供兼容 shim — `llm_harness_sdk/__init__.py` 内容为 `from senza import *`，等所有下游迁移完成后删除

---

## 9. Python 版本矩阵

当前各处 Python 版本不一致，需统一：

| 来源 | 版本 |
|------|------|
| README.md（旧） | CPython 3.12 |
| runtime CI (`ffi-sdk-wheels.yml`) | 3.11 |
| `setup.py` `python_requires` | >=3.9 |
| eda-agent-py 运行环境 | 3.14.4 |

**Senza 目标版本矩阵**（建议）：

| Python | 支持 | 说明 |
|--------|------|------|
| 3.9 | ✅ | `setup.py` 下限，CI 覆盖 |
| 3.11 | ✅ | runtime CI 已覆盖 |
| 3.12 | ✅ | README 原定版本 |
| 3.14 | ✅ | eda-agent-py 运行环境 |

cffi 是纯 C ABI，不依赖特定 CPython 版本，wheel 标记为 `py3-none-{platform}` 即可跨版本使用（当前 `setup.py` 的 `PlatformWheel` 已这样做）。CI 只需在一个 Python 版本上构建 .so + wheel，安装时跨版本兼容。

---

## 10. README.md 修正项

原 README.md 有以下错误，需在改名时一并修正：

| 项 | 原文 | 修正 |
|----|------|------|
| 技术描述 | "PyO3 extension" | "cffi binding to Rust `extern \"C\"` library" |
| CPython 版本 | "CPython 3.12" | 删除固定版本，改为 "Python >=3.9"（cffi 纯 C ABI 跨版本兼容） |
| 包名 | `pip install llm_harness_py` | `pip install senza` |
| import 名 | `llm_harness_py` | `senza` |
| find-links URL | `releases/expanded_assets/v0.2.0` | 改为 Senza 仓库的 Release URL |

---

## 11. Workflow JSON Schema 完整参考

> 来源：`llm-harness-runtime/crates/llm-harness-runtime/src/workflow/model.rs`

### Workflow

```json
{
  "entry_step": "step_a",
  "steps": [ ... ],
  "edges": [ ... ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `entry_step` | string | 入口步骤 ID（必须在 steps 里） |
| `steps` | array | 步骤定义列表 |
| `edges` | array | 边定义列表（条件跳转 / 无条件顺序） |

### Step（tagged union，`kind` 字段区分）

```json
// LLM step — 引擎构造 AgentHarness，用 prompt 驱动 LLM
{
  "kind": "llm",
  "id": "step_analyze",
  "name": "分析阶段",
  "prompt": "请分析以下数据并返回 JSON...",
  "allowed_tools": ["spawn_agent", "submit_step_result"],
  "policy": { "timeout_ms": 60000, "max_attempts": 3, "retry_backoff_ms": 1000 }
}

// Executor step — 确定性非 LLM 步骤，调用注册的 executor
{
  "kind": "executor",
  "id": "step_transform",
  "name": "数据转换",
  "executor_name": "json_transform",
  "config": { "fields": { "result": "/output" } },
  "policy": { "timeout_ms": 5000 }
}
```

| 字段 | 类型 | 说明 | Llm | Executor |
|------|------|------|:---:|:--------:|
| `kind` | `"llm"` \| `"executor"` | 步骤类型标签 | ✅ | ✅ |
| `id` | string | 步骤唯一标识 | ✅ | ✅ |
| `name` | string | 人类可读名称 | ✅ | ✅ |
| `prompt` | string | LLM 指令（Llm only） | ✅ | — |
| `allowed_tools` | string[] | 本步允许的工具集（空 = 不允许任何工具） | ✅ | — |
| `executor_name` | string | Executor 注册键（Executor only） | — | ✅ |
| `config` | JSON | Executor 特定配置（Executor only） | — | ✅ |
| `policy` | object | 执行策略（可选） | ✅ | ✅ |

### StepExecutionPolicy

```json
{
  "timeout_ms": 60000,
  "max_attempts": 3,
  "retry_backoff_ms": 1000
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `timeout_ms` | u64? | 单次尝试超时（毫秒），缺省 = 无超时 |
| `max_attempts` | u32? | 最大执行尝试次数（含首次），与 judge Retry 独立 |
| `retry_backoff_ms` | u64? | 重试前固定延迟（毫秒） |

### Edge

```json
{
  "from": "step_a",
  "to": "step_b",
  "condition": "pass"                    // string = 自定义 judge label
  // 或
  "condition": { "op": "eq", "pointer": "/status", "value": "ok" }  // 声明式条件
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `from` | string | 起始步骤 ID |
| `to` | string | 目标步骤 ID |
| `condition` | string \| object? | 跳转条件（缺省 = 无条件顺序） |

### EdgeCondition（untagged union）

**Label**（string）：自定义 judge 的路由标签，由 Python judge callback 解析。

**Expr**（object，tag = `op`）：

| op | 参数 | 语义 |
|----|------|------|
| `exists` | `pointer` | structured 中该 JSON Pointer 路径存在 |
| `missing` | `pointer` | structured 中该路径不存在 |
| `eq` | `pointer`, `value` | structured 中该路径的值 == value |
| `ne` | `pointer`, `value` | structured 中该路径的值 != value |
| `gt` | `pointer`, `value`(f64) | structured 中该路径的数值 > value |
| `gte` | `pointer`, `value`(f64) | >= |
| `lt` | `pointer`, `value`(f64) | < |
| `lte` | `pointer`, `value`(f64) | <= |

`pointer` 使用 RFC 6901 JSON Pointer 语法（如 `/status`、`/data/0/score`）。条件对 `StepResult.structured` 求值。

**声明式条件自动启用**：如果 workflow 的 edges 中有任意 `EdgeCondition::Expr`，且 judge 是 NoopJudge，引擎自动替换为内置 `EdgeConditionJudge`（`engine.rs:62 default_declarative_judge`）。

### Transition（judge 返回值，snake_case 序列化）

```json
{ "to": "step_b" }                    // 跳到指定步骤
{ "retry": true }                     // 重跑当前步
{ "fail": { "reason": "不合格" } }     // 标记流程失败
{ "abort": { "reason": "正常结束" } }  // 终止流程（正常结束或 abort）
```

| 变体 | 字段 | 说明 |
|------|------|------|
| `to` | `step_id: string` | 跳到指定步骤（引擎校验合法性，非法跳转 = Failed） |
| `retry` | — | 重跑当前步（新建 harness） |
| `fail` | `reason: string` | 标记流程 Failed |
| `abort` | `reason: string` | 终止流程（Succeeded） |

### StepResult（executor callback 返回值）

```json
{
  "output": "完整文本输出",
  "structured": { "status": "ok", "score": 0.95 },
  "tool_calls_count": 2,
  "session_id": "sess_abc123",
  "cost": { "total_input_tokens": 100, "total_output_tokens": 50, ... },
  "started_at": "2026-07-13T10:00:00Z",
  "ended_at": "2026-07-13T10:00:05Z"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `output` | string | 完整文本输出 |
| `structured` | JSON? | 结构化结果（judge 读此字段做路由决策） |
| `tool_calls_count` | u32 | 工具调用次数 |
| `session_id` | string | 本步 session ID |
| `cost` | CostAggregate | 本步开销 |
| `started_at` | DateTime? | 开始时间 |
| `ended_at` | DateTime? | 结束时间 |

**executor callback 写回 context**：Python executor 返回的 `structured._context_update`（JSON object）会被引擎写回 `WorkflowContext.variables`（全量替换）。

### WorkflowState（`state()` 返回值的一部分）

```json
{
  "status": "running",
  "current_step": "step_b",
  "step_history_len": 3
}
```

`ffi_workflow_state` 返回的 JSON 包含以上三个字段。完整的 `WorkflowState`（Rust 内部）还含 `reason`、`result`、`error`、`started_at`、`ended_at`、`step_history`（完整列表）、`context`，但这些目前 FFI 未暴露。

### WorkflowStatus（snake_case）

`idle` | `running` | `paused` | `succeeded` | `failed` | `cancelled`

### TaskResult（`run()` 返回值）

```json
{
  "cost": { "total_input_tokens": 500, "total_output_tokens": 200, ... },
  "turns": 5,
  "final_message": "最终输出文本"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `cost` | CostAggregate | 所有步骤的聚合开销 |
| `turns` | u32 | 完成的步骤数（step_history 中 result: Some 的条目数） |
| `final_message` | string? | 最后一步的 output |

### CostAggregate

```json
{
  "total_input_tokens": 500,
  "total_output_tokens": 200,
  "total_cache_read_tokens": 0,
  "total_cache_write_tokens": 0,
  "total_cost": 0.015,
  "by_model": { "gpt-4": { ... } }
}
```

---

## 12. LangGraph 类似编排能力总览

> Runtime 的 WorkflowEngine 引入了与 LangGraph 类似的编排机制。以下对照 runtime 有 → FFI 暴露 → 设计文档提及。

### 核心编排

| 能力 | Rust 实现 | LangGraph 对应 | FFI 暴露 | 设计文档 |
|------|-----------|---------------|---------|---------|
| DAG workflow (steps+edges+entry) | `Workflow` struct | `StateGraph` | ✅ `ffi_workflow_new` | ✅ |
| 两种 step 类型 (Llm/Executor) | `Step` enum | Node types | ✅ JSON 传入 | ✅ §11 |
| 声明式条件边 (8 种 op) | `EdgeConditionJudge` | Conditional edges | ✅ 引擎内部自动 | ✅ §11 |
| 自定义 judge 路由 | `StepTransitionJudge` trait | Edge routing | ✅ judge callback | ✅ §11 |
| Transition: To/Retry/Fail/Abort | `Transition` enum | Edge transitions | ✅ judge 返回 | ✅ §11 |
| 共享 context 黑板 (KV) | `WorkflowContext` | Shared state | ✅ `get_var` | ✅ |
| 崩溃恢复 | `restore()` + `TaskStore` | Checkpointer | ✅ `ffi_workflow_restore` | ✅ |
| StepExecutionPolicy (timeout/retry) | `StepExecutionPolicy` | Node retry policy | ✅ JSON 传入 | ✅ §11 |
| max_steps / max_retries 安全阀 | engine 字段 | Recursion limit | ✅ config 传入 | ❌ 应补 |
| Gate hook (工具收窄) | `WorkflowGateHook` | — | ✅ 引擎内部 | ❌ 应补 |
| 动态 workflow 规划 | `PlanWorkflowTool` | — | ❌ 未暴露 | ❌ |
| 内置 executor (json_transform) | `builtin_executors()` | — | ⚠️ 被 FFI 覆盖 (§14) | ❌ 应补 |
| shell executor | `ShellExecutor` | — | ❌ 未自动注册 | ❌ |
| http_call executor | `HttpCallExecutor` | — | ❌ 未自动注册 | ❌ |

### 运行时控制（LangGraph 核心能力）

| 能力 | Rust 实现 | LangGraph 对应 | FFI 暴露 | 设计文档 |
|------|-----------|---------------|---------|---------|
| 事件流 subscribe | `subscribe()` → broadcast | `astream_events` | ❌ | ✅ §13 |
| Pause | `pause()` | `interrupt` | ❌ | ✅ §13 |
| Resume | `resume()` | `Command(resume=)` | ❌ | ✅ §13 |
| Cancel | `cancel()` | — | ❌ | ✅ §13 |
| Checkpoint | `checkpoint()` | Checkpointer | ❌ | ✅ §13 |
| Cost 追踪 | `total_cost()` | — | ❌ | ✅ §13 |
| Step plugin (每步可注入 plugin) | `with_step_plugin()` | — | ❌ | ❌ |
| Hooks (BeforeToolCall/AfterToolCall 等) | `with_hooks()` | — | ❌ | ❌ |
| Extra tools (引擎级注入) | `with_tool()` | — | ❌ | ❌ |

### Sub-agent

| 能力 | Rust 实现 | LangGraph 对应 | FFI 暴露 | 设计文档 |
|------|-----------|---------------|---------|---------|
| spawn_agent (同步等待) | `SyncSpawnAgentTool` | Subgraph | ✅ LLM step 内部自动注册 | ✅ §5 |
| spawn_agent (异步) | `SpawnAgentTool` (spawn_tool.rs) | — | ❌ 未在 FFI harness 注册 | ❌ |

**spawn_agent 注册条件**（`engine.rs:1122`）：LLM step 的 `allowed_tools` 含 `"spawn_agent"` 时，引擎自动构造 `SyncSpawnAgentTool` 并注入 step harness。不需要额外 FFI 函数。但要求 step 类型为 `kind: "llm"`。

---

## 13. FFI 编排能力暴露缺口 (F-20)

以下 6 项能力在 Rust `WorkflowEngine` 中已实现，但 FFI 未暴露。这些是 LangGraph 的核心运行时控制能力。

| # | Rust 方法 | 功能 | FFI 需新增 | 优先级 | Example |
|---|-----------|------|-----------|--------|---------|
| 1 | `subscribe()` | 返回 broadcast Receiver，推送 6 种 WorkflowEvent | `ffi_workflow_subscribe` | P1 | `08_event_streaming.py` |
| 2 | `pause(reason)` | 非阻塞暂停，run() 在步边界消费 | `ffi_workflow_pause` | P1 | `09_pause_resume.py` |
| 3 | `resume()` | 从 Paused/Failed 恢复，重置为 Paused | `ffi_workflow_resume` | P1 | `09_pause_resume.py` |
| 4 | `cancel(reason)` | 立即 abort 当前 step | `ffi_workflow_cancel` | P1 | — |
| 5 | `checkpoint(desc, payload)` | 保存检查点（append-only） | `ffi_workflow_checkpoint` | P2 | — |
| 6 | `total_cost()` | 聚合所有步骤开销 | `ffi_workflow_total_cost` | P2 | — |

### WorkflowEvent 类型（subscribe 推送）

```rust
pub enum WorkflowEvent {
    StepStarted { step_id, step_name },
    StepFinished { step_id, result: StepResult },
    Paused { reason },
    Resumed,
    Cancelled { reason },
    Failed { error },
}
```

### 注意事项

- `pause()` 是非阻塞的（设标志即返回），`run()` 在步边界检查并消费。这意味着 pause 不会中断当前正在执行的 step。
- `resume()` 接受 `Paused` 和 `Failed` 两种状态。`Failed` 恢复时重置为 `Paused`，由 `run()` 驱动 `Paused → Running`。
- `cancel()` 会 abort 当前 step 的 CancellationToken，并置 `Cancelled` 状态。
- `subscribe()` 返回 `broadcast::Receiver`，溢出时丢弃旧事件。FFI 需设计轮询 API（类似 `ffi_harness_wait_event`）。

---

## 14. 内置 executor 被 FFI 覆盖问题 (F-21)

### 问题

`WorkflowEngine::new()` 内部调 `from_parts()`，自动注册 `builtin_executors()`（当前只有 `json_transform`，`executor.rs:57`）。

但 FFI 的 `ffi_workflow_new`（`lib.rs:1555`）会提取 workflow 中**所有** Executor step 的 `executor_name`，统一注册为 Python callback：

```rust
let executor_names: Vec<String> = workflow.steps.iter()
    .filter_map(|s| s.executor_name().map(|n| n.to_string()))
    .collect();
for name in &executor_names {
    engine = engine.with_executor(name.clone(), executor.clone()); // insert → 覆盖 builtin
}
```

`with_executor` 用 `HashMap::insert`（`engine.rs:607`），会覆盖同名的内置 executor。所以如果 workflow 里有 `executor_name: "json_transform"` 的 step，Python callback 会覆盖 Rust 内置实现。

### 影响

- 用户无法通过 FFI 使用 Rust 内置的 `json_transform` executor
- `shell` 和 `http_call` executor 本来就没在 `builtin_executors()` 中自动注册，FFI 更无法使用

### 修复方向

**方案 A**（Rust 侧）：FFI `ffi_workflow_new` 中跳过已知内置 executor name，不注册 Python callback：

```rust
const BUILTIN_EXECUTORS: &[&str] = &["json_transform"];
for name in &executor_names {
    if !BUILTIN_EXECUTORS.contains(&name.as_str()) {
        engine = engine.with_executor(name.clone(), executor.clone());
    }
}
```

**方案 B**（Rust 侧）：`builtin_executors()` 注册 `shell` 和 `http_call`，FFI 同样跳过。

**方案 C**（Python 侧）：Senza 高层 API 中，用户可选注册 builtin executor 的 Python 镜像（不经过 Rust）。

建议方案 A + B：Rust 侧补全 builtin 注册 + FFI 跳过 builtin name。

---

## 15. Harness Event 类型完整参考

> 来源：`llm-harness-ffi/src/lib.rs` `forward_agent_event` + `forward_harness_event`

Harness 的 `wait_event()` 返回 JSON dict，`type` 字段区分事件类型。

### 终端事件（TERMINAL_EVENTS）

收到这些事件后 `collect_until_settled` 会计数：

| type | 来源 | 含义 |
|------|------|------|
| `settled` | `AgentHarnessEvent::Settled` | Agent loop 正常完成 |
| `aborted` | `AgentHarnessEvent::Aborted` | 被 abort() 中断 |
| `error` | `AgentEvent::Error` | 发生错误 |

### 流式事件

| type | 字段 | 含义 |
|------|------|------|
| `prompt_start` | `prompt: string` | prompt 发送开始 |
| `text_delta` | `message_id: string`, `text: string` | LLM 流式文本增量 |
| `message_end` | `message_id: string`, `message: object` | LLM 消息结束（含 usage） |
| `tool_start` | `tool_call_id: string`, `tool_name: string`, `args: JSON` | 工具调用开始 |
| `tool_end` | `tool_call_id: string`, `tool_name: string`, `result: object` | 工具调用结束 |
| `tool_update` | `tool_call_id: string`, `partial: object` | 工具执行中间进度 |
| `agent_end` | `new_messages: array` | Agent 一轮结束 |
| `save_point` | `entries_flushed: int` | Session 持久化保存点 |
| `phase_change` | `from: string`, `to: string` | Harness 阶段变更 |
| `progress` | `text: string` | 进度文本 |
| `final_answer` | `text: string` | 最终答案 |

### Python 侧聚合

`get_final_response()` / `aggregate_events()` 会把事件列表聚合为：

```python
{
    "text": "...",           # final_answer 优先，否则 text_delta 拼接
    "message": {...},        # 最后一个 message_end 的 message
    "usage": {...},          # message 中的 usage
    "tool_calls": [...],     # 所有 tool_start/tool_end 配对
    "errors": [...],         # 所有 error 事件
    "progress": [...],       # 所有 progress 事件
}
```
