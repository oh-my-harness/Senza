# Senza (森座) — Python SDK 设计文档

> Senza = "森座" — oh-my-harness runtime 的 Python 发行包。
> 本仓库从 `llm-harness-py-wheels` 改名为 Senza，定位为 **runtime + agent 两层能力的 Python 分发与示例仓库**。

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

```
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

---

## 2. 当前状态

### 已有

- Rust FFI (`crates/llm-harness-ffi/src/lib.rs`)：14 个 harness 函数 + 7 个 workflow 函数，ABI v2
- Python SDK (`sdk-python/llm_harness_sdk/binding.py`)：cffi binding，`Harness` + `WorkflowEngine` 两个类
- 预编译 `.so` 已放在 `sdk-python/llm_harness_sdk/native/`
- eda-agent-py 已通过 `Harness` 做 LLM 单次调用（`agent_call.py`）
- eda-agent-py 已写好 `ffi_bridge.py` 桥接 WorkflowEngine（但实际跑的是 Python 镜像版编排器）

### 缺口

| ID | 问题 | 严重度 |
|----|------|--------|
| — | `WorkflowEngine.restore()` Rust FFI 已有 `ffi_workflow_restore`，Python 类未包装 | **P0** |
| — | 零 type hints、零 docstrings | **P0** |
| F-03 | Tool 错误被拍平为 `{"error": str(exc)}`，丢失异常类型/code | P1 |
| F-06 | ToolContext 只有 `is_cancelled()` + `send_update()`，无 work_dir / 共享 context | P1 |
| F-10 | 无自动化 wheel 构建（当前需手动 cargo build + copy .so） | P1 |
| — | `WorkflowEngine` 缺 `step_history()` / `context()` / `status()` 便捷查询 | P2 |
| — | `WorkflowEngine.run()` 是同步阻塞，无 async 版本 | P2 |

### cffi vs PyO3

当前实现基于 **cffi**（`sdk-python/llm_harness_sdk/binding.py`）。原 README 提到 "PyO3 extension"，但实际代码是 cffi。

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
│       ├── binding.py           # cffi binding（从 runtime 仓库同步，见下方同步机制）
│       ├── errors.py            # HarnessError
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
│       └── 07_mixed_llm_executor.py
├── ci/
│   └── build_wheel.sh           # clone runtime → cargo build → copy .so → pip build
└── .github/
    └── workflows/
        └── build.yml            # tag push → build wheel → publish release
```

### binding.py 同步机制

cffi 的 cdef 与 Rust `extern "C"` 签名必须原子性同步，否则内存踩踏。采用 **方案 A**：

- `binding.py` 源码留在 `llm-harness-runtime` 仓库的 `crates/llm-harness-ffi/sdk-python/`（与 `lib.rs` 同 commit）
- Senza build 时从 runtime 仓库指定 commit 同步 `binding.py` + `errors.py`
- Senza 仓库只做打包分发 + 高层 API 打磨 + examples，不直接改 cdef

```bash
# ci/build_wheel.sh 核心逻辑
RUNTIME_REV=<pinned commit>
git clone --depth 1 https://github.com/oh-my-harness/llm-harness-runtime.git /tmp/runtime
cd /tmp/runtime && cargo build -p llm-harness-ffi --release
cp /tmp/runtime/target/release/libllm_harness_ffi.so src/senza/native/
cp /tmp/runtime/crates/llm-harness-ffi/sdk-python/llm_harness_sdk/binding.py src/senza/binding.py
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

```python
# 目标 API
engine = WorkflowEngine.restore(
    task_id="task_abc123",
    config={...},
    judge_fn=my_judge,
)
state = engine.state()  # 应恢复到崩溃前的 step
engine.run()            # 从断点续跑
```

#### 4.2 Type hints + docstrings

当前 `binding.py` 零类型标注、零文档。需要补全：
- `Harness.__init__` 参数类型（provider/model/api_key/system_prompt/max_tokens/work_dir 等）
- `Harness.prompt` / `wait_event` / `register_tool` / `abort` / `close` 签名 + docstring
- `WorkflowEngine.__init__` / `run` / `state` / `get_var` / `register_executor` / `restore` 签名 + docstring
- event 类型文档（`text_delta` / `tool_start` / `tool_end` / `message_end` / `settled` / `aborted` / `error`）

#### 4.3 `WorkflowEngine` 便捷查询方法

当前只有 `state()` 和 `get_var()`，缺：
- `step_history()` — 返回已完成步骤列表
- `status()` — 返回当前 WorkflowStatus（idle/running/paused/succeeded/failed/cancelled）
- `current_step()` — 返回当前步骤 ID

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

#### 4.6 自动化 wheel 构建 (F-10)

GitHub Actions workflow：
1. push tag `v*` → trigger
2. clone runtime repo (pinned rev)
3. `cargo build -p llm-harness-ffi --release`
4. copy `.so` + `binding.py` + `errors.py` → `src/senza/`
5. `python -m build` → wheel
6. upload to GitHub Release + PyPI

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

| 文件 | 内容 | 核心展示 |
|------|------|---------|
| `01_linear_workflow.py` | step A → step B → 完成 | 最简线性流程：workflow JSON + executor + judge |
| `02_conditional_routing.py` | 结果合格 → 下一步，不合格 → 返工 | `EdgeCondition::Expr` 声明式条件边 |
| `03_executor_steps.py` | 非 LLM 确定性步骤（json_transform + 自定义 executor） | `Step::Executor` 类型 |
| `04_shared_context.py` | step 间通过 WorkflowContext 传数据 | `get_var()` / 共享 KV 黑板 |
| `05_crash_recovery.py` | 跑到一半模拟崩溃 → `restore()` → 续跑 | **runtime 杀手级能力：崩溃恢复** |
| `06_sub_agent.py` | step 内派发 sub-agent 处理子任务 | `spawn_agent` tool |
| `07_mixed_llm_executor.py` | LLM 步和 executor 步混合 | `Step::Llm` + `Step::Executor` 混合 |

---

## 6. 执行顺序

1. **建 Senza 仓库结构** — pyproject.toml、目录骨架、build 脚本
2. **补 `restore()` Python 包装** — P0 缺口，examples 依赖它
3. **打磨 binding.py** — type hints + docstrings + 便捷方法
4. **写 examples** — agent 层 01 → runtime 层 01 → 逐步到 05 crash recovery
5. **CI wheel 构建** — GitHub Actions 自动化
6. **发布 v0.1.0** — PyPI `pip install senza`

---

## 7. 仓库改名

```
github.com/oh-my-harness/llm-harness-py-wheels  →  github.com/oh-my-harness/senza
```

GitHub Settings → Repository name → `senza`。旧 URL 自动 redirect。

PyPI 包名同步注册为 `senza`。
