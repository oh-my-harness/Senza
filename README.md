# Senza (森座)

oh-my-harness Rust runtime 的 Python SDK，基于 PyO3 构建。

Senza 向 Python 暴露 runtime 的两层能力：

| 层级 | 类 | 用途 |
|------|-----|------|
| **Agent** | `HarnessBuilder`、`AgentHarness` | 单轮 LLM 对话、工具调用、流式输出、动态配置 |
| **Runtime** | `WorkflowEngine` | 多步工作流、条件路由、崩溃恢复、暂停/取消 |

---

## 安装

```bash
pip install senza-sdk
```

验证：

```python
import senza as lh
print(lh.version())  # e.g. "0.3.0"
```

---

## 快速上手

### Agent：单轮 LLM 对话

```python
import senza as lh

provider = lh.create_openai_provider(api_key="sk-...")

harness = (
    lh.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .system_prompt("你是一个有用的助手。")
    .max_tokens(512)
    .build()
)

events = harness.prompt_and_collect("用一句话解释闭包。")

text = ""
for event in events:
    if event["type"] == "text_delta":
        text += event.get("text", "")
print(text)
```

### Agent：带工具调用

```python
import json

def get_weather(args, ctx):
    return {
        "content": [{"type": "text", "text": f"{args['city']}的天气：晴，22°C"}],
        "terminate": False,
    }

tool = lh.create_tool(
    "get_weather", "查询城市天气",
    json.dumps({"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}),
    get_weather,
)

harness = (
    lh.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .tool(tool)
    .build()
)
harness.prompt("东京天气怎么样？")
```

### Agent：异步流式输出

Senza 提供模块级 async generator 函数，支持在 asyncio 事件循环中流式消费事件：

```python
import asyncio
import senza as lh

async def main():
    provider = lh.create_openai_provider(api_key="sk-...")
    harness = (
        lh.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .system_prompt("你是一个有用的助手。")
        .max_tokens(256)
        .build()
    )

    # stream_prompt: 发送 prompt 并 async yield 事件
    async for event in lh.stream_prompt(harness, "用一句话解释闭包。", timeout_ms=30000):
        if event["type"] == "text_delta":
            print(event.get("text", ""), end="", flush=True)

    # stream_events: 仅订阅事件流（需另起线程调用 prompt）
    # stream_run: 工作流事件流

asyncio.run(main())
```

> **提示**：异步流式方法是模块级函数（`senza.stream_prompt`、`senza.stream_events`、`senza.stream_run`），不是 `AgentHarness` 的方法。

### Runtime：多步工作流

```python
import senza as lh

provider = lh.create_openai_provider(api_key="sk-...")

workflow = {
    "entry_step": "writer",
    "steps": [
        {"id": "writer", "name": "写作", "prompt": "写一句关于猫的故事。", "allowed_tools": []},
        {"id": "reviewer", "name": "审阅", "prompt": "给这个故事打分 1-5。", "allowed_tools": []},
    ],
    "edges": [{"from": "writer", "to": "reviewer"}],
}

def judge(ctx):
    if ctx["step_id"] == "writer":
        return "to:reviewer"
    return "abort:done"

engine = (
    lh.WorkflowEngine(workflow, provider, "gpt-4o", lh.create_judge(judge))
    .with_max_tokens(256)
)

engine.run()

for record in engine.step_history():
    r = record.get("result")
    print(f"{record['step_id']}: {r['output'][:80] if r else '(无结果)'}")
```

### Runtime：崩溃恢复

```python
import tempfile

with tempfile.TemporaryDirectory() as store_dir:
    # 带持久化运行
    engine = (
        lh.WorkflowEngine(workflow, provider, "gpt-4o", lh.create_judge(judge))
        .with_task_store(store_dir)
    )
    task_id = engine.task_id()
    engine.run()

    # 崩溃后恢复
    restored = lh.WorkflowEngine.restore(store_dir, task_id, provider, "gpt-4o", lh.create_judge(judge))
    print(restored.state(), restored.current_step())
```

---

## API 速查

### Provider

```python
lh.create_openai_provider(api_key, base_url=None, chat_path=None, thinking_scheme=None, parse_reasoning_content=True, tolerant_keepalive=True)
lh.create_anthropic_provider(api_key, base_url=None, messages_path=None)
```

### Agent 层

