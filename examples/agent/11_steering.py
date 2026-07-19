"""11 — Steering & Multi-turn: guide a running agent and manage conversation flow.

Demonstrates:
  - ``prompt()`` — start a turn (blocking; completes when the turn ends)
  - ``next_turn(text)`` — queue the next user message, then ``continue_run()``
    to process it
  - ``follow_up(text)`` — inject a message that triggers a new turn
    immediately after the current one ends
  - ``steer(text)`` — inject guidance added to the *next* turn's context
    (does not start a new turn by itself)
  - ``continue_run()`` — resume without adding a new message
  - ``wait_for_idle()`` / ``wait_for_settled()`` — block until the agent
    finishes processing
  - Queue inspection: ``has_queued_messages()``, ``clear_all_queues()``
  - Context manager: ``with HarnessBuilder.build() as harness:`` ensures
    graceful shutdown via ``__enter__`` / ``__exit__``

Steering vs follow-up vs next-turn:
  - ``steer``    — "while you're at it, also consider X" (appended to next
                   turn's context; does not force a new turn)
  - ``follow_up``— "now do X" (queues a message that triggers a new turn
                   as soon as the current one finishes)
  - ``next_turn`` — "here's my next message" (queues a user message;
                   call ``continue_run()`` to process it)

Scenario: a research assistant. We ask a question, then follow up with a
refinement, then steer it to be more concise, then start a fresh turn.

Prerequisites:
  - Set OPENAI_API_KEY env var

Run:
  python 11_steering.py
"""
import os
import sys

import senza as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = lh.create_openai_provider(api_key=api_key, base_url=base_url)
    model = os.environ.get("SENZA_MODEL", "gpt-4o")

    # ── Context manager: __enter__ / __exit__ for clean lifecycle ──────────
    with (
        lh.HarnessBuilder(model)
        .provider("gpt-*", provider)
        .system_prompt("You are a research assistant. Answer clearly and concisely.")
        .max_tokens(512)
        .build()
    ) as harness:

        # ── Turn 1: initial question ──────────────────────────────────────
        print("=== Turn 1: initial question ===")
        harness.prompt("What are the main trade-offs between SQL and NoSQL databases?")
        harness.wait_for_idle()
        print(f"  Response: {_last_text(harness)}")
        print(f"  Messages so far: {harness.message_count()}")

        # ── Turn 2: next_turn + continue_run ──────────────────────────────
        print("\n=== Turn 2: next_turn + continue_run ===")
        harness.next_turn("Which one would you pick for a logging system and why?")
        print(f"  Queued messages: {harness.has_queued_messages()}")  # True
        harness.continue_run()
        harness.wait_for_idle()
        print(f"  Queued after run: {harness.has_queued_messages()}")  # False
        print(f"  Response: {_last_text(harness)}")

        # ── Turn 3: follow_up (auto-triggers a new turn) ──────────────────
        print("\n=== Turn 3: follow_up ===")
        harness.follow_up("Give a concrete example with a specific NoSQL database.")
        harness.continue_run()
        harness.wait_for_settled()
        print(f"  Response: {_last_text(harness)}")

        # ── Turn 4: steer (guidance for the next turn) + next_turn ────────
        print("\n=== Turn 4: steer + next_turn ===")
        harness.steer("Keep the answer under 3 sentences.")
        harness.next_turn("What about transaction support in NoSQL?")
        harness.continue_run()
        harness.wait_for_idle()
        print(f"  Response: {_last_text(harness)}")

        # ── Queue management demo ─────────────────────────────────────────
        print("\n=== Queue management ===")
        # Queue some messages we won't actually process
        harness.next_turn("unused question 1")
        harness.follow_up("unused question 2")
        print(f"  Queued: {harness.has_queued_messages()}")  # True
        harness.clear_all_queues()
        print(f"  After clear_all_queues: {harness.has_queued_messages()}")  # False

        # ── Final stats ───────────────────────────────────────────────────
        print("\n=== Summary ===")
        usage = harness.usage()
        print(f"  Total messages: {harness.message_count()}")
        print(f"  Tokens: {usage['total_input_tokens']} in / "
              f"{usage['total_output_tokens']} out")


def _last_text(harness) -> str:
    """Extract the assistant's last response text from session messages."""
    messages = harness.get_messages()
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
            return ""
    return ""


if __name__ == "__main__":
    main()
