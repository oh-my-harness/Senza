# Senza (森座)

Python SDK for [`llm-harness-runtime`](https://github.com/oh-my-harness/llm-harness-runtime) — a cffi binding to the Rust `extern "C"` FFI library.

This repo contains **compiled wheels + high-level Python API + examples**.

## Install

```bash
pip install senza
```

## Quick Start

```python
from senza import Harness

with Harness(provider="openai", model="gpt-4", api_key="...") as h:
    h.prompt("Hello!")
    response = h.get_final_response()
    print(response["text"])
```

## Layers

| Class | Layer | Use case |
|-------|-------|----------|
| `Harness` | Agent | Single LLM prompt → streaming response, tool calling |
| `WorkflowEngine` | Runtime | Multi-step workflow orchestration, crash recovery |

See `examples/` for detailed usage.
