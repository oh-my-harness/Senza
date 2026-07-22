"""01 — Basic Prompt: send a message and get a response.

Demonstrates the minimal Senza flow:
  1. Create an OpenAI-compatible provider
  2. Build a harness via the fluent HarnessBuilder chain
  3. Prompt the LLM and collect events in one call
  4. Extract text from text_delta events

Prerequisites:
  - Set OPENAI_API_KEY env var (or change the provider config below)
  - pip install senza  (or maturin develop from the runtime crate)

Run:
  python 01_basic_prompt.py
"""
import os
import sys

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None

    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

    harness = (
        senza.HarnessBuilder(os.environ.get("SENZA_MODEL", "gpt-4o"))
        .provider("*", provider)
        .system_prompt("You are a concise, helpful assistant.")
        .max_tokens(512)
        .build()
    )

    print("Sending prompt...")
    events = harness.prompt_and_collect("Explain what a closure is in one sentence.", timeout_ms=30000)

    text = ""
    for event in events:
        t = event["type"]
        if t == "text_delta":
            text += event.get("text", "")
        elif t == "error":
            print(f"\n[error] {event.get('message', event)}", file=sys.stderr)
            sys.exit(1)

    print(f"\nResponse:\n{text}")

    cost = harness.usage()
    print(f"\nTokens: {cost['total_input_tokens']} in / {cost['total_output_tokens']} out")


if __name__ == "__main__":
    main()
