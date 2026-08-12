"""31 — Multiple Providers: route different models to different providers.

Mirrors 原仓库根 `examples/agent/05_multi_provider.py`. The runtime example
builds two provider factories directly (OpenAI + Anthropic) and pins each model
to a provider via `.provider(pattern, provider)` glob matching.

What the bare env provides: live-tests configures providers from the
environment via `providers_from_env()` — one OpenAI-compatible entry when
`OPENAI_API_KEY` is set, one Anthropic entry when `ANTHROPIC_API_KEY` is set —
instead of constructing providers by hand (see `_AUTHORING.md`). This example
routes the same prompt through every provider the bare env exposes, showing
that model-to-provider routing is a per-harness decision bound at build time.

Run:
  source ~/.omp_llm_env && python live-tests/examples/31_multi_provider.py
"""

from _common import make_harness, providers_from_env, require_provider, run_prompt


def main() -> None:
    print("=== 31: Multiple Providers ===\n")
    require_provider()  # no-key gate: prints SKIP + exits 0

    entries = providers_from_env()
    print(f"Providers configured from env: {[name for name, _ in entries]}\n")

    prompt = "Say hello in one word."
    for name, provider in entries:
        print(f"--- {name} router ---")
        harness = make_harness(
            provider,
            lambda b: b.system_prompt("You are a helpful assistant.").max_tokens(256),
        )
        events = run_prompt(harness, prompt, timeout_ms=60_000)
        for event in events:
            if event["type"] == "text_delta":
                print(event.get("text", ""), end="")
            elif event["type"] == "settled":
                break
        print("\n")

    print(
        "[note] `make_harness` seeds every harness with the live model and a "
        "`*` provider pattern, so each configured provider serves the same "
        "prompt. The runtime demo pins distinct models to distinct providers "
        "via `.provider(pattern, provider)` per harness."
    )


if __name__ == "__main__":
    main()
