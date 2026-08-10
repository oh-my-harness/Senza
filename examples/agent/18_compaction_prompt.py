"""18 — Custom compaction prompt: control how the harness summarizes.

When a conversation grows beyond the context window, the harness compacts
(summarizes) earlier messages to free space. By default it uses a built-in
prompt; `compaction_prompt()` lets you customize both the system prompt
and the user template that drive the summarizer.

Demonstrates:
  - HarnessBuilder.compaction_prompt(system_prompt=..., user_template=...)
    The user_template MUST contain the {conversation} placeholder.
    Supported placeholders: {conversation}, {previous_summary},
    {file_operations}, {query}.
  - model_info(context_window, max_tokens) to set a small window so
    compaction triggers quickly in a demo.
  - compaction_keep_recent_tokens / compaction_reserve_tokens to tune
    how much context is preserved vs. summarized.
  - harness.phase() to observe the compaction lifecycle.

Prerequisites:
  - OPENAI_API_KEY / OPENAI_API_BASE / OPENAI_MODEL set

Run:
  python 18_compaction_prompt.py
"""

import os
import sys

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    model = os.environ.get("SENZA_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-4o")

    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

    harness = (
        senza.HarnessBuilder(model)
        .provider("*", provider)
        .system_prompt("You are a helpful assistant.")
        .max_tokens(256)
        # A small context window so compaction triggers within a few turns.
        .model_info(context_window=800, max_tokens=256)
        # Enable auto-compaction and tune how much recent context is kept.
        .auto_compact(True)
        .compaction_keep_recent_tokens(100)
        .compaction_reserve_tokens(50)
        # Custom compaction prompt — guide the summarizer to preserve
        # decisions and action items. Both arguments are required together;
        # pass None to clear and revert to the default.
        .compaction_prompt(
            system_prompt=(
                "You are a conversation summarizer. "
                "Preserve all decisions, action items, and key facts. "
                "Be concise but lossless with respect to commitments."
            ),
            user_template=(
                "Summarize the following conversation, preserving all "
                "decisions and action items:\n\n{conversation}"
            ),
        )
        .build()
    )

    print("Running a multi-turn conversation to trigger compaction...")
    for i in range(10):
        events = harness.prompt_and_collect(
            f"Tell me about topic {i + 1}: something interesting and detailed.",
            timeout_ms=30_000,
        )
        for event in events:
            if event["type"] == "text_delta":
                print(event.get("text", ""), end="", flush=True)
            elif event["type"] == "compaction_start":
                print("\n  [compaction triggered]", end="", file=sys.stderr)
            elif event["type"] == "compaction_end":
                print(" [done]", file=sys.stderr)
            elif event["type"] == "error":
                print(f"\n[error] {event.get('message', event)}", file=sys.stderr)
        print()

    phase = harness.phase()
    print(f"Final phase: {phase}")

    cost = harness.usage()
    print(f"Tokens: {cost['total_input_tokens']} in / {cost['total_output_tokens']} out")

    harness.shutdown()


if __name__ == "__main__":
    main()
