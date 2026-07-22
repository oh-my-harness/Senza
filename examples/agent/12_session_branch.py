"""12 — Session Branching: fork conversations and explore alternatives.

Demonstrates the session tree API:
  - ``read_active_path()`` — entries on the current cursor path (root-first)
  - ``fork_branch(from_entry, label)`` — create a new branch starting from
    a historical entry; returns the new leaf entry ID
  - ``navigate_tree(target)`` — switch the active cursor to another entry
  - ``list_branches()`` — all branch leaves with metadata
  - ``read_all_entries()`` — every node in the session tree
  - ``generate_branch_summary(leaf)`` — AI-generated summary of a branch
  - ``delete_branch(leaf)`` — remove a branch

Each ``prompt()`` call appends a new entry to the session tree. Entries
have ``id``, ``parent_id``, ``timestamp``, and ``payload``. Forking from
an earlier entry lets you explore a different direction without losing
the original conversation.

Scenario: a planning assistant. We run two turns, fork from the first
turn to explore an alternative approach, compare both branches, then
generate a summary of the alternative branch.

Prerequisites:
  - Set OPENAI_API_KEY env var

Run:
  python 12_session_branch.py
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)
    model = os.environ.get("SENZA_MODEL", "gpt-4o")

    harness = (
        senza.HarnessBuilder(model)
        .provider("*", provider)
        .system_prompt("You are a project planning assistant. Be concise.")
        .max_tokens(512)
        .build()
    )

    # ── Turn 1: initial question ──────────────────────────────────────────
    print("=== Turn 1 ===")
    harness.prompt("I want to build a real-time chat app. What architecture do you suggest?")
    harness.wait_for_idle()
    print(f"  Response: {_last_text(harness)[:120]}...")

    # ── Capture the entry ID after turn 1 for forking later ───────────────
    path = harness.read_active_path()
    turn1_entry = path[-1]["id"]
    print(f"  Entry after turn 1: {turn1_entry}")
    print(f"  Active path length: {len(path)}")

    # ── Turn 2: continue the main branch ──────────────────────────────────
    print("\n=== Turn 2 (main branch) ===")
    harness.prompt("Tell me more about the database choice for this architecture.")
    harness.wait_for_idle()
    print(f"  Response: {_last_text(harness)[:120]}...")

    path = harness.read_active_path()
    main_leaf = path[-1]["id"]
    print(f"  Main branch leaf: {main_leaf}")
    print(f"  Active path length: {len(path)}")

    # ── Fork from turn 1 to explore an alternative ────────────────────────
    print(f"\n=== Fork from turn 1 ({turn1_entry}) ===")
    alt_leaf = harness.fork_branch(from_entry=turn1_entry, label="serverless-alt")
    print(f"  New branch leaf: {alt_leaf}")

    # Navigate to the new branch
    harness.navigate_tree(target=alt_leaf)
    print(f"  Navigated to: {alt_leaf}")

    # ── Turn 3 on the alternative branch ──────────────────────────────────
    print("\n=== Turn 3 (alternative branch) ===")
    harness.prompt("What if I used a serverless architecture with WebSocket APIs instead?")
    harness.wait_for_idle()
    print(f"  Response: {_last_text(harness)[:120]}...")

    alt_path = harness.read_active_path()
    print(f"  Alt branch path length: {len(alt_path)}")

    # ── List all branches ─────────────────────────────────────────────────
    print("\n=== All branches ===")
    branches = harness.list_branches()
    for b in branches:
        print(f"  - leaf={b['leaf_id']}")
        print(f"    label={b['label']}")
        print(f"    messages={b['message_count']}")
        print(f"    last_activity={b['last_activity']}")
        summary = b.get("summary")
        if summary:
            print(f"    summary={summary[:80]}...")

    # ── Compare branch paths ──────────────────────────────────────────────
    print(f"\n=== Total entries in session tree: {len(harness.read_all_entries())} ===")

    # ── Generate AI summary for the alternative branch ────────────────────
    print(f"\n=== AI summary of alternative branch ({alt_leaf}) ===")
    try:
        summary = harness.generate_branch_summary(leaf=alt_leaf)
        if isinstance(summary, dict):
            print(f"  {summary}")
        else:
            print(f"  {summary}")
    except Exception as e:
        print(f"  [skipped] {e}")

    # ── Clean up: delete the alternative branch ───────────────────────────
    print(f"\n=== Delete alternative branch ({alt_leaf}) ===")
    harness.navigate_tree(target=main_leaf)
    harness.delete_branch(leaf=alt_leaf)
    print(f"  Branches after deletion: {len(harness.list_branches())}")

    # ── Verify we're back on the main branch ─────────────────────────────
    main_path = harness.read_active_path()
    print(f"\nMain branch path length: {len(main_path)}")
    print(f"Main leaf: {main_path[-1]['id']}")


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
