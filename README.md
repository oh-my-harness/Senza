# Senza (森座)

> **生产级 Agent 运行时 — Rust 性能，Python 易用，崩溃可恢复，成本可控**

Senza 是 oh-my-harness Rust runtime 的 Python SDK，基于 PyO3 构建。面向需要长流程编排、崩溃恢复和成本管控的生产级 AI Agent 场景。

### 核心卖点

| 特性 | 说明 |
|------|------|
| ⚡ **Rust 内核** | PyO3 绑定，比纯 Python 框架更高的吞吐和更低的内存占用 |
| 🛡️ **原生崩溃恢复** | 工作流持久化 + 断点恢复，长流程不丢失进度 |
| 💰 **内置预算管控** | 定价感知 + 预算上限 + 超限回调，每一分钱都看得见 |
| 🔧 **两层 API** | Agent 层（单轮对话/工具调用/流式）+ Runtime 层（多步工作流/条件路由/暂停取消） |

### Showcase

两个完整应用 demo，不是 toy example：

| 项目 | 场景 | 展示能力 |
|------|------|---------|
| [**blender-scene-generator**](https://github.com/oh-my-harness/blender-scene-generator) | 自然语言 → Blender 3D 场景 | AgentHarness + WorkflowEngine + human-in-the-loop |
| [**eda-studio**](https://github.com/oh-my-harness/eda-studio) | LLM 驱动 RTL→GDS 芯片设计全流程 | 长流程编排 + 崩溃恢复 + 失败回环路由 + 多工具协调 |

![Blender demo](https://raw.githubusercontent.com/oh-my-harness/blender-scene-generator/main/docs/examples/rainy_neon_alley.png)

### 与其他框架对比

| 特性 | Senza | LangGraph | CrewAI | AutoGen |
|------|-------|-----------|--------|---------|
| 实现语言 | Rust 内核 + Python SDK | 纯 Python | 纯 Python | 纯 Python |
| 崩溃恢复 | ✅ 原生持久化 + 断点恢复 | ❌ 需自建 checkpoint | ❌ | ❌ |
| 预算管控 | ✅ 内置定价 + 预算上限 | ❌ | ❌ | ❌ |
| 工作流编排 | ✅ 条件路由/暂停/取消 | ✅ 图编排 | ✅ 顺序为主 | ✅ 对话编排 |
| 生产级 demo | ✅ 芯片设计 RTL→GDS | ❌ | ❌ | ❌ |
| 流式输出 | ✅ 原生 async | ✅ | ❌ | ✅ |

---

## 安装

```bash
pip install senza-sdk
```

```python
import senza
print(senza.version())  # e.g. "0.4.9"
```

---

## 快速上手

### 何时用 Agent，何时用 Workflow？

**简单判断**：一个 prompt + 几个工具能完成 → 用 Agent。多个 prompt 串联、条件分支或需要持久化 → 用 Workflow。

| 场景 | 用什么 |
|------|--------|
| 单轮问答 / 工具调用 | `AgentHarness` |
| 多步流程、条件分支 | `WorkflowEngine` |
| 人工介入 / 暂停恢复 | `WorkflowEngine` |
| 崩溃恢复 | `WorkflowEngine` + `with_task_store` |
| 预算管控 | 两者皆可（Agent `.budget()`，Workflow `.with_pricing()`）|

### Agent 示例

```python
import senza

provider = senza.create_openai_provider(api_key="sk-...")

harness = (
    senza.HarnessBuilder("gpt-4o")
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

### Workflow 示例

```python
import senza

provider = senza.create_openai_provider(api_key="sk-...")

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
    return "done"

engine = (
    senza.WorkflowEngine(workflow, provider, "gpt-4o", senza.create_judge(judge))
    .with_max_tokens(256)
)

engine.run()

for record in engine.step_history():
    r = record.get("result")
    print(f"{record['step_id']}: {r['output'][:80] if r else '(无结果)'}")
```

> **Judge 返回值**：`"to:<step_id>"` 跳转 / `"retry"` 重跑 / `"fail:<reason>"` 失败 / `"done"` 结束。详见 [API 参考](docs/api-reference.md#judge)。

---

## 指南

### Provider 配置

`create_openai_provider` 支持 `base_url` 参数，任何兼容 OpenAI Chat Completions API 的服务都能直接接入（通义千问、DeepSeek、Ollama 等）。见 [Provider 配置指南](docs/providers.md)。

### 崩溃恢复

```python
import tempfile

with tempfile.TemporaryDirectory() as store_dir:
    engine = (
        senza.WorkflowEngine(workflow, provider, "gpt-4o", senza.create_judge(judge))
        .with_task_store(store_dir)
    )
    task_id = engine.task_id()
    engine.run()

    # 崩溃后恢复
    restored = senza.WorkflowEngine.restore(store_dir, task_id, provider, "gpt-4o", senza.create_judge(judge))
    print(restored.state(), restored.current_step())
```

### 流式输出

```python
import asyncio
import senza

async def main():
    provider = senza.create_openai_provider(api_key="sk-...")
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .max_tokens(256)
        .build()
    )
    async for event in senza.stream_prompt(harness, "用一句话解释闭包。", timeout_ms=30000):
        if event["type"] == "text_delta":
            print(event.get("text", ""), end="", flush=True)

asyncio.run(main())
```

> `stream_prompt` / `stream_events` / `stream_run` 是模块级 async generator，不是 `AgentHarness` 的方法。

### 内置文件工具

```python
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(senza.create_fs_tools_plugin())  # bash/read/write/edit
    .env(senza.create_os_env("."))           # 真实文件系统 + shell
    .build()
)
```

---

## 示例

见 [`examples/`](examples/) 目录（26 个示例，均可直接运行）：

```bash
export OPENAI_API_KEY=sk-...
python examples/agent/01_basic_prompt.py
python examples/runtime/01_linear_workflow.py
```

- `examples/agent/` — 15 个示例（基础对话、工具调用、流式输出、动态配置、多 provider、hooks、rules、skills、plugins、budget/pricing、steering、session 分支、Anthropic、代码审查模板、RAG 问答模板）
- `examples/runtime/` — 11 个示例（线性工作流、条件路由、执行器、崩溃恢复、暂停/取消、人工介入、Shell、HTTP、CompositeJudge、hooks+重试、数据分析流水线模板）

---

## API 参考

完整 API 速查（含所有方法签名、事件类型、judge ctx 字段、hooks、rules 等）见 [docs/api-reference.md](docs/api-reference.md)。

## Skills

见 [`skills/`](skills/) 目录（供 Codex 加载的过程性知识）：

- `senza-agent` — Agent 层使用模式
- `senza-workflow` — Runtime 层使用模式
- `senza-advanced` — Hooks、插件、人工介入、执行器

## 设计文档

见 [`SENZA_DESIGN.md`](SENZA_DESIGN.md) — 完整架构、缺口分析、路线图。

## 开发

开发 Senza 本身见 [DEVELOPMENT.md](DEVELOPMENT.md)——涵盖本地搭建、测试（`./scripts/cargo_checks.sh` 一键跑 fmt+clippy+cargo test+pytest）、发布流程、CI 行为。

## 贡献

欢迎参与！见 [CONTRIBUTING.md](CONTRIBUTING.md) — 涵盖开发环境搭建、测试方法、PR 规范和 good first issue 指引。
