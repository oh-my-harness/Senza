"""02 — Tool Calling: register a tool and let the LLM use it.

Demonstrates:
  - create_tool() with a JSON Schema and a Python callback
  - Registering the tool on HarnessBuilder
  - The LLM discovers the tool, calls it, and incorporates the result

Run:
  python 02_tool_calling.py
"""
import json
import os
import sys

try:
    import senza as lh
except ImportError:
    import llm_harness_py as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    def get_weather(args, ctx):
        city = args.get("city", "unknown")
        return {
            "content": [{"type": "text", "text": f"The weather in {city} is sunny, 22°C."}],
            "terminate": False,
        }

    weather_tool = lh.create_tool(
        name="get_weather",
        description="Get current weather for a city",
        parameters_schema=json.dumps({
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        }),
        callback=get_weather,
    )

    harness = (
        lh.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .system_prompt("You are a weather assistant. Use the get_weather tool to answer.")
        .tool(weather_tool)
        .max_tokens(512)
        .build()
    )

    print("Asking about weather...")
    harness.prompt("What's the weather in Tokyo?")

    text = ""
    tool_calls = []
    for event in harness.collect_until_settled(timeout_ms=30000):
        t = event["type"]
        if t == "text_delta":
            text += event.get("text", "")
        elif t == "tool_call_start":
            tool_calls.append(event.get("tool_name", "?"))
        elif t == "settled":
            break

    print(f"Tool calls: {tool_calls}")
    print(f"Response:\n{text}")


if __name__ == "__main__":
    main()
