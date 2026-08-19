"""21 — Context-Aware Compaction Prompt.

Mirrors runtime `21_context_aware_compact.rs`. Demonstrates:
  - `senza.strategy.context_aware_compaction_prompt()` — a structured
    (system, user) compaction prompt pair with `## Goal`, `## Progress`,
    `## Key Decisions`, `## Next Steps`, `## Critical Context` sections.
  - Wired in via `HarnessBuilder.compaction_prompt(system_prompt=...,
    user_template=...)` plus a query-focused `.compaction_query(...)`.
  - Auto-compact driven by a small context window after checking that the
    configured template contains the expected structured sections.
  - A second harness uses `Harness.compact()` to trigger the same configured
    prompt manually and prints the returned compaction statistics.

Run:
  source ~/.omp_llm_env && python live-tests/examples/21_context_aware_compact.py
"""

import senza
from _common import live_model, make_example_harness, run_prompt, text_of

SECTIONS = [
    "## Goal",
    "## Progress",
    "## Key Decisions",
    "## Next Steps",
    "## Critical Context",
]


def count_compactions(events) -> int:
    return sum(1 for e in events if e["type"] == "compaction_end")


def check_template_sections(summary: str) -> None:
    """Print which structured sections the summarizer preserved."""
    for section in SECTIONS:
        print(f"  contains '{section}': {section in summary}")


def main() -> None:
    print("=== 21: Context-Aware Compaction Prompt ===\n")

    # Show the context-aware prompt spec structure.
    system_prompt, user_template = senza.strategy.context_aware_compaction_prompt()
    print("Context-aware prompt spec:")
    print(f"  System prompt: {len(system_prompt)} chars")
    print(f"  User template: {len(user_template)} chars")
    for section in SECTIONS:
        print(f"  Template contains '{section}': {section in user_template}")
    print()

    # ── Part 1: Auto-compact with context-aware prompt ──────────────────
    print("--- Part 1: Auto-compact with context-aware prompt (<=10 turns) ---\n")
    harness = make_example_harness(
        lambda b: (
            b.model_info(context_window=1200, max_tokens=1024)
            .compaction_model(live_model(), context_window=200_000, max_tokens=4096)
            .compaction_reserve_tokens(50)
            .compaction_keep_recent_tokens(100)
            .auto_compact(True)
            .compaction_prompt(system_prompt=system_prompt, user_template=user_template)
            .compaction_query("User is building a Rust CLI tool for weather data analysis")
        )
    )
    print("Set compaction query for context-aware summarization")

    # Build history; stop after the first auto-compact fires so a second
    # compaction boundary (documented NoValidBoundary path) isn't forced.
    fired = False
    for i in range(1, 11):
        events = run_prompt(
            harness,
            f"Tell me fact #{i} about the Rust programming language.",
            timeout_ms=60_000,
        )
        if count_compactions(events):
            fired = True
            print(f"Turn {i:2}: auto-compact triggered — {text_of(events).strip()[:60]}...")
            break
        print(f"Turn {i:2}: {text_of(events).strip()[:60]}...")
    print(f"\nAuto-compact fired during conversation: {fired}")

    # Verify the LLM can still recall the summarized conversation.
    events = run_prompt(harness, "What facts about Rust did I ask about?", timeout_ms=60_000)
    print(f"Post-compaction recall: {text_of(events).strip()[:150]}")
    print()

    # ── Part 2: manual compact with the same prompt contract ─────────────
    print("--- Part 2: Manual context-aware compact() ---\n")
    harness2 = make_example_harness(
        lambda b: (
            b.model_info(context_window=16_000, max_tokens=256)
            .compaction_model(live_model(), context_window=200_000, max_tokens=4096)
            .compaction_reserve_tokens(0)
            .compaction_keep_recent_tokens(0)
            .auto_compact(False)
            .compaction_prompt(system_prompt=system_prompt, user_template=user_template)
            .compaction_query("User is discussing database migration strategies")
        )
    )

    for i in range(1, 3):
        events = run_prompt(
            harness2,
            f"Summarize database migration approach #{i} in one short sentence.",
            timeout_ms=60_000,
        )
        print(f"Turn {i}: {text_of(events).strip()[:70]}...")
    stats = harness2.compact()
    print(
        "Manual compact stats: "
        f"{stats['tokens_before']} -> {stats['tokens_after']} tokens, "
        f"{stats['compressed_entries']} entries compressed"
    )

    print("\n--- Summary ---")
    print(
        "Context-aware template sections: Goal/Progress/Key Decisions/Next Steps/Critical Context"
    )
    print(f"Auto-compact fired (Part 1): {fired}")
    print("Manual compact API exercised (Part 2): true")


if __name__ == "__main__":
    main()
