"""02 — Tool Calling: register tools and let the LLM discover and call them.

Mirrors runtime `02_tool_calling.rs`. Demonstrates:
  - Defining tools via senza.create_tool (JSON Schema + Python callback)
  - Registering tools on the builder
  - The LLM discovers tools, calls them, and incorporates results
  - Multiple tool calls

Run:
  source ~/.omp_llm_env && python live-tests/examples/02_tool_calling.py
"""

import json

import senza
from _common import make_example_harness

calls: list[str] = []


def get_weather(args, ctx):
    city = args.get("city", "unknown")
    calls.append(f"weather:{city}")
    return {
        "content": [{"type": "text", "text": f"The weather in {city} is sunny, 22°C."}],
        "terminate": False,
    }


def get_time(args, ctx):
    zone = args.get("timezone", "UTC")
    calls.append(f"time:{zone}")
    return {
        "content": [{"type": "text", "text": f"The current time in {zone} is 14:30."}],
        "terminate": False,
    }


def make_tool(name, description, schema, callback):
    return senza.create_tool(
        name=name,
        description=description,
        parameters_schema=json.dumps(schema),
        callback=callback,
    )


def main() -> None:
    print("=== 02: Tool Calling ===\n")
    weather_tool = make_tool(
        "get_weather",
        "Get current weather for a city",
        {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
        get_weather,
    )
    time_tool = make_tool(
        "get_time",
        "Get current time for a timezone",
        {
            "type": "object",
            "properties": {"timezone": {"type": "string", "description": "IANA timezone"}},
            "required": ["timezone"],
        },
        get_time,
    )

    harness = make_example_harness(
        lambda b: (
            b.system_prompt(
                "You are an assistant with weather and time tools. "
                "Call them to answer the user's question."
            )
            .tool(weather_tool)
            .tool(time_tool)
            .max_tokens(512)
        )
    )

    events = harness.prompt_and_collect(
        "What's the weather in Tokyo and the current time in UTC?", timeout_ms=60_000
    )

    tools_used = sorted({e.get("tool_name") for e in events if e["type"] == "tool_call_start"})
    text = senza.extract_text(events)
    print(f"Tools called: {tools_used}")
    print(f"Callbacks fired: {calls}")
    print(f"Response:\n{text}\n")
    usage = harness.usage()
    print(f"Tokens: {usage['total_input_tokens']} in / {usage['total_output_tokens']} out")


if __name__ == "__main__":
    main()
