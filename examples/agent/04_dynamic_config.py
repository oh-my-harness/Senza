"""04 — Dynamic Configuration: change model, system prompt, and temperature at runtime.

Demonstrates the newly exposed AgentHarness methods:
  - set_model()
  - set_system_prompt()
  - set_temperature()
  - set_thinking_level()
  - set_max_tokens()
  - usage() / reset_usage()

Run:
  python 04_dynamic_config.py
"""
import os
import sys

import senza as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    harness = (
        lh.HarnessBuilder(os.environ.get("SENZA_MODEL", "gpt-4o"))
        .provider("gpt-*", provider)
        .system_prompt("You are a helpful assistant.")
        .max_tokens(256)
        .build()
    )

    # Dynamically reconfigure
    harness.set_system_prompt("You are a pirate. Answer in pirate speak.")
    harness.set_temperature(0.9)
    harness.set_max_tokens(128)

    print("Prompt 1 (pirate mode)...")
    events = harness.prompt_and_collect("Hello, how are you?", timeout_ms=15000)
    for event in events:
        if event["type"] == "text_delta":
            print(event.get("text", ""), end="")
        elif event["type"] == "settled":
            break
    print()

    # Switch to a different model and persona
    harness.set_model("gpt-4o-mini")
    harness.set_system_prompt("You are a formal academic. Be precise and cite sources.")
    harness.set_temperature(0.3)
    harness.set_thinking_level("medium")

    print("\nPrompt 2 (academic mode)...")
    events = harness.prompt_and_collect("What is the capital of France?", timeout_ms=15000)
    for event in events:
        if event["type"] == "text_delta":
            print(event.get("text", ""), end="")
        elif event["type"] == "settled":
            break
    print()

    # Check accumulated cost
    cost = harness.usage()
    print(f"\nTotal tokens: {cost['total_input_tokens']} in / {cost['total_output_tokens']} out")
    print(f"Estimated cost: ${cost['total_cost']:.4f}")

    # Reset cost tracking
    harness.reset_usage()
    print(f"After reset: {harness.usage()['total_input_tokens']} tokens")


if __name__ == "__main__":
    main()
