"""02 — In-Memory Trace Exporter.

Demonstrates:
  - InMemoryTraceExporter: collects span events for testing / debugging
  - exported_spans(): retrieve accumulated span dicts
  - exported_span_count(): quick count assertion

The trace exporter hooks into the harness's observability layer. In
production you'd use an OTLP exporter; for tests and local debugging, the
in-memory variant captures every span event for inspection.
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    exporter = senza.InMemoryTraceExporter()
    print(f"Trace exporter created: {type(exporter).__name__}")

    # Before any run, the exporter is empty
    spans = exporter.exported_spans()
    count = exporter.exported_span_count()
    print(f"Pre-run spans: {count}")
    print(f"Span list type: {type(spans).__name__}")

    # Build a harness (the exporter would be wired via tracing config)
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .env(env)
        .build()
    )

    print(f"Harness phase: {harness.phase()}")
    print(f"Post-build span count: {exporter.exported_span_count()}")


if __name__ == "__main__":
    main()
