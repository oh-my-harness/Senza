"""07 — Hooks: observe and intercept the turn/tool lifecycle.

Mirrors runtime `07_Hooks.rs`. Demonstrates the before_turn / after_turn /
before_tool_call / after_tool_call hooks via senza.hooks.*, including the
symmetry invariant that every tool call has a matching before/after pair.
Also registers after_run (post-run cleanup) and on_abort (abort signal) to
show the full lifecycle bookends.

Note: the runtime example also registers `before_run`, `should_stop` and the
`prepare_next_turn` hook. In Senza's Python surface, `should_stop` returning
`False` can keep the loop from settling (divergence worth investigating);
this example sticks to the turn + tool lifecycle hooks that behave cleanly.

Run:
  source ~/.omp_llm_env && python live-tests/examples/07_hooks.py
"""

import json
from collections import Counter

import senza
from _common import make_example_harness, run_prompt, text_of

counts = Counter()


def before_turn(ctx):
    counts["before_turn"] += 1


def after_turn(ctx):
    counts["after_turn"] += 1


def before_tool_call(ctx):
    counts["before_tool_call"] += 1
    return "allow"


def after_tool_call(ctx):
    counts["after_tool_call"] += 1
    return "passthrough"


def after_run():
    counts["after_run"] += 1


def on_abort():
    counts["on_abort"] += 1


def get_weather(args, ctx):
    city = args.get("city", "unknown")
    return {
        "content": [{"type": "text", "text": f"The weather in {city} is sunny, 22°C."}],
        "terminate": False,
    }


def main() -> None:
    print("=== 07: Hooks ===\n")
    weather_tool = senza.create_tool(
        name="get_weather",
        description="Get current weather for a city",
        parameters_schema=json.dumps(
            {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            }
        ),
        callback=get_weather,
    )
    harness = make_example_harness(
        lambda b: (
            b.system_prompt("Use the get_weather tool to answer weather questions.")
            .tool(weather_tool)
            .hooks(
                [
                    senza.hooks.before_turn(before_turn),
                    senza.hooks.after_turn(after_turn),
                    senza.hooks.before_tool_call(before_tool_call),
                    senza.hooks.after_tool_call(after_tool_call),
                    senza.hooks.after_run(after_run),
                    senza.hooks.on_abort(on_abort),
                ]
            )
        )
    )

    events = run_prompt(harness, "What's the weather in Tokyo?", timeout_ms=60_000)
    print(f"Response: {text_of(events).strip()[:120]}\n")

    print("Hook counts:")
    for name in sorted(counts):
        print(f"  {name}: {counts[name]}")
    ok = counts["before_tool_call"] == counts["after_tool_call"]
    print(f"\nTool-call before/after symmetry: {ok}")


if __name__ == "__main__":
    main()
