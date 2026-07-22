"""08 — Budget & Pricing: track token cost and stop when spending exceeds a limit.

Demonstrates:
  - ``create_pricing_provider(table)`` — static per-model price table
    (also see ``create_pricing_provider_callback`` for dynamic pricing)
  - ``create_budget_exceeded_hook(callback)`` — called when cumulative
    cost exceeds the budget; ``callback(cost, limit) -> bool`` returns
    ``True`` to continue or ``False`` to stop and fail.
  - ``HarnessBuilder.pricing(provider).budget(limit, exceeded_hook=...)``
  - ``harness.usage()`` — inspect the cost aggregate afterwards

The ``cost`` dict passed to the hook contains:
  total_input_tokens, total_output_tokens, total_cache_read_tokens,
  total_cache_write_tokens, total_reasoning_tokens, total_cost, by_model

A deliberately tiny budget is set so the hook fires during the demo.

Prerequisites:
  - Set OPENAI_API_KEY env var

Run:
  python 08_budget_pricing.py
"""
import os
import sys

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)
    model = os.environ.get("SENZA_MODEL", "gpt-4o")

    # ── Pricing: price per million tokens (USD) ─────────────────────────────
    # Fields default to 0.0 if omitted, so a minimal table is fine.
    pricing = senza.create_pricing_provider({
        model: {
            "input_per_mtok": 2.5,
            "output_per_mtok": 10.0,
            "cache_read_per_mtok": 1.25,
            "cache_write_per_mtok": 2.5,
        },
    })
    # Alternative: dynamic pricing via a callback
    #   senza.create_pricing_provider_callback(
    #       lambda m, p: {"input_per_mtok": 2.5, "output_per_mtok": 10.0}
    #       if m == model else None)

    # ── Budget exceeded hook: log and stop ──────────────────────────────────
    def on_budget_exceeded(cost, limit):
        print(f"\n  [BUDGET EXCEEDED] limit=${limit:.4f} "
              f"spent=${cost['total_cost']:.4f} "
              f"(in={cost['total_input_tokens']} out={cost['total_output_tokens']})")
        # Return False to stop the run and mark it failed.
        # Return True to let the agent continue despite the overrun.
        return False

    budget_hook = senza.create_budget_exceeded_hook(on_budget_exceeded)

    harness = (
        senza.HarnessBuilder(model)
        .provider("*", provider)
        .system_prompt("You are a concise, helpful assistant.")
        .pricing(pricing)
        # $0.001 — intentionally tiny so the hook fires during the demo.
        .budget(0.001, exceeded_hook=budget_hook)
        .max_tokens(512)
        .build()
    )

    print("Prompting with a $0.001 budget (expect the hook to fire)...\n")
    events = harness.prompt_and_collect(
        "Explain recursion in three sentences.", timeout_ms=30000
    )

    text = ""
    budget_hit = False
    for event in events:
        t = event["type"]
        if t == "text_delta":
            text += event.get("text", "")
        elif t == "error":
            msg = event.get("message", event)
            print(f"\n[error] {msg}", file=sys.stderr)
            budget_hit = True
        elif t == "budget_exceeded":
            budget_hit = True

    if budget_hit:
        print("[budget] run was stopped by the budget hook.")
    else:
        print(f"\nResponse:\n{text}")

    usage = harness.usage()
    print(f"\nFinal cost: ${usage.get('total_cost', 0):.6f} "
          f"(in={usage['total_input_tokens']} out={usage['total_output_tokens']})")


if __name__ == "__main__":
    main()
