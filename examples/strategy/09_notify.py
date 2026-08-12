"""09 — Notify Plugin.

Demonstrates:
  - NotifyPlugin: sends notifications on key lifecycle events
  - Hooks into after_turn and should_stop to emit alerts

NotifyPlugin fires callbacks when the harness finishes a turn, encounters an
error, or stops. Wire it to desktop notifications, Slack webhooks, or log
aggregators to get real-time awareness of long-running agents.
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    plugin = senza.strategy.notify()

    harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).plugin(plugin).env(env).build()

    print("NotifyPlugin installed — alerts on turn-complete, error, and stop.")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
