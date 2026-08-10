"""17 — grep/glob: file search tools via FsToolsPlugin.

Demonstrates:
  - senza.create_fs_tools_plugin() bundles 6 tools: read, write, edit,
    bash, grep, glob (auto-registered in runtime v0.5.0)
  - senza.create_os_env(working_dir) as the execution environment
  - The agent uses `grep` to search file contents and `glob` to find
    files by pattern — no custom tool definitions needed

Prerequisites:
  - OPENAI_API_KEY / OPENAI_API_BASE / OPENAI_MODEL set

Run:
  python 17_grep_glob.py
"""

import os
import sys

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    model = os.environ.get("SENZA_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-4o")

    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

    # FsToolsPlugin auto-registers 6 tools: read, write, edit, bash, grep, glob.
    # No manual tool definitions needed — the agent can search files out of the box.
    env = senza.create_os_env(".")  # current directory as working dir
    plugin = senza.create_fs_tools_plugin()

    harness = (
        senza.HarnessBuilder(model)
        .provider("*", provider)
        .system_prompt(
            "You are a coding assistant. Use `glob` to find files by pattern "
            "(e.g. '**/*.py') and `grep` to search file contents. "
            "Report concise results."
        )
        .plugin(plugin)
        .env(env)
        .max_tokens(512)
        .build()
    )

    print("Prompting agent to find and inspect Python files...")
    events = harness.prompt_and_collect(
        "Find all Python files in the current directory with glob, "
        "then use grep to count how many contain 'def main'. "
        "Summarize what you found.",
        timeout_ms=30_000,
    )

    # ── Extract results ──────────────────────────────────────────────
    text = ""
    tool_calls = []
    for event in events:
        t = event["type"]
        if t == "text_delta":
            text += event.get("text", "")
        elif t == "tool_call_start":
            tool_calls.append(event.get("tool_name", "?"))
        elif t == "error":
            print(f"\n[error] {event.get('message', event)}", file=sys.stderr)

    print(f"\nTool calls ({len(tool_calls)}):")
    for tc in tool_calls:
        print(f"  - {tc}")

    print(f"\nAgent response:\n{text}")

    cost = harness.usage()
    print(f"\nTokens: {cost['total_input_tokens']} in / {cost['total_output_tokens']} out")

    harness.shutdown()


if __name__ == "__main__":
    main()
