"""03 — Status Panel Plugin.

Demonstrates:
  - StatusPanelPlugin: real-time dashboard of harness state
  - Tracks turn count, token usage, active tools, and elapsed time

StatusPanelPlugin installs after_turn hooks that maintain a live status dict.
Query it via harness state inspection to see how many turns have elapsed,
total tokens consumed, and which tools are active.
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.create_openai_provider(api_key=api_key)
    env = senza.create_os_env(".")

    plugin = senza.create_status_panel_plugin()

    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .env(env)
        .build()
    )

    print(f"StatusPanelPlugin installed. Harness phase: {harness.phase()}")
    print("Live metrics: turns, tokens, active tools, elapsed time.")


if __name__ == "__main__":
    main()
