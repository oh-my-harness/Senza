# Senza (森座) — Python SDK 设计文档

> Senza = "森座" — oh-my-harness runtime 的 Python 发行包。
> 本仓库从 `llm-harness-py-wheels` 改名为 Senza，定位为 **runtime + agent 两层能力的 Python 分发与示例仓库**。

---

> **Review 修正记录**（2026-07-13）
>
> 本文档经代码级逐条验证后修正了以下内容：
> 1. §2 当前状态：eda-agent-py **已用 FFI WorkflowEngine 跑通**（非 Python 镜像版），G1/G2/G3/G4 均已修复
> 2. §2 缺口表：FFI 函数计数修正（13 harness + 2 tool + 7 workflow = 22），新增 F-10 已有 CI 的说明
> 3. §2 缺口表："零 type hints/docstrings" 修正为"几乎无"
> 4. §4.1：`restore()` API 补充 `register_executor()` 步骤（Rust 侧不接收 executor_callback）
> 5. §4.3：`state()` 已返回 status/current_step/step_history_len，降级为 P2
> 6. §3：补充 `binding.py` 归属分层方案（cdef 留 runtime，高层封装放 Senza）
> 7. §5：`06_sub_agent.py` 标记为依赖 FFI 扩展（spawn_agent 未在 FFI 层暴露）
> 8. 新增 §8：包名迁移影响清单（eda-agent-py 硬编码导入）
> 9. 新增 §9：Python 版本矩阵
> 10. README.md 同步修正（PyO3→cffi、包名、CPython 版本）

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
│       ├── 06_sub_agent.py       # ← 依赖 FFI 扩展（spawn_agent 未暴露），v0.1.0 暂不实现
│       └── 07_mixed_llm_executor.py
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
- `Harness.__init__` 参数类型（provider/model/api_key/system_prompt/max_tokens/work_dir 等）
- `Harness.prompt` / `wait_event` / `register_tool` / `abort` / `close` 签名 + docstring
- `WorkflowEngine.__init__` / `run` / `state` / `get_var` / `register_executor` / `restore` 签名 + docstring
- event 类型文档（`text_delta` / `tool_start` / `tool_end` / `message_end` / `settled` / `aborted` / `error`）

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

---

## 5. Examples 规划

### Agent 层 (`examples/agent/`) — 用 `Harness`

| 文件 | 内容 | 核心展示 |
|------|------|---------|
| `01_basic_prompt.py` | 创建 Harness → prompt → 收 events → 拿最终回复 | 最小可用示例 |
| `02_tool_calling.py` | 注册 tool → LLM 调 tool → 拿结果 → 继续对话 | tool calling 闭环 |
| `03_system_prompt.py` | 设置 system_prompt 定义 agent 角色 | system_prompt 参数 |
| `04_streaming.py` | 逐 token 流式输出，展示所有 event 类型 | streaming events |
| `05_multi_harness.py` | 多个 Harness 实例并行 | 实例隔离性 |

### Runtime 层 (`examples/runtime/`) — 用 `WorkflowEngine`

| 文件 | 内容 | 核心展示 | 备注 |
|------|------|---------|------|
| `01_linear_workflow.py` | step A → step B → 完成 | 最简线性流程：workflow JSON + executor + judge | |
| `02_conditional_routing.py` | 结果合格 → 下一步，不合格 → 返工 | `EdgeCondition::Expr` 声明式条件边 | |
| `03_executor_steps.py` | 非 LLM 确定性步骤（json_transform + 自定义 executor） | `Step::Executor` 类型 | |
| `04_shared_context.py` | step 间通过 WorkflowContext 传数据 | `get_var()` / 共享 KV 黑板 | |
| `05_crash_recovery.py` | 跑到一半模拟崩溃 → `restore()` → `register_executor()` → 续跑 | **runtime 杀手级能力：崩溃恢复** | 注意 restore 后必须重新注册 executor |
| `06_sub_agent.py` | step 内派发 sub-agent 处理子任务 | `spawn_agent` tool | **依赖 FFI 扩展**：`spawn_agent` tool 当前未在 FFI 层暴露（`ffi_harness_new` 不注册，`HarnessBuilder` 无 spawn 代码），需先在 FFI 增加支持。v0.1.0 暂不实现 |
| `07_mixed_llm_executor.py` | LLM 步和 executor 步混合 | `Step::Llm` + `Step::Executor` 混合 | |

---

## 6. 执行顺序

1. **建 Senza 仓库结构** — pyproject.toml、目录骨架、build 脚本
2. **拆分 binding.py** — `_binding.py`（cdef 层，从 runtime 同步）+ `binding.py`（高层封装，Senza 维护）
3. **补 `restore()` Python 包装** — P0 缺口，examples 依赖它（注意 register_executor 步骤）
4. **打磨高层 binding.py** — type hints + docstrings + 便捷 property
5. **写 examples** — agent 层 01 → runtime 层 01 → 逐步到 05 crash recovery
6. **CI wheel 发布** — 复用或对接 runtime CI 产物 → GitHub Release → PyPI
7. **发布 v0.1.0** — PyPI `pip install senza`

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
