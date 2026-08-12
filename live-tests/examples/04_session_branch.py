"""04 — Session Persistence & Branching: fork, navigate, branch summary.

Mirrors runtime `04_session_branch.rs` (InMemory session tree part). Demonstrates:
  - read_active_path: entries on the current cursor path (root-first)
  - fork_branch: create an independent branch from a past entry
  - navigate_tree: switch the active cursor to another branch
  - list_branches: all branch leaves with metadata
  - generate_branch_summary: AI-generated summary of a branch
  - delete_branch + back to main branch

Run:
  source ~/.omp_llm_env && python live-tests/examples/04_session_branch.py
"""

from _common import make_example_harness, run_prompt, text_of


def prompt_turn(harness, label: str, message: str) -> str:
    events = run_prompt(harness, message, timeout_ms=60_000)
    print(f"  {label}: {text_of(events).strip()[:120]}")
    return text_of(events)


def main() -> None:
    print("=== 04: Session Persistence & Branching ===\n")
    harness = make_example_harness(
        lambda b: b.system_prompt("You are a concise project planning assistant.").max_tokens(256)
    )

    # ── Turn 1-2: build the main branch ─────────────────────────────────────
    print("--- Part 1: main conversation ---")
    prompt_turn(harness, "Turn 1", "I want to build a real-time chat app. Suggest an architecture.")
    path = harness.read_active_path()
    turn1 = path[0]["id"]
    prompt_turn(harness, "Turn 2", "Tell me more about the database choice.")
    main_leaf = harness.read_active_path()[-1]["id"]
    print(f"  Session entries after 2 turns: {len(path)}")

    # ── Part 2: fork from turn 1 and explore an alternative ─────────────────
    print("\n--- Part 2: fork and branch ---")
    alt_leaf = harness.fork_branch(from_entry=turn1, label="alt")
    harness.navigate_tree(target=alt_leaf)
    print(f"  Forked branch at: {alt_leaf}")
    prompt_turn(
        harness,
        "Branch turn 1",
        "What if I used a serverless architecture with WebSocket APIs instead?",
    )

    branches = harness.list_branches()
    print(f"\n  Branches: {len(branches)}")
    for b in branches:
        summary = b.get("summary") or "(none)"
        print(
            f"    - leaf={b['leaf_id']} label={b['label']} "
            f"messages={b['message_count']} summary={str(summary)[:40]}"
        )

    # ── Part 3: branch summary ──────────────────────────────────────────────
    print("\n--- Part 3: branch summary ---")
    summary = harness.generate_branch_summary(leaf=alt_leaf)
    print(f"  Alternative branch summary: {summary}")

    # ── Part 4: back to main, delete the alternative branch ─────────────────
    print("\n--- Part 4: navigate back + delete branch ---")
    harness.navigate_tree(target=main_leaf)
    harness.delete_branch(leaf=alt_leaf)
    print(f"  Branches after deletion: {len(harness.list_branches())}")
    print(f"  Main leaf: {harness.read_active_path()[-1]['id']}")


if __name__ == "__main__":
    main()
