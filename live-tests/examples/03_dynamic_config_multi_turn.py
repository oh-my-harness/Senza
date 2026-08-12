"""03 — Dynamic Config & Multi-Turn: change settings at runtime and continue a conversation.

Mirrors runtime `03_dynamic_config_multi_turn.rs`. Demonstrates:
  - set_system_prompt: change the system prompt between turns
  - set_temperature: change sampling temperature
  - prompt_and_collect: each call continues the session (history preserved)
  - Usage tracking across turns

Run:
  source ~/.omp_llm_env && python live-tests/examples/03_dynamic_config_multi_turn.py
"""

from _common import make_example_harness, text_of


def prompt_turn(harness, label: str, message: str) -> None:
    print(f"--- {label} ---")
    events = harness.prompt_and_collect(message, timeout_ms=60_000)
    print(f"Response: {text_of(events).strip()}\n")


def main() -> None:
    print("=== 03: Dynamic Config & Multi-Turn ===\n")
    harness = make_example_harness()

    # Turn 1: establish two facts to remember.
    prompt_turn(
        harness,
        "Turn 1: Establish facts",
        "My name is Alice and my favorite number is 42. Remember both.",
    )

    # Turn 2-3: verify recall (history preserved).
    prompt_turn(harness, "Turn 2: Verify name recall", "What is my name?")
    prompt_turn(harness, "Turn 3: Verify favorite number recall", "What is my favorite number?")

    # Change system prompt to pirate mode.
    print("--- Changing system prompt to pirate mode ---\n")
    harness.set_system_prompt(
        "You are a pirate. Always speak like a pirate. Use 'Arrr' and nautical terms."
    )
    prompt_turn(
        harness,
        "Turn 4: Pirate mode + recall both facts",
        "Tell me both my name and my favorite number. Answer in character.",
    )

    # Change temperature.
    print("--- Changing temperature to 0.7 (creative) ---\n")
    harness.set_temperature(0.7)
    prompt_turn(
        harness,
        "Turn 5: Creative temperature + pirate still active",
        "Ask me a question about my favorite number, in character.",
    )

    # Summary.
    print("--- Summary ---")
    usage = harness.usage()
    print(f"Total tokens: {usage['total_input_tokens']} in / {usage['total_output_tokens']} out")


if __name__ == "__main__":
    main()
