# Senza API 参考

## Provider

```python
senza.create_openai_provider(api_key, base_url=None, chat_path=None, thinking_scheme=None, parse_reasoning_content=True, tolerant_keepalive=True)
senza.create_anthropic_provider(api_key, base_url=None, messages_path=None)
```

> 接入通义千问 / DeepSeek / Ollama 等 OpenAI 兼容模型？见 [Provider 配置指南](providers.md)。

## Agent 层

### HarnessBuilder

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

### AgentHarness

| 方法 | 说明 |
|------|------|
| `.prompt_and_collect(text, timeout_ms=30000)` | 发送提示并收集事件（推荐） |
| `.prompt(text)` | 发送提示（阻塞，需配合线程收集事件） |
| `.collect_until_settled(timeout_ms=30000)` | 收集事件直到完成 |
| `.events(timeout_ms=5000)` | 流式事件迭代器 |
| `.set_model(model)` | 运行时切换模型 |
| `.set_system_prompt(text)` | 修改系统提示 |
| `.set_thinking_level("high")` | "off"/"minimal"/"low"/"medium"/"high"/"xhigh"/"budget:N" |
| `.steer(text)` / `.follow_up(text)` | 运行中注入消息 |
| `.usage()` | 查询成本统计 |
| `.get_messages()` | 获取完整对话历史 |
| `.last_response()` | 获取最近一条 assistant 回复文本 |
| `.abort()` | 取消当前提示 |
| `.clear_all_queues()` / `.has_queued_messages()` | 队列管理 |
| `.set_active_tools(tools)` | 限定下一轮工具子集 |
| `.fork_branch()` / `.list_branches()` / `.navigate_tree()` | 会话分支管理 |
| `.read_active_path()` / `.read_all_entries()` | 读取会话历史 |
| `.delete_branch()` / `.generate_branch_summary()` | 分支删除与摘要 |

### 事件类型

Terminal: `settled`, `aborted`, `error`.

Streaming: `text_delta` (has `.text`), `message_end`, `tool_call_start`, `tool_call_end`, `tool_execution_start`, `tool_execution_end`, `thinking_delta`.

Harness: `phase_change`, `compaction_start`, `compaction_end`, `tools_update`.

### 三种 prompt 方式

| 方式 | 适用场景 | 说明 |
|------|---------|------|
| `harness.prompt_and_collect(text)` | **推荐**，同步场景 | 一步发送 + 收集所有事件，返回 `list[dict]` |
| `senza.stream_prompt(harness, text)` | 需要流式输出 | 模块级 async generator，逐 token yield 事件 |
| `harness.prompt(text)` + `harness.events()` | 需要线程级控制 | prompt 阻塞，需另起线程收集事件 |

### 工具创建

```python
import json

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
```

- `parameters_schema`: JSON Schema 字符串（不是 dict，需 `json.dumps`）。
- `callback`: `(args: dict, ctx: ToolContext) -> dict`。`ctx` 可选——函数接受 2 参时传 `ctx`，1 参时只传 `args`。
- 返回 dict: `{"content": [ContentBlock...], "terminate": bool}`。`terminate=True` 停止 agent 循环。
- **Async 工具**: 传 `async def` 回调，通过 `asyncio.run()` 在阻塞线程上运行。

### 内置 fs 工具

```python
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(senza.create_fs_tools_plugin())  # bash/read/write/edit
    .env(senza.create_os_env("."))           # 真实文件系统 + shell
    .build()
)
```

## Runtime 层

### WorkflowEngine

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

### Workflow Dict Schema

```python
{
    "entry_step": "step1",       # must be in steps
    "steps": [...],               # list of step dicts
    "edges": [...],               # list of edge dicts
}
```

Step 类型由引擎自动检测：**有 `"executor"` key → Executor step；否则 → LLM step。**

| 字段 | LLM | Executor | 类型 |
|-------|:---:|:--------:|------|
| `id` | ✅ | ✅ | str (unique) |
| `name` | ✅ | ✅ | str |
| `prompt` | ✅ | — | str |
| `allowed_tools` | ✅ | — | str[] (empty = no tools) |
| `structured` | ✅ | — | bool (设 `true` 启用 JSON 提取) |
| `executor` | — | ✅ | str (registry key) |
| `executor_config` | — | ✅ | dict (optional) |

### Edges

```python
{"from": "step1", "to": "step2"}                                           # unconditional
{"from": "step1", "to": "step2", "condition": "pass"}                      # label (judge interprets)
{"from": "step1", "to": "step2", "condition": {"op": "eq", "pointer": "/status", "value": "ok"}}  # declarative
```

