"""18 — Loop Safety: run with the loop_safety() guard plugin attached.

Mirrors runtime `18_loop_safety.rs`. Demonstrates:
  - Attaching `senza.strategy.loop_safety()` via `.plugin(...)`
  - Giving the model a prompt that encourages repetitive tool calls
  - Confirming the run settles instead of spinning in a runaway loop

The runtime plugin bundles several guards behind one config (a hard cap on
total turns, a repetition guard that fingerprints tool name + canonical args,
a failure circuit breaker and a death-spiral guard). In Senza's Python surface
`loop_safety(config=None)` takes an opaque dict; this example uses the default
guards and relies on them to stop a loop-free, non-repeating run cleanly.

Note: the runtime example walks each guard individually by configuring
sub-configs (max_turns, repetition_guard, failure_circuit_breaker,
death_spiral_guard). Senza's Python API exposes only the single `config`
dict (no per-guard factories), so this example keeps the default config and
verifies the observable contract: a well-behaved run settles with no runaway
tool-call loop.

Run:
  source ~/.omp_llm_env && python live-tests/examples/18_loop_safety.py
"""

import json

import senza
from _common import make_example_harness, run_prompt, text_of


def _echo(args, ctx):
    """Echo the provided text back verbatim (never terminates)."""
    msg = args.get("text", "(no text)")
    return {
        "content": [{"type": "text", "text": msg}],
        "terminate": False,
    }


def _summarize(events):
    """Print a compact event summary and return (tool_calls, settled)."""
    by_type = {}
    tool_calls = 0
    settled = False
    first_error = None
    for ev in events:
        t = ev["type"]
        by_type[t] = by_type.get(t, 0) + 1
        if t == "tool_call_start":
            tool_calls += 1
        elif t == "settled":
            settled = True
        elif t == "error" and first_error is None:
            first_error = ev.get("error") or ev.get("message")
    print("  Event counts:")
    for k in sorted(by_type):
        print(f"    {k}: {by_type[k]}")
    print(f"  echo tool calls:   {tool_calls}")
    print(f"  settled:           {settled}")
    if first_error:
        print(f"  first error:       {first_error}")
    return tool_calls, settled


def main() -> None:
    print("=== 18: Loop Safety ===\n")

    echo_tool = senza.create_tool(
        name="echo",
        description="Echo the provided text verbatim.",
        parameters_schema=json.dumps(
            {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            }
        ),
        callback=_echo,
    )

    harness = make_example_harness(
        lambda b: (
            b.system_prompt("You have an 'echo' tool. Call it when asked; it never terminates.")
            .plugin(senza.strategy.loop_safety())
            .tool(echo_tool)
        )
    )

    # Encourage multiple identical tool calls with no terminating result — the
    # guard must keep the loop bounded and let the run settle.
    prompt = (
        "Call the echo tool twice with the SAME text 'same'. "
        "After the second result, stop and report what the tool said."
    )
    print(f"Prompt: {prompt}\n")

    events = run_prompt(harness, prompt, timeout_ms=60_000)
    print("Observation:")
    tool_calls, settled = _summarize(events)
    print(f"  Final text: {text_of(events).strip()[:160]}\n")

    # The loop_safety plugin guards the loop; a run must never spin forever.
    ok = settled and tool_calls <= 4
    print(
        f"EXPECTED: run settled with a bounded number of tool calls "
        f"(<= 4). got settled={settled}, tool_calls={tool_calls} -> {ok}"
    )


if __name__ == "__main__":
    main()
