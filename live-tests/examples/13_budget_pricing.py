"""13 — Budget & Pricing: cost accumulation, pricing, and budget enforcement.

Mirrors runtime `13_budget_pricing.rs`. Demonstrates:
  - `senza.UsageLedger` — caller-owned cost accounting that survives harness
    runs; snapshot via `.snapshot()`
  - `senza.create_pricing_provider_callback(...)` — inject per-model token
    pricing to compute USD cost (see `create_pricing_provider(table)` for the
    static-table form)
  - `HarnessBuilder.pricing(p).usage_ledger(ledger)` — wire pricing + ledger
  - `harness.usage()` / `harness.reset_usage()` — inspect / clear cost
  - `HarnessBuilder.budget(limit, exceeded_hook=...)` + the
    `create_budget_exceeded_hook` callback (continue vs stop)

The `cost` dict exposed by `usage()` / the exceeded hook contains:
  total_input_tokens, total_output_tokens, total_cache_read_tokens,
  total_cache_write_tokens, total_reasoning_tokens, total_cost, by_model

Feature-gap note: the runtime example also builds a standalone
`BudgetControlAdapter` (a pure ShouldStopHook) to show the enforcement wiring
path separately from the accumulator. Senza's Python surface exposes the
equivalent end-to-end wiring directly: `.budget(limit, exceeded_hook=...)` on
the builder wires enforcement to the harness's own cost state (the path the
Rust example documents as requiring runtime-crate access). So there is no
adapter gap here — Part 2 demonstrates the builder `.budget()` path instead.

Run:
  source ~/.omp_llm_env && python live-tests/examples/13_budget_pricing.py
"""

import asyncio

import senza
from _common import make_example_harness, run_prompt, text_of


def _report(label: str, cost: dict) -> None:
    print(
        f"  [{label}] in={cost['total_input_tokens']} "
        f"out={cost['total_output_tokens']} "
        f"cost=${cost.get('total_cost', 0.0):.6f}"
    )
    by_model = cost.get("by_model") or {}
    for model, mc in by_model.items():
        print(
            f"      {model}: in={mc.get('input_tokens')} "
            f"out={mc.get('output_tokens')} "
            f"calls={mc.get('call_count')} "
            f"cost=${mc.get('cost', 0.0):.6f}"
        )


async def main() -> None:
    print("=== 13: Budget & Pricing ===\n")
    # No key = graceful skip (prints SKIP + exit 0).
    make_example_harness()  # gates the key; we build our own harnesses below

    # ── Pricing ─────────────────────────────────────────────────────────────
    # Dynamic callback prices ANY model (mirrors the runtime's FixedPricing).
    # Price per million tokens (USD). A static table keyed by model name works
    # too: senza.create_pricing_provider({model: {...}}).
    pricing = senza.create_pricing_provider_callback(
        lambda _m, _p: {
            "input_per_mtok": 3.0,
            "output_per_mtok": 15.0,
            "cache_read_per_mtok": 0.3,
            "cache_write_per_mtok": 3.75,
        }
    )

    # ══════════════════════════════════════════════════════════════════════
    # Part 1: Cost accumulation across turns via UsageLedger + pricing
    # ══════════════════════════════════════════════════════════════════════
    # Caller-owned ledger: hand a copy to the builder, keep one to snapshot
    # after each turn. Cost accumulates across prompts on the same harness.
    print("── Part 1: Cost accumulation (UsageLedger + pricing) ──\n")

    ledger = senza.UsageLedger()
    harness = make_example_harness(
        lambda b: (
            b.system_prompt("You are a concise, helpful assistant. Answer in one sentence.")
            .pricing(pricing)
            .usage_ledger(ledger)
        )
    )

    turns = [
        ("Turn 1", "In one sentence, explain what a token is in LLMs."),
        ("Turn 2", "In one sentence, what is the difference between input and output tokens?"),
        ("Turn 3", "In one sentence, why does caching reduce cost?"),
    ]
    for label, prompt in turns:
        print(f"--- {label} ---")
        events = run_prompt(harness, prompt, timeout_ms=60_000)
        print(f"  Response: {text_of(events).strip()[:100]}...")
        _report(label, ledger.snapshot())

    print("\n  Ledger snapshot (UsageLedger.snapshot()):")
    snapshot = ledger.snapshot()
    _report("total", snapshot)
    print(
        f"  Cross-check harness.usage() == ledger: "
        f"{abs(harness.usage()['total_cost'] - snapshot['total_cost']) < 1e-9}"
    )

    # ── reset_usage(): clear accumulated cost mid-run ──────────────────────
    print("\n  Reset usage, then one more turn:")
    harness.reset_usage()
    _report("after reset", harness.usage())
    events = run_prompt(harness, "In one sentence, what is a model parameter?", timeout_ms=60_000)
    print(f"  Response: {text_of(events).strip()[:100]}...")
    _report("after 4th turn", harness.usage())

    # ══════════════════════════════════════════════════════════════════════
    # Part 2: Budget enforcement via builder.budget(limit, exceeded_hook)
    # ══════════════════════════════════════════════════════════════════════
    # The runtime example's standalone BudgetControlAdapter maps to the
    # builder's `.budget()` path (see feature-gap note in the docstring).
    # A deliberately tiny budget lets the hook fire during the demo.
    print("\n── Part 2: Budget enforcement (builder.budget) ──\n")

    def on_budget_exceeded(cost, limit):
        print(
            f"  [BudgetExceededHook] limit=${limit:.6f} "
            f"spent=${cost['total_cost']:.6f} "
            f"(in={cost['total_input_tokens']}, out={cost['total_output_tokens']})"
        )
        # False = stop this run; True = surveillance mode (continue).
        return False

    budget_hook = senza.create_budget_exceeded_hook(on_budget_exceeded)
    budget_harness = make_example_harness(
        lambda b: (
            b.system_prompt("You are a concise, helpful assistant.")
            .pricing(pricing)
            .budget(0.001, exceeded_hook=budget_hook)
        )
    )

    print("Prompting with a $0.001 budget (expect the hook to fire)...\n")
    events = run_prompt(
        budget_harness,
        "Explain recursion in three sentences.",
        timeout_ms=60_000,
    )
    types = {e["type"] for e in events}
    print(f"  Event types seen: {sorted(types)}")
    if "budget_exceeded" in types:
        print("  Run was stopped by the budget hook.")
    else:
        print(f"  Response: {text_of(events).strip()[:100]}...")
        print("  (budget was not exceeded this run)")

    usage = budget_harness.usage()
    print("\n  Final harness.usage():")
    _report("budget harness", usage)


if __name__ == "__main__":
    asyncio.run(main())