| 方法 | 说明 |
|------|------|
| `HarnessBuilder(model)` | 创建 builder |
| `.provider(pattern, provider)` | 注册 LLM provider（glob 匹配模型名，`"*"` 匹配所有） |
| `.system_prompt(text)` | 设置系统提示 |
| `.max_tokens(n)` / `.temperature(t)` | LLM 参数 |
| `.thinking_level(level)` | 设置 thinking level |
| `.auto_compact(b)` / `.compaction_reserve_tokens(n)` / `.compaction_keep_recent_tokens(n)` | Compaction 配置 |
| `.compaction_model(model, context_window, max_tokens)` | 独立 compaction 模型 |
| `.should_stop_hook(hook)` / `.hooks([hook, ...])` | 注册 ShouldStopHook / 批量 hooks |
| `.retry(max_retries, base_delay_ms)` | 瞬时错误重试配置 |
| `.model_info(context_window, max_tokens)` | 模型元数据 |
| `.final_answer_mode("heuristic"\|"tool")` | 最终回答判定模式 |
| `.stream_options(timeout_ms, max_retries)` | 流式请求选项 |
| `.queue_capacity(n)` | steer/follow-up 队列容量 |
| `.budget(limit, exceeded_hook=None)` | 预算上限 + 超限回调 |
| `.pricing(provider)` | 定价 provider（成本计算） |
| `.skill(skill)` / `.skills([skill, ...])` | 注册 skill(s) |
| `.disable_skill_read_tool()` | 关闭 SkillReadTool 自动注册 |
| `.tool(tool)` / `.plugin(plugin)` | 注册工具/插件 |
| `.env(env)` | 设置执行环境（`create_os_env(...)`），启用 bash/read/write/edit 工具 |
| `.build()` | 返回 `AgentHarness` |
| `harness.prompt_and_collect(text, timeout_ms=30000)` | 发送提示并收集事件（推荐） |
| `harness.prompt(text)` | 发送提示（阻塞，需配合线程收集事件） |
| `harness.collect_until_settled(timeout_ms=30000)` | 收集事件直到完成 |
| `harness.events(timeout_ms=5000)` | 流式事件迭代器 |
| `harness.set_model(model)` | 运行时切换模型 |
| `harness.set_system_prompt(text)` | 修改系统提示 |
| `harness.set_thinking_level("high")` | "off"/"minimal"/"low"/"medium"/"high"/"xhigh"/"budget:N" |
| `harness.steer(text)` / `harness.follow_up(text)` | 运行中注入消息 |
| `harness.usage()` | 查询成本统计 |
| `harness.get_messages()` | 获取完整对话历史 |
| `harness.last_response()` | 获取最近一条 assistant 回复文本 |
| `harness.abort()` | 取消当前提示 |
| `harness.clear_all_queues()` / `harness.has_queued_messages()` | 队列管理 |
| `harness.set_active_tools(tools)` | 限定下一轮工具子集 |
| `harness.fork_branch()` / `harness.list_branches()` / `harness.navigate_tree()` | 会话分支管理 |
| `harness.read_active_path()` / `harness.read_all_entries()` | 读取会话历史 |
| `harness.delete_branch()` / `harness.generate_branch_summary()` | 分支删除与摘要 |

### Runtime 层

| 方法 | 说明 |
|------|------|
| `WorkflowEngine(workflow_dict, provider, model, judge, env=...)` | 构造引擎；`env` 可选，传 `create_os_env(...)` 以启用 shell 执行 |
| `.with_tool(tool)` / `.with_executor(name, exec)` | 注册工具/执行器 |
| `.with_hooks([hooks])` | 注册 hooks |
| `.with_task_store(dir)` | 启用持久化 |
| `.with_max_steps(n)` / `.with_max_retries(n)` | 总步数上限 / per-step 连续 Retry 上限（超限 → Failed） |
| `.with_max_tokens(n)` / `.with_thinking_level(level)` | per-step LLM 参数（共享，所有 step） |
| `.with_step_builder(step_id, customize)` | per-step builder 定制闭包（覆盖共享设置，如 system_prompt） |
| `.run()` | 执行（阻塞） |
| `.state()` | "idle"/"running"/"paused"/"succeeded"/"failed"/"cancelled" |
| `.current_step()` / `.step_history()` | 进度查询 |
| `.pause(reason)` / `.resume()` / `.cancel(reason)` | 流程控制 |
| `WorkflowEngine.restore(store_dir, task_id, provider, model, judge)` | 类方法 — 崩溃恢复 |
| `.checkpoint(desc, payload)` / `.total_cost()` | 检查点 & 成本 |
| `.subscribe(timeout_ms=5000)` | 事件流迭代器 |

### Executor

