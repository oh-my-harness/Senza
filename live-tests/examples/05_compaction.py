"""05 — Compaction: auto-compact driven by token thresholds, verify recall.

Mirrors runtime `05_compaction.rs`. Senza's Python surface configures compaction
on the builder (context window + keep-recent + reserve tokens) and emits
`compaction_start` / `compaction_end` events; there is no manual `compact()`
method (that is runtime-only). Demonstrates:
  - Configuring a small context window to force auto-compact
  - Observing compaction_start / compaction_end events in the stream
  - Verifying the LLM can still recall summarized facts afterwards

Run:
  source ~/.omp_llm_env && python live-tests/examples/05_compaction.py
"""

from _common import live_model, make_example_harness, run_prompt, text_of


def count_compactions(events) -> int:
    return sum(1 for e in events if e["type"] == "compaction_end")


def main() -> None:
    print("=== 05: Compaction ===\n")
    harness = make_example_harness(
        lambda b: (
            b.model_info(context_window=800, max_tokens=1024)
            .compaction_model(live_model(), context_window=200_000, max_tokens=4096)
            .compaction_reserve_tokens(50)
            .compaction_keep_recent_tokens(100)
            .auto_compact(True)
        )
    )

    # Build up history; stop after the first auto-compact fires so a second
    # compaction boundary (documented NoValidBoundary path) isn't forced.
    total = 0
    for i in range(1, 11):
        events = run_prompt(
            harness,
            f"Tell me fact #{i} about space.",
            timeout_ms=60_000,
        )
        fired = count_compactions(events)
        total += fired
        if fired:
            print(f"Turn {i:2}: auto-compact triggered (total: {total})")
            break
        print(f"Turn {i:2}: {text_of(events).strip()[:60]}")
    print(f"\nAuto-compact fired: {total > 0} (total compactions: {total})")

    # Verify the LLM can recall summarized history after compaction.
    events = run_prompt(harness, "What facts about space did I ask about?", timeout_ms=60_000)
    print(f"Post-compaction recall: {text_of(events).strip()[:150]}")

    print("\n--- Summary ---")
    print(f"Auto-compact events observed: {total}")


if __name__ == "__main__":
    main()
