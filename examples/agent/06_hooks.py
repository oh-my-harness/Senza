"""06 — Lifecycle Hooks: observe and control every stage of the agent loop.

Demonstrates all 11 hook types exposed by Senza. Hooks let you observe
(or modify) the agent at well-defined points: per-turn, around provider
calls, around tool calls, before compaction, etc.

This example focuses on the **observability** hooks (they print what they
see) plus the two **decision** hooks that return a value:

  - ``before_tool_call`` — return ``"allow"`` to permit a tool call
  - ``should_stop``      — return ``True`` to stop the agent after a turn

Hook callback signatures (from the Rust FFI):

  before_turn(ctx)             -> None          ctx: {turn_index, model, system_prompt}
  after_turn(ctx)              -> None          ctx: {turn_index, new_messages}
  before_run(ctx)              -> dict|None     return {additional_messages, system_prompt}
  before_provider_request(opts)-> None
  after_provider_response(info)-> None
  before_tool_call(ctx)        -> str|dict      "allow" | "deny" | {"action":"modify","args":..}
  after_tool_call(ctx)         -> str|dict      "passthrough" | {"action":"patch",...}
  should_stop(ctx)             -> bool          ctx: {turn_index, stop_reason, last_assistant}
  before_compact(ctx)          -> str|dict      "proceed"|"skip"|"compact"|{"action":"override",...}
  transform_context(ctx)       -> dict          return {system_prompt, messages}
  prepare_next_turn(ctx)       -> dict|None     return {model, thinking_level, temperature, active_tools}

Prerequisites:
  - Set OPENAI_API_KEY env var (or change the provider config below)

Run:
  python 06_hooks.py
"""
import json
import os
import sys

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

    # ── A simple tool so before_tool_call / after_tool_call fire ────────────
    def get_weather(args, ctx):
        city = args.get("city", "unknown")
        return {
            "content": [{"type": "text", "text": f"The weather in {city} is sunny, 22C."}],
            "terminate": False,
        }

    weather_tool = senza.create_tool(
        name="get_weather",
        description="Get current weather for a city",
        parameters_schema=json.dumps({
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        }),
        callback=get_weather,
    )

    # ── Observability hooks: just print what they see ───────────────────────
    def on_before_turn(ctx):
        print(f"  [before_turn] turn={ctx['turn_index']} model={ctx['model']}")

    def on_after_turn(ctx):
        n = len(ctx.get("new_messages", []))
        print(f"  [after_turn]  turn={ctx['turn_index']} new_messages={n}")

    def on_before_provider_request(opts):
        print(f"  [before_provider_request] keys={sorted(opts.keys())}")

    def on_after_provider_response(info):
        print(f"  [after_provider_response] keys={sorted(info.keys())}")

    # ── Decision hooks: return a value that controls the agent ─────────────
    def on_before_tool_call(ctx):
        name = ctx["tool_name"]
        print(f"  [before_tool_call] tool={name} args={ctx['args']}")
        # Returning "allow" permits the call. Other options:
        #   "deny"                                    -> block, empty result
        #   {"action": "deny", "result": {...}}       -> block, custom result
        #   {"action": "modify", "args": {...}}       -> rewrite arguments
        return "allow"

    def on_after_tool_call(ctx):
        print(f"  [after_tool_call] tool={ctx.get('tool_name', '?')}")
        # "passthrough" keeps the tool result unchanged.
        return "passthrough"

    def on_should_stop(ctx):
        reason = ctx.get("stop_reason", "")
        print(f"  [should_stop] turn={ctx['turn_index']} reason={reason}")
        # Stop as soon as the model signals end_turn (normal completion).
        return reason == "end_turn"

    hooks = [
        senza.create_before_turn_hook(on_before_turn),
        senza.create_after_turn_hook(on_after_turn),
        senza.create_before_provider_request_hook(on_before_provider_request),
        senza.create_after_provider_response_hook(on_after_provider_response),
        senza.create_before_tool_call_hook(on_before_tool_call),
        senza.create_after_tool_call_hook(on_after_tool_call),
    ]

    harness = (
        senza.HarnessBuilder(os.environ.get("SENZA_MODEL", "gpt-4o"))
        .provider("*", provider)
        .system_prompt("You are a weather assistant. Use the get_weather tool to answer.")
        .tool(weather_tool)
        .hooks(hooks)
        .should_stop_hook(senza.create_should_stop_hook(on_should_stop))
        .max_tokens(512)
        .build()
    )

    print("Prompting (watch the hook trace below)...\n")
    events = harness.prompt_and_collect(
        "What's the weather in Tokyo?", timeout_ms=30000
    )

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
