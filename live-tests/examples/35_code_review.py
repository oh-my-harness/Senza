"""35 — Code Review: review Python code via a tool and a review system prompt.

Mirrors 原仓库根 examples/agent/14_code_review.py. Demonstrates:
  - Building a harness via make_example_harness
  - Custom tool (read_code) that returns the code to review
  - A code-review system prompt driving the LLM to list issues
  - Collecting the response and token usage via prompt_and_collect

Run:
  source ~/.omp_llm_env && python live-tests/examples/35_code_review.py
"""

import json

import senza
from _common import make_example_harness

SAMPLE_CODE = """
def divide(a, b):
    return a / b

def process_items(items):
    result = []
    for i in range(len(items)):
        result.append(items[i] * 2)
    return result
"""


def main() -> None:
    print("=== 35: Code Review ===\n")

    def read_code(args, ctx):
        """Tool: return the code to review."""
        return {
            "content": [{"type": "text", "text": SAMPLE_CODE}],
            "terminate": False,
        }

    read_tool = senza.create_tool(
        name="read_code",
        description="Read the Python code file to review",
        parameters_schema=json.dumps({"type": "object", "properties": {}}),
        callback=read_code,
    )

    harness = make_example_harness(
        lambda b: (
            b.system_prompt(
                "You are a code reviewer. Use the read_code tool to read the code, "
                "then list all issues found: bugs, style problems, performance issues. "
                "Format output as a numbered list."
            )
            .tool(read_tool)
            .max_tokens(1024)
        )
    )

    print("Reviewing code...\n")
    events = harness.prompt_and_collect(
        "Please review the code. Call read_code first, then list all issues.",
        timeout_ms=60_000,
    )

    tools_used = sorted({e.get("tool_name") for e in events if e["type"] == "tool_call_start"})
    for event in events:
        if event["type"] == "error":
            print(f"\n[error] {event.get('message', event)}")
            return
    print(f"Tools called: {tools_used}\n")
    print(senza.extract_text(events))

    usage = harness.usage()
    print(f"\n--- Tokens: {usage['total_input_tokens']} in / {usage['total_output_tokens']} out")


if __name__ == "__main__":
    main()
