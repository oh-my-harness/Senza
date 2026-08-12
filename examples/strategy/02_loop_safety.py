"""02 — Loop Safety Plugin.

Demonstrates:
  - LoopSafetyPlugin: detects infinite tool-call loops and terminates them
  - Configurable thresholds via the config dict

LoopSafetyPlugin tracks consecutive identical tool invocations. When the same
tool+args repeat beyond `max_repeats`, the plugin injects a stop signal so the
harness breaks out of the loop instead of burning tokens indefinitely.
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    config = {
        "max_repeats": 3,  # stop after 3 identical calls
        "window_turns": 10,  # look back across last 10 turns
    }
    plugin = senza.strategy.loop_safety(config=config)

    harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).plugin(plugin).env(env).build()

    print(f"LoopSafetyPlugin installed (max_repeats={config['max_repeats']}).")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
