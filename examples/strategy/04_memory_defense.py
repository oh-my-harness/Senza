"""04 — Memory Defense Plugin (with builder).

Demonstrates:
  - MemoryDefensePlugin via MemoryDefensePluginBuilder
  - Protects context window from unbounded memory growth
  - Configurable extra-file allowlist for retention

MemoryDefensePlugin trims stale context entries, caps per-source token budgets,
and keeps only the most relevant messages. The fluent builder lets you mark
specific files as "extra" — always retained regardless of compaction.
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    # Fluent builder variant with extra-file retention
    plugin = (
        senza.MemoryDefensePluginBuilder()
        .extra_file("CLAUDE.md")
        .extra_file("AGENTS.md")
        .extra_files(["README.md", "docs/architecture.md"])
        .build()
    )

    harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).plugin(plugin).env(env).build()

    print(f"MemoryDefensePlugin (builder) installed. Phase: {harness.phase()}")
    print("Retained files: CLAUDE.md, AGENTS.md, README.md, docs/architecture.md")


if __name__ == "__main__":
    main()
