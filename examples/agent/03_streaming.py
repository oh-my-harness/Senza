"""03 — Streaming: print tokens as they arrive in real time.

Demonstrates:
  - Using events() iterator for real-time streaming
  - Handling different event types (text_delta, tool_call_start, etc.)

Note: events() must be consumed concurrently with prompt() because
prompt() is blocking. This example uses a background thread to
collect events while the main thread drives the prompt.

Run:
  python 03_streaming.py
"""
import os
import sys
import threading

import senza as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    harness = (
        lh.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .system_prompt("You are a creative writer.")
        .max_tokens(256)
        .build()
    )

    print("Streaming response:\n")

    # Collect events in a background thread while prompt() blocks in the main thread.
    done = threading.Event()

    def stream_events():
        for event in harness.events(timeout_ms=10000):
            t = event["type"]
            if t == "text_delta":
                print(event.get("text", ""), end="", flush=True)
            elif t == "tool_call_start":
                print(f"\n[tool: {event.get('tool_name', '?')}]", flush=True)
            elif t in ("settled", "aborted", "error"):
                done.set()
                break

    stream_thread = threading.Thread(target=stream_events)
    stream_thread.start()

    harness.prompt("Write a short haiku about programming.")
    stream_thread.join(timeout=15)

    print("\n")
    print(f"Phase: {harness.phase()}")
    cost = harness.usage()
    print(f"Tokens: {cost['total_input_tokens']} in / {cost['total_output_tokens']} out")


if __name__ == "__main__":
    main()
