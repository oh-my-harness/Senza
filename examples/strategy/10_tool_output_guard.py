"""10 — Tool Output Guard Plugin.

Demonstrates:
  - ToolOutputGuardPlugin: validates / truncates tool results before context
  - Config-driven limits per tool (max bytes, allowed fields, redaction)

ToolOutputGuardPlugin intercepts after_tool_call events. It enforces output
size limits, strips secrets (API keys, tokens) via regex redaction, and can
truncate verbose stdout — keeping the context window lean and safe.
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.create_openai_provider(api_key=api_key)

    env = senza.create_os_env(".")

    config = {
        "max_output_bytes": 4096,
        "redact_patterns": [
            r"sk-[a-zA-Z0-9]{20,}",
            r"ghp_[a-zA-Z0-9]{36}",
        ],
        "truncate_tools": ["bash", "http_get"],
    }
    plugin = senza.create_tool_output_guard_plugin(env=env, config=config)

    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .env(env)
        .build()
    )

    print("ToolOutputGuardPlugin installed.")
    print(f"  max_output_bytes={config['max_output_bytes']}")
    print(f"  redact_patterns={len(config['redact_patterns'])}")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
