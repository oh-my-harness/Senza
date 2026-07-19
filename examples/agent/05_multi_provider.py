"""05 — Multiple Providers: route different models to different providers.

Demonstrates:
  - Registering multiple providers with glob patterns
  - Model routing based on pattern matching

Run:
  OPENAI_API_KEY=sk-... ANTHROPIC_API_KEY=sk-ant-... python 05_multi_provider.py
"""
import os
import sys

import senza as lh


def main():
    openai_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "sk-ant-demo")

    openai_provider = lh.create_openai_provider(api_key=openai_key)
    anthropic_provider = lh.create_anthropic_provider(api_key=anthropic_key)

    # Register both providers — model name determines routing
    harness = (
        lh.HarnessBuilder(os.environ.get("SENZA_MODEL", "gpt-4o"))
        .provider("gpt-*", openai_provider)
        .provider("claude-*", anthropic_provider)
        .system_prompt("You are a helpful assistant.")
        .max_tokens(256)
        .build()
    )

    # Prompt with GPT-4o (routes to OpenAI)
    print("=== GPT-4o ===")
    events = harness.prompt_and_collect("Say hello in one word.", timeout_ms=15000)
    for event in events:
        if event["type"] == "text_delta":
            print(event.get("text", ""), end="")
        elif event["type"] == "settled":
            break
    print()

    # Switch to Claude (routes to Anthropic)
    print("\n=== Claude ===")
    harness.set_model("claude-sonnet-4-20250514")
    events = harness.prompt_and_collect("Say hello in one word.", timeout_ms=15000)
    for event in events:
        if event["type"] == "text_delta":
            print(event.get("text", ""), end="")
        elif event["type"] == "settled":
            break
    print()


if __name__ == "__main__":
    main()
