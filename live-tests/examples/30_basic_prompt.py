"""30 — Basic Prompt: send a message and get a response.

Mirrors the runtime `examples/agent/01_basic_prompt.py` minimal flow.
Demonstrates:
  - Building a real provider from the environment (require_provider)
  - Building a harness via make_example_harness
  - Prompting the LLM and collecting events in one turn (run_prompt)
  - Extracting the response text and token usage

Run:
  source ~/.omp_llm_env && python live-tests/examples/30_basic_prompt.py
"""

from _common import make_example_harness, require_provider, run_prompt, text_of


def main() -> None:
    print("=== 30: Basic Prompt ===\n")
    require_provider()

    harness = make_example_harness(
        lambda b: b.system_prompt("You are a concise, helpful assistant.").max_tokens(512)
    )

    prompt = "Explain what a closure is in one sentence."
    print(f'Prompt: "{prompt}"\n')
    print("Sending prompt...\n")

    events = run_prompt(harness, prompt, timeout_ms=60_000)

    print(f"Response:\n{text_of(events)}\n")

    usage = harness.usage()
    print(f"Tokens: {usage['total_input_tokens']} in / {usage['total_output_tokens']} out")


if __name__ == "__main__":
    main()
