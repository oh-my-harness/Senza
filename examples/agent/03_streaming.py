"""03 — Streaming: print tokens as they arrive.

Demonstrates:
  - Using events() iterator for real-time streaming
  - Handling different event types (text_delta, tool_call_start, etc.)

Run:
  python 03_streaming.py
"""
import os
import sys

try:
    import senza as lh
except ImportError:
    import llm_harness_py as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    harness = (
        lh.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .system_prompt("You are a creative writer.")
        .max_tokens(1024)
        .build()
    )

    print("Streaming response:\n")
    harness.prompt("Write a short haiku about programming.")

    for event in harness.events(timeout_ms=10000):
        t = event["type"]
        if t == "text_delta":
            print(event.get("text", ""), end="", flush=True)
        elif t == "tool_call_start":
            print(f"\n[calling tool: {event.get('tool_name')}]", flush=True)
        elif t in ("settled", "aborted"):
            break
        elif t == "error":
            print(f"\n[error] {event}", file=sys.stderr)
            break

    print()  # final newline


if __name__ == "__main__":
    main()
