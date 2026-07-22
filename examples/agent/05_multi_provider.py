"""05 — Multiple Providers: route different models to different providers.

Demonstrates:
  - Registering multiple providers with glob patterns
  - Model routing based on pattern matching

Run:
  OPENAI_API_KEY=sk-... ANTHROPIC_API_KEY=sk-ant-... python 05_multi_provider.py
"""
import os
import sys

import senza


def main():
    openai_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "sk-ant-demo")

    openai_base_url = os.environ.get("OPENAI_API_BASE") or None
    anthropic_base_url = os.environ.get("ANTHROPIC_API_BASE") or None
    openai_provider = senza.create_openai_provider(api_key=openai_key, base_url=openai_base_url)
    anthropic_provider = senza.create_anthropic_provider(api_key=anthropic_key, base_url=anthropic_base_url)

    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    anthropic_model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # Register both providers — model name determines routing via glob patterns.
    # Note: build a separate harness per provider when switching models at runtime,
    # since set_model() does not re-evaluate provider glob matching.

    # Prompt with OpenAI-compatible model (routes to OpenAI provider)
    print(f"=== {openai_model} (OpenAI) ===")
    openai_harness = (
        senza.HarnessBuilder(openai_model)
        .provider("*", openai_provider)
        .system_prompt("You are a helpful assistant.")
        .max_tokens(256)
        .build()
    )
    events = openai_harness.prompt_and_collect("Say hello in one word.", timeout_ms=30000)
    for event in events:
        if event["type"] == "text_delta":
            print(event.get("text", ""), end="")
        elif event["type"] == "settled":
            break
    print()

    # Prompt with Claude (routes to Anthropic provider)
    print(f"\n=== {anthropic_model} (Anthropic) ===")
    anthropic_harness = (
        senza.HarnessBuilder(anthropic_model)
        .provider("*", anthropic_provider)
        .system_prompt("You are a helpful assistant.")
        .max_tokens(256)
        .build()
    )
    events = anthropic_harness.prompt_and_collect("Say hello in one word.", timeout_ms=30000)
    for event in events:
        if event["type"] == "text_delta":
            print(event.get("text", ""), end="")
        elif event["type"] == "settled":
            break
    print()


if __name__ == "__main__":
    main()
