"""06 — Source Tag Plugin.

Demonstrates:
  - SourceTagPlugin: annotates messages with provenance metadata
  - Entry list maps tool names to human-readable source labels

SourceTagPlugin wraps tool outputs with XML-style source tags so the LLM (and
downstream consumers) can distinguish between e.g. a web-search result, a file
read, and a shell command. This improves citation accuracy and auditability.
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    entries = [
        {"tool": "web_search", "label": "Web", "trust": "low"},
        {"tool": "read_file", "label": "Local File", "trust": "high"},
        {"tool": "bash", "label": "Shell Output", "trust": "medium"},
    ]
    plugin = senza.strategy.source_tag(entries=entries)

    harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).plugin(plugin).env(env).build()

    print(f"SourceTagPlugin installed with {len(entries)} source mappings.")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
