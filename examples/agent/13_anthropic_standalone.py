"""13 — Anthropic Provider & Utilities.

Demonstrates:
  - ``create_anthropic_provider(api_key, base_url, messages_path)`` —
    use Anthropic (Claude) as the LLM provider, with optional
    ``base_url`` / ``messages_path`` for proxies, gateways, or
    Anthropic-compatible endpoints (Azure, Bedrock, self-hosted).
  - ``HarnessBuilder.provider(pattern, provider)`` — route a model name
    pattern to the Anthropic provider.
  - Utilities: ``version()``, ``to_json(obj)``, ``from_json(json_str)``
    — SDK version introspection and JSON serialization helpers for
    event/data round-tripping.

Anthropic vs OpenAI provider:
  - ``create_openai_provider`` uses the OpenAI chat completions wire
    format (``chat_path`` configurable).
  - ``create_anthropic_provider`` uses the Anthropic messages API
    (``messages_path`` configurable, defaults to ``/v1/messages``).
  - Both return an opaque ``Provider`` handle; the rest of the API is
    identical — only the wire format differs.

Scenario: use Claude to answer a question, then demonstrate the JSON
utilities by round-tripping the collected events.

Prerequisites:
  - Set ANTHROPIC_API_KEY env var (or change the config below)

Run:
  python 13_anthropic_standalone.py
"""
import os
import sys

import senza as lh


def main():
    # ── SDK version ───────────────────────────────────────────────────────
    print(f"Senza SDK version: {lh.version()}")

    # ── Anthropic provider ────────────────────────────────────────────────
    api_key = os.environ.get("ANTHROPIC_API_KEY", "sk-ant-demo-key")
    base_url = os.environ.get("ANTHROPIC_API_BASE") or None
    # messages_path defaults to /v1/messages; override for proxies/gateways
    messages_path = os.environ.get("ANTHROPIC_MESSAGES_PATH") or None

    provider = lh.create_anthropic_provider(
        api_key=api_key,
        base_url=base_url,
        messages_path=messages_path,
    )

    model = os.environ.get("SENZA_MODEL", "claude-sonnet-4-20250514")

    harness = (
        lh.HarnessBuilder(model)
        .provider("claude-*", provider)
        .system_prompt("You are a concise, helpful assistant.")
        .max_tokens(512)
        .build()
    )

    print(f"\nUsing Anthropic provider with model: {model}")
    print("Prompting...\n")

    events = harness.prompt_and_collect(
        "Explain the difference between TCP and UDP in two sentences.",
        timeout_ms=30000,
    )

    # ── JSON utilities: round-trip the events ─────────────────────────────
    # to_json serializes a Python object (list[dict]) to a JSON string
    json_str = lh.to_json(events)
    print(f"Serialized {len(events)} events to {len(json_str)} bytes of JSON")

    # from_json parses it back
    restored = lh.from_json(json_str)
    print(f"Deserialized back to {len(restored)} events")

    # Verify round-trip integrity
    assert len(restored) == len(events), "round-trip mismatch!"
    print("Round-trip integrity: OK")

    # Extract text from restored events
    text = ""
    for event in restored:
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
