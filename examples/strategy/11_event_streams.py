"""11 — Webhook Event Stream.

Demonstrates:
  - create_webhook_stream: producer/consumer pair for external events
  - WebhookChannel.push() injects events from outside the harness
  - EventStream consumed by the harness as an inline event source

Webhook streams let external systems (CI, webhooks, human reviewers) push
events into a running harness. The channel is the write side; the stream is
read by the harness's event loop.
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    channel, stream = senza.strategy.webhook_stream(buffer=64)

    # Simulate an external webhook firing
    channel.push({"event": "ci_complete", "status": "passed", "build_id": 42})

    harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).env(env).build()

    print("Webhook stream created (buffer=64).")
    print(f"  channel type: {type(channel).__name__}")
    print(f"  stream type:  {type(stream).__name__}")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
