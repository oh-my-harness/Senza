"""05 — Injection Filter Plugin.

Demonstrates:
  - InjectionFilterPlugin: strips prompt-injection payloads from tool output
  - Custom pattern list for domain-specific filtering

Tool outputs (web pages, file contents) can contain adversarial instructions
like "ignore previous instructions and ...". InjectionFilterPlugin scans all
tool results before they enter the context window and redacts known injection
patterns.
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    patterns = [
        r"(?i)ignore (all )?previous instructions",
        r"(?i)you are now (a |an )?\w+",
        r"(?i)system:\s",
        r"(?i)forget everything",
    ]
    plugin = senza.strategy.injection_filter(patterns=patterns)

    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .env(env)
        .build()
    )

    print(f"InjectionFilterPlugin installed with {len(patterns)} patterns.")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
