"""05 — Compaction: automatic thresholds plus the manual compact API.

Mirrors runtime `05_compaction.rs`. Senza's Python surface configures compaction
on the builder (context window + keep-recent + reserve tokens) and emits
`compaction_start` / `compaction_end` events. It also exposes
`Harness.compact()` for an explicit compaction request. Demonstrates:
  - Configuring a small context window to force auto-compact
  - Observing compaction_start / compaction_end events in the stream
  - Verifying the LLM can still recall summarized facts afterwards
  - Triggering compaction manually and inspecting its returned statistics

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

    # Manual compaction is a production Python API. Use a fresh harness so this
    # path has an independent compaction boundary after two settled turns.
    print("\n--- Manual compact() ---")
    manual = make_example_harness(
        lambda b: (
            b.model_info(context_window=16_000, max_tokens=256)
            .compaction_model(live_model(), context_window=200_000, max_tokens=4096)
            .compaction_reserve_tokens(0)
            .compaction_keep_recent_tokens(0)
            .auto_compact(False)
        )
    )
    run_prompt(manual, "Remember that the release codename is Aurora.", timeout_ms=60_000)
    run_prompt(manual, "Remember that the launch region is Singapore.", timeout_ms=60_000)
    stats = manual.compact()
    print(
        "Manual compact stats: "
        f"{stats['tokens_before']} -> {stats['tokens_after']} tokens, "
        f"{stats['compressed_entries']} entries compressed"
    )

    print("\n--- Summary ---")
    print(f"Auto-compact events observed: {total}")
    print("Manual compact API exercised: true")


if __name__ == "__main__":
    main()
