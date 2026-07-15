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
pip install senza
```

验证：

```python
import llm_harness_py as lh
print(lh.version())  # e.g. "0.3.0"
```

---

## 快速上手

### Agent：单轮 LLM 对话

```python
import llm_harness_py as lh

provider = lh.create_openai_provider(api_key="sk-...")

harness = (
    lh.HarnessBuilder("gpt-4o")
    .provider("gpt-*", provider)
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
    .provider("gpt-*", provider)
    .tool(tool)
    .build()
)
harness.prompt("东京天气怎么样？")
```

### Runtime：多步工作流

```python
import llm_harness_py as lh

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
lh.create_openai_provider(api_key, base_url=None, parse_reasoning_content=True, tolerant_keepalive=True)
lh.create_anthropic_provider(api_key, base_url=None)
```

### Agent 层

| 方法 | 说明 |
|------|------|
| `HarnessBuilder(model)` | 创建 builder |
| `.provider(pattern, provider)` | 注册 LLM provider（glob 匹配） |
| `.system_prompt(text)` | 设置系统提示 |
| `.max_tokens(n)` / `.temperature(t)` | LLM 参数 |
| `.tool(tool)` / `.plugin(plugin)` | 注册工具/插件 |
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
| `harness.abort()` | 取消当前提示 |

### Runtime 层

| 方法 | 说明 |
|------|------|
| `WorkflowEngine(workflow_dict, provider, model, judge)` | 构造引擎 |
| `.with_tool(tool)` / `.with_executor(name, exec)` | 注册工具/执行器 |
| `.with_hooks([hooks])` | 注册 hooks |
| `.with_task_store(dir)` | 启用持久化 |
| `.with_max_steps(n)` / `.with_max_retries(n)` | 步数/重试上限 |
| `.run()` | 执行（阻塞） |
| `.state()` | "idle"/"running"/"paused"/"succeeded"/"failed"/"cancelled" |
| `.current_step()` / `.step_history()` | 进度查询 |
| `.pause(reason)` / `.resume()` / `.cancel(reason)` | 流程控制 |
| `WorkflowEngine.restore(store_dir, task_id, provider, model, judge)` | 类方法 — 崩溃恢复 |
| `.checkpoint(desc, payload)` / `.total_cost()` | 检查点 & 成本 |
| `.subscribe(timeout_ms=5000)` | 事件流迭代器 |

### Executor

```python
lh.create_executor(callback)           # Python 回调执行器
lh.create_shell_executor(commands)     # Shell 命令执行器（命令白名单）
lh.create_http_executor(allowed_hosts) # HTTP 调用执行器（host 白名单）
```

### Hooks（11 种）

```python
lh.create_before_turn_hook(cb)         # cb(ctx: dict) -> None
lh.create_after_turn_hook(cb)          # cb(ctx: dict) -> None
lh.create_should_stop_hook(cb)         # cb(ctx: dict) -> bool
lh.create_before_tool_call_hook(cb)    # cb(ctx: dict) -> str | None
lh.create_after_tool_call_hook(cb)     # cb(ctx: dict) -> str | dict
# ... 还有 6 种（见 examples/ 和 skills/）
```

---

## 示例

见 [`examples/`](examples/) 目录：

- `examples/agent/` — 5 个示例（基础对话、工具调用、流式输出、动态配置、多 provider）
- `examples/runtime/` — 8 个示例（线性工作流、条件路由、执行器、崩溃恢复、暂停/取消、人工介入、Shell、HTTP）

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