```python
lh.create_composite_judge()           # CompositeJudge（按节点注册独立路由）
lh.create_executor(callback)           # Python 回调执行器
lh.create_shell_executor(commands)     # Shell 命令执行器（命令白名单，需配合 create_os_env）
lh.create_http_executor(allowed_hosts) # HTTP 调用执行器（host 白名单）
lh.create_fs_tools_plugin()       # bash/read/write/edit 四件套 Plugin（需配合 create_os_env）
lh.create_os_env(working_dir=".")      # OS 文件系统 + shell 执行环境（传给 WorkflowEngine(env=...)）


### Judge ctx 字段

Judge callback 收到的 `ctx: dict` 包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `step_id` | str | 当前步 ID |
| `output` | str | 当前步执行输出 |
| `structured` | dict \| None | 结构化结果（step 声明 `structured: true` 时，引擎从 final answer 提取的 JSON） |
| `structured_status` | str | `"not_required"` / `"ok"` / `"failed"`（结构化提取状态） |
| `step_count` | int | `step_history` 长度（含当前步） |
| `retry_count` | int | 当前 step 的连续 Retry 次数（0 = 首次执行后；与 `with_max_retries` 同口径） |
| `tool_calls_count` | int | 本步工具调用次数（不含 `submit_step_result`，该工具已移除） |

### Retry 语义

- `with_max_retries(n)`：**per-step** 连续 Retry 上限。`n=3` 允许 3 次 Retry，第 4 次触发 Failed（不含原始执行）。
- `with_max_steps(n)`：**workflow 级** 总步数护栏，含所有 Retry 重跑。超限 → Failed。
- judge 每次 Retry 后仍会被调用，engine 不自动吞重试——judge 自行决定是否继续 Retry。
- 与 `StepExecutionPolicy.max_attempts` 独立：最坏情况单步执行次数 = `max_retries × max_attempts`。
- 如需 per-回环 独立限制，在 judge 中读 `ctx["retry_count"]` 并自行决策。

### Hooks（11 种）

```python
lh.create_before_turn_hook(cb)         # cb(ctx: dict) -> None
lh.create_after_turn_hook(cb)          # cb(ctx: dict) -> None
lh.create_should_stop_hook(cb)         # cb(ctx: dict) -> bool
lh.create_before_tool_call_hook(cb)    # cb(ctx: dict) -> str | None
lh.create_after_tool_call_hook(cb)     # cb(ctx: dict) -> str | dict
# ... 还有 6 种（见 examples/ 和 skills/）
```

### Pricing

```python
lh.create_pricing_provider(table)              # 静态定价表 dict
lh.create_pricing_provider_callback(cb)        # cb(model, provider) -> dict | None
```

### Budget

```python
lh.create_budget_exceeded_hook(cb)  # cb(cost: dict, limit: float) -> bool
```

### Rules 审批

```python
lh.create_contains_predicate(allowed)              # tool_name ∈ allowed
lh.create_regex_field_predicate(arg_path, pattern) # args[arg_path] 匹配正则
lh.create_number_range_predicate(arg_path, min, max) # 数值区间
lh.create_rate_limit_predicate(max, window_seconds)  # 限流

chain = lh.create_rule_chain().rule("search", pred, "allow").fallback("deny").build()
hook = lh.create_rule_approval_hook(chain)  # → BeforeToolCallHook
```

### Skills

```python
lh.load_skills(path)  # 扫描目录下的 SKILL.md，返回 list[Skill]
```

### Agent：内置 bash/read/write/edit 工具

```python
import senza as lh

provider = lh.create_openai_provider(api_key="sk-...")

harness = (
    lh.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(lh.create_fs_tools_plugin())  # 注册 bash/read/write/edit
    .env(lh.create_os_env("."))           # 提供真实文件系统 + shell
    .system_prompt("你是一个能读写文件的助手。")
    .build()
)

events = harness.prompt_and_collect("在当前目录创建 hello.txt，内容写 Hello")
```

---
## Session Viewer

Senza 内置 session 查看器，可视化 `JsonlSessionRepo` 持久化的 agent session。JSONL 解析和分支树构建由 Rust `session-viewer` crate 完成（通过 `senza.read_sessions()` / `senza.viewer_html()` 暴露），Python 端仅负责 HTTP serving 和浏览器启动——单一真相源，零重复逻辑。

```bash
# CLI
python -m senza.viewer /path/to/sessions [--port PORT]
```

```python
# 编程式
import senza.viewer
senza.viewer.serve("/path/to/sessions")  # 阻塞，自动打开浏览器
```

支持：session 列表、分支树切换、消息渲染（user/assistant/tool-result）、thinking 和 tool-use 折叠、token 用量统计、config entry（model change / compaction / label 等）、图片内联。

---
## 示例

见 [`examples/`](examples/) 目录：

- `examples/agent/` — 5 个示例（基础对话、工具调用、流式输出、动态配置、多 provider）
- `examples/runtime/` — 9 个示例（线性工作流、条件路由、执行器、崩溃恢复、暂停/取消、人工介入、Shell、HTTP、CompositeJudge）

```bash
export OPENAI_API_KEY=sk-...
python examples/agent/01_basic_prompt.py
python examples/runtime/01_linear_workflow.py
```

## Skills

见 [`skills/`](skills/) 目录（供 Codex 加载的过程性知识）：

- `senza-agent` — Agent 层使用模式
- `senza-workflow` — Runtime 层使用模式
- `senza-advanced` — Hooks、插件、人工介入、执行器

## 设计文档

见 [`SENZA_DESIGN.md`](SENZA_DESIGN.md) — 完整架构、缺口分析、路线图。

## 开发

开发 Senza 本身见 [DEVELOPMENT.md](DEVELOPMENT.md)——涵盖本地搭建、测试（`./scripts/cargo_checks.sh` 一键跑 fmt+clippy+cargo test+pytest）、发布流程、CI 行为。下游项目想本地改 Senza 源码：用下游项目的 `scripts/install-senza-dev.sh`（editable 安装 `../Senza`）。
