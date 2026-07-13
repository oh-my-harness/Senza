# Senza (森座)

Python SDK for [`llm-harness-runtime`](https://github.com/oh-my-harness/llm-harness-runtime) — built with PyO3.

## Install

```bash
pip install senza
```

## Quick Start

```python
import senza

# Create a provider
provider = senza.create_openai_provider(api_key="sk-...")

# Build a harness
harness = (
    senza.HarnessBuilder("gpt-4o")
    .provider("gpt-*", provider)
    .system_prompt("You are helpful.")
    .build()
)

# Prompt and collect events
harness.prompt("Hello!")
for event in harness.collect_until_settled():
    if event["type"] == "text_delta":
        print(event["text"], end="")
```

## Layers

| Class | Layer | Use case |
|-------|-------|----------|
| `HarnessBuilder` / `AgentHarness` | Agent | Single LLM prompt, tool calling, streaming |
| `WorkflowEngine` | Runtime | Multi-step workflow, conditional routing, crash recovery |

See `examples/` for detailed usage.
