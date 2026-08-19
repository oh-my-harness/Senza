"""12 — Audit + lifecycle timeline: hash-chain log and hook observations.

Mirrors runtime `12_tracing_audit.rs`. Demonstrates:
  - `senza.strategy.audit(sink_path, trace_id, task_id)` plugin writing
    tool-call audit entries to a JSONL file with SHA-256 hash-chain integrity
  - `senza.JsonlAuditSink.validate(path)` verifying chain integrity after the run
  - A real prompt whose turn produces an auditable tool call

Tracing gap: the runtime wires an `InMemoryTraceExporter` into a
`TracingHookAdapter` across the provider/tool/turn hooks. Senza's Python
surface exposes `senza.infra.in_memory_trace_exporter` (an opaque introspection
type with only `exported_spans()` / `exported_span_count()`) but **no way to
attach it to a harness** — there is no Python binding for the adapter /
`CaptureLevel` / `SpanKind` wiring. As the nearest analog, this example captures
lifecycle events via the `before_provider_request` / `after_provider_response` /
`after_tool_call` / `after_turn` hooks (the same hook slots the runtime adapter
uses). These records are not exported tracing spans and do not prove that the
runtime TraceExporter path is wired from Python.

Run:
  source ~/.omp_llm_env && python live-tests/examples/12_tracing_audit.py
"""

import json
import os
import tempfile

import senza
from _common import make_example_harness, run_prompt, text_of

# Nearest-analog timeline: events collected from the lifecycle hooks the
# runtime's TracingHookAdapter would occupy.
lifecycle_events: list[dict] = []


def before_provider_request(ctx):
    lifecycle_events.append(
        {"hook": "provider_request", "event": "start", "turn": ctx.get("turn_id")}
    )


def after_provider_response(ctx):
    lifecycle_events.append(
        {"hook": "provider_response", "event": "end", "turn": ctx.get("turn_id")}
    )


def after_tool_call(ctx):
    lifecycle_events.append(
        {"hook": "tool_call", "event": "end", "tool": ctx.get("tool_name")}
    )
    return "passthrough"


def after_turn(ctx):
    lifecycle_events.append({"hook": "turn", "event": "end", "turn": ctx.get("turn_id")})


def get_weather(args, ctx):
    city = args.get("city", "unknown")
    return {
        "content": [{"type": "text", "text": f"The weather in {city} is sunny, 22°C."}],
        "terminate": False,
    }


def main() -> None:
    print("=== 12: Tracing & Audit ===\n")

    # JsonlAuditSink opens lazily; touch an empty file so validate() can read it.
    audit_path = os.path.join(tempfile.mkdtemp(), "audit.jsonl")
    with open(audit_path, "w"):
        pass

    weather_tool = senza.create_tool(
        name="get_weather",
        description="Get current weather for a city",
        parameters_schema=json.dumps(
            {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            }
        ),
        callback=get_weather,
    )

    plugin = senza.strategy.audit(sink_path=audit_path, trace_id="lt-12", task_id="demo")
    harness = make_example_harness(
        lambda b: (
            b.system_prompt("Use the get_weather tool to answer weather questions.")
            .tool(weather_tool)
            .plugin(plugin)
            .hooks(
                [
                    senza.hooks.before_provider_request(before_provider_request),
                    senza.hooks.after_provider_response(after_provider_response),
                    senza.hooks.after_tool_call(after_tool_call),
                    senza.hooks.after_turn(after_turn),
                ]
            )
        )
    )

    events = run_prompt(harness, "What's the weather in Tokyo?", timeout_ms=60_000)
    types = [e.get("type") for e in events]
    assert "settled" in types, f"expected settled, got {types}"
    print(f"Response: {text_of(events).strip()[:120]}\n")

    # Audit: validate the JSONL hash-chain written by the plugin.
    status = senza.JsonlAuditSink.validate(audit_path)
    print(f"Audit sink: {audit_path}")
    lines = 0
    with open(audit_path) as f:
        for _ in f:
            lines += 1
    print(f"  entries: {lines} | chain valid (validate()={status} >= 0): {status >= 0}")

    # Nearest analog only: hook observations, not TraceExporter spans.
    print(f"\nLifecycle events (via hooks, not exported spans): {len(lifecycle_events)}")
    for ev in lifecycle_events:
        print(
            f"  {ev['hook']:<18} {ev['event']:<5} "
            f"turn={ev.get('turn')} tool={ev.get('tool', '-')}"
        )


if __name__ == "__main__":
    main()
