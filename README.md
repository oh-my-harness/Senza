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
| 🧠 **知识与记忆** | 本地知识源 RAG、长期记忆、跨会话历史召回 |

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
print(senza.version())  # e.g. "1.0.0"
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

provider = senza.providers.openai(api_key="sk-...")

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

provider = senza.providers.openai(api_key="sk-...")

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

`senza.providers.openai` 支持 `base_url` 参数，任何兼容 OpenAI Chat Completions API 的服务都能直接接入（通义千问、DeepSeek、Ollama 等）。见 [Provider 配置指南](docs/providers.md)。

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
    provider = senza.providers.openai(api_key="sk-...")
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

### 策略插件

Senza 内置 12 个策略插件，覆盖安全防护、循环断路、审计日志、注入检测等生产场景：

```python
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(senza.strategy.safety_defaults())   # bash 黑名单 + 路径穿越防护
    .plugin(senza.strategy.loop_safety())        # 死循环/重复/连续失败断路器
    .build()
)
```

### 知识与记忆

给 Agent 挂载本地知识源（RAG）和长期记忆：

```python
# 本地知识源 RAG
docs = senza.knowledge.local_source(
    path="/data/wiki", source_id="wiki",
)
knowledge = senza.knowledge.plugin(sources=[docs])

harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("*", provider)
    .plugin(knowledge)  # LLM 可调用 knowledge_search / knowledge_read
    .build()
)
```

## 示例（Live Tests）

全部可运行的示例已统一收拢到 [`live-tests/examples/`](live-tests/examples/)（仓库根 `examples/`
目录已废弃删除）：23 个运行时同名镜像（`01_prompt_streaming` … `23_infra_integration`）
+ 17 个仓库根迁入示例（`30` … `46`），每个都是驱动真实 LLM 的独立脚本。

```bash
cd live-tests/examples
source ~/.omp_llm_env && python 01_prompt_streaming.py   # 跑真实 DeepSeek
python 30_basic_prompt.py                                # 无 key → 打印 SKIP 并 exit 0
```

`live-tests/` 另含按架构层组织的**真实 LLM 集成测试**（agent / loop / tools / runtime /
strategy），镜像 runtime 仓库的 `llm-harness-live-tests` 惯例；每层含一个不依赖 key 的
离线构造冒烟。详见 [`live-tests/README.md`](live-tests/README.md)。

```bash
python -m pytest live-tests/ -v                           # 跑 5 层测试（真实 DeepSeek）
```

> `live-tests/examples/` 中的每个示例都能与 `llm-harness-runtime` 同名示例 1:1 对照
>（同一 DeepSeek-V4-Flash 端点），用于交叉验证两套实现。

---

## API 结构

Senza 的公开 API 分两层：

- **顶层高频 API**：`HarnessBuilder`、`create_tool`、`create_judge`、
  `create_plugin`、`create_fs_tools_plugin`、`create_os_env` 等 —— 每个Agent都会用到的函数。
- **子模块分组**：较低频 API 按领域组织：
  - `senza.providers` — LLM 提供商工厂（`openai`、`anthropic`）
  - `senza.hooks` — 11 个生命周期 hook 工厂
  - `senza.strategy` — 12 个策略插件工厂
  - `senza.knowledge` — 知识源、记忆、会话召回工厂
  - `senza.rules` — 规则链和谓词工厂
  - `senza.infra` — 审计 sink、trace exporter、sandbox 工厂

完整 API 速查（含所有方法签名、事件类型、judge ctx 字段、hooks、rules 等）见 [docs/api-reference.md](docs/api-reference.md)。

## 工具创建

### 用 `@senza.tool` 装饰器创建工具

创建工具的推荐方式是使用 `@senza.tool` 装饰器，它从类型提示自动推导 JSON Schema：

```python
import senza

@senza.tool
def search(query: str) -> str:
    """搜索网络信息。"""
    # 实现...
    return results
```

函数名成为工具名，docstring 成为描述，类型注解定义参数 schema。同步和异步函数均支持。

### 用 `create_tool` 手动创建工具

```python
tool = senza.create_tool(
    name="search",
    description="搜索网络信息",
    parameters={"type": "object", "properties": {"query": {"type": "string"}}},
    callback=lambda args, ctx: {"content": [{"type": "text", "text": "结果"}], "terminate": False},
)
```

`parameters` 接受 dict 或 JSON 字符串。回调签名可以是 `(args, ctx)` 或仅 `(args)`。

## Skills

见 [`skills/`](skills/) 目录（供 Codex 加载的过程性知识）：

- `senza-agent` — Agent 层使用模式
- `senza-workflow` — Runtime 层使用模式
- `senza-advanced` — Hooks、插件、人工介入、执行器
- `senza-strategy` — 策略插件（安全防护、循环断路、审计、注入检测）
- `senza-knowledge` — 知识与记忆（RAG、长期记忆、会话召回）

## 设计文档

见 [`SENZA_DESIGN.md`](SENZA_DESIGN.md) — 完整架构、缺口分析、路线图。

## 开发

开发 Senza 本身见 [DEVELOPMENT.md](DEVELOPMENT.md)——涵盖本地搭建、测试（`./scripts/cargo_checks.sh` 一键跑 fmt+clippy+cargo test+pytest）、发布流程、CI 行为。

## 贡献

欢迎参与！见 [CONTRIBUTING.md](CONTRIBUTING.md) — 涵盖开发环境搭建、测试方法、PR 规范和 good first issue 指引。
