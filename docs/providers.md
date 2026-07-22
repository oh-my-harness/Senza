# Provider 配置指南

Senza 内置两个 provider 构造器，通过 `base_url` 参数可覆盖大量 OpenAI 兼容模型。

## OpenAI 兼容 Provider

`create_openai_provider` 支持 `base_url` 参数，任何兼容 OpenAI Chat Completions API 的服务都可以直接接入：

```python
import senza as lh

# 通义千问（DashScope OpenAI 兼容模式）
provider = lh.create_openai_provider(
    api_key="sk-...",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# DeepSeek
provider = lh.create_openai_provider(
    api_key="sk-...",
    base_url="https://api.deepseek.com/v1",
)

# Ollama（本地模型）
provider = lh.create_openai_provider(
    api_key="ollama",  # 任意值
    base_url="http://localhost:11434/v1",
)

harness = (
    lh.HarnessBuilder("deepseek-chat")  # 或 qwen-plus / llama3.2 等
    .provider("*", provider)
    .build()
)
```

## Anthropic Provider

```python
provider = lh.create_anthropic_provider(
    api_key="sk-ant-...",
    base_url=None,  # 可选，自定义 Anthropic 兼容端点
)
```

## 在 WorkflowEngine 中使用

```python
engine = lh.WorkflowEngine(workflow, provider, "deepseek-chat", judge)
```

provider 只需创建一次，传入 `HarnessBuilder` 或 `WorkflowEngine` 即可。
