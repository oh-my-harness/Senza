"""01 — Safety Defaults Plugin.

Demonstrates:
  - SafetyDefaultsPlugin: bash command blacklist + path traversal protection
  - Zero-config safety hardening for any harness

SafetyDefaultsPlugin installs before_tool_call / after_tool_call hooks that
block dangerous commands (rm -rf /, curl | sh, etc.) and reject tool outputs
containing filesystem escape sequences (../).
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    plugin = senza.strategy.safety_defaults()

    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .system_prompt("You are a careful, safety-conscious assistant.")
        .plugin(plugin)
        .env(env)
        .build()
    )

    print(f"SafetyDefaultsPlugin installed. Harness phase: {harness.phase()}")
    print("Blocked commands include: rm -rf /, curl|sh, sudo chmod 777, ...")
    print("Path traversal patterns (../) in tool output are stripped.")


if __name__ == "__main__":
    main()
