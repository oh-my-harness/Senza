"""01 — Prompt & Streaming: send a prompt and observe token-by-token streaming.

Mirrors runtime `01_prompt_streaming.rs`. Demonstrates:
  - Building a real provider from the environment
  - Building a harness via make_example_harness
  - Streaming events as they arrive (senza.stream_prompt)
  - Collecting the full response text and token usage

Run:
  source ~/.omp_llm_env && python live-tests/examples/01_prompt_streaming.py
"""

import asyncio

import senza
from _common import make_example_harness


async def main() -> None:
    print("=== 01: Prompt & Streaming ===\n")
    harness = make_example_harness()

    prompt = "Explain what a closure is in one sentence."
    print(f'Prompt: "{prompt}"\n')
    print("Streaming response:\n")

    async for event in senza.stream_prompt(harness, prompt, timeout_ms=60_000):
        if event["type"] == "text_delta":
            print(event.get("text", ""), end="", flush=True)
        elif event["type"] in ("settled", "aborted", "error"):
            break

    # Full response text + token usage.
    usage = harness.usage()
    print(f"\n\n--- Tokens: {usage['total_input_tokens']} in / {usage['total_output_tokens']} out")


if __name__ == "__main__":
    asyncio.run(main())