### 声明式 ConditionExpr

| op | params | semantics |
|----|--------|-----------|
| `exists` | `pointer` | path exists in structured |
| `missing` | `pointer` | path does not exist |
| `eq` | `pointer`, `value` | equals |
| `ne` | `pointer`, `value` | not equals |
| `gt` / `gte` / `lt` / `lte` | `pointer`, `value`(float) | numeric comparison |

`pointer` uses RFC 6901 JSON Pointer (e.g. `/status`, `/data/0/score`).

**Auto-enable**: if any edge has an Expr condition and judge is NoopJudge, engine auto-switches to built-in `EdgeConditionJudge`.

### Judge

```python
def my_judge(ctx: dict) -> str:
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

| 返回值 | 含义 |
|--------|------|
| `"to:<step_id>"` | 跳转到指定 step |
| `"retry"` | 重跑当前 step（计入 retry_count） |
| `"fail:<reason>"` | 标记工作流失败 |
| `"abort:<reason>"` | 结束工作流（视为成功完成） |
| `"done"` | 同 `abort:done`，结束工作流 |

### Judge ctx 字段

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

### Executor

```python
senza.create_composite_judge()           # CompositeJudge（按节点注册独立路由）
senza.create_executor(callback)           # Python 回调执行器
senza.create_shell_executor(commands)     # Shell 命令执行器（命令白名单，需配合 create_os_env）
senza.create_http_executor(allowed_hosts) # HTTP 调用执行器（host 白名单）
senza.create_fs_tools_plugin()       # bash/read/write/edit 四件套 Plugin（需配合 create_os_env）
senza.create_os_env(working_dir=".")      # OS 文件系统 + shell 执行环境（传给 WorkflowEngine(env=...)）
```

### Shared Context

```python
# Set before run
engine.set_context_variable("user_input", "hello")

# Executor reads context
def my_executor(ctx):
    user_input = ctx["context"]["user_input"]
    return {"output": f"Processed: {user_input}"}
```

### WorkflowEvent 类型 (subscribe)

| type | fields |
|------|--------|
| `step_started` | `step_id`, `step_name` |
| `step_finished` | `step_id`, `output`, `structured`, `tool_calls_count` |
| `paused` | `reason` |
| `resumed` | — |
| `cancelled` | `reason` |
| `failed` | `error` |

## Hooks（11 种）

```python
senza.create_before_turn_hook(cb)         # cb(ctx: dict) -> None
senza.create_after_turn_hook(cb)          # cb(ctx: dict) -> None
senza.create_before_run_hook(cb)          # cb(ctx: dict) -> None
senza.create_after_provider_response_hook(cb)  # cb(ctx: dict) -> None
senza.create_before_provider_request_hook(cb)  # cb(ctx: dict) -> None
senza.create_before_tool_call_hook(cb)    # cb(ctx: dict) -> str | None
senza.create_after_tool_call_hook(cb)     # cb(ctx: dict) -> str | dict
senza.create_should_stop_hook(cb)         # cb(ctx: dict) -> bool
senza.create_before_compact_hook(cb)      # cb(ctx: dict) -> Any
senza.create_transform_context_hook(cb)   # cb(ctx: dict) -> dict
senza.create_prepare_next_turn_hook(cb)   # cb(ctx: dict) -> Optional[dict]
```

## Pricing

```python
senza.create_pricing_provider(table)              # 静态定价表 dict
senza.create_pricing_provider_callback(cb)        # cb(model, provider) -> dict | None
```

## Budget

```python
senza.create_budget_exceeded_hook(cb)  # cb(cost: dict, limit: float) -> bool
```

## Rules 审批

```python
senza.create_contains_predicate(allowed)              # tool_name ∈ allowed
senza.create_regex_field_predicate(arg_path, pattern) # args[arg_path] 匹配正则
senza.create_number_range_predicate(arg_path, min, max) # 数值区间
senza.create_rate_limit_predicate(max, window_seconds)  # 限流

chain = senza.create_rule_chain().rule("search", pred, "allow").fallback("deny").build()
hook = senza.create_rule_approval_hook(chain)  # → BeforeToolCallHook
```

## Skills

```python
senza.load_skills(path)  # 扫描目录下的 SKILL.md，返回 list[Skill]
```

## Event Channel（人工介入）

```python
handle, wait_tool = senza.create_event_channel("review-task")
# wait_tool 注册到 WorkflowEngine.with_external_tool(wait_tool)
# LLM 调用 wait_for_external_event 时暂停，直到 handle.submit() 被调用
handle.submit("approved", {"feedback": "Looks good!"})
```

## Session Viewer

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
