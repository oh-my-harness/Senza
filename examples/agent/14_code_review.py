"""01 — Code Review Agent: review Python code and report issues.

Demonstrates:
  - HarnessBuilder with a code review system prompt
  - Custom tool for reading code files (simulated)
  - Structured output via prompt_and_collect

Prerequisites:
  - Set OPENAI_API_KEY env var

Run:
  python examples/templates/01_code_review.py
"""
import json
import os
import sys

import senza

SAMPLE_CODE = """
def divide(a, b):
    return a / b

def process_items(items):
    result = []
    for i in range(len(items)):
        result.append(items[i] * 2)
    return result
"""


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

    def read_code(args, ctx):
        """Tool: return the code to review."""
        return {
            "content": [{"type": "text", "text": SAMPLE_CODE}],
            "terminate": False,
        }

    read_tool = senza.create_tool(
        name="read_code",
        description="Read the Python code file to review",
        parameters_schema=json.dumps({
            "type": "object",
            "properties": {},
        }),
        callback=read_code,
    )

    harness = (
        senza.HarnessBuilder(os.environ.get("SENZA_MODEL", "gpt-4o"))
        .provider("*", provider)
        .system_prompt(
            "You are a code reviewer. Use the read_code tool to read the code, "
            "then list all issues found: bugs, style problems, performance issues. "
            "Format output as a numbered list."
        )
        .tool(read_tool)
        .max_tokens(1024)
        .build()
    )

    print("Reviewing code...\n")
    events = harness.prompt_and_collect(
        "Please review the code. Call read_code first, then list all issues.",
        timeout_ms=30000,
    )

    text = ""
    for event in events:
        t = event["type"]
        if t == "text_delta":
            text += event.get("text", "")
        elif t == "tool_call_start":
            print(f"  [tool called: {event.get('tool_name', '?')}]")
        elif t == "error":
            print(f"\n[error] {event.get('message', event)}", file=sys.stderr)
            sys.exit(1)

    print(text)

    cost = harness.usage()
    print(f"\nTokens: {cost['total_input_tokens']} in / {cost['total_output_tokens']} out")


if __name__ == "__main__":
    main()
