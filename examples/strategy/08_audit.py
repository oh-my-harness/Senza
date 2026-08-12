"""08 — Audit Plugin.

Demonstrates:
  - AuditPlugin: writes every tool call + result to a JSONL audit log
  - SHA-256 hash-chain for tamper-evident integrity
  - Optional trace_id and task_id correlation

AuditPlugin captures before_tool_call / after_tool_call events and appends
them as structured JSON lines to sink_path. Each line links to the previous
via a rolling hash, so post-hoc tampering is detectable.
"""

import os
import tempfile

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.create_openai_provider(api_key=api_key)
    env = senza.create_os_env(".")

    audit_path = os.path.join(tempfile.gettempdir(), "senza_audit.jsonl")
    plugin = senza.create_audit_plugin(
        sink_path=audit_path,
        trace_id="trace-001",
        task_id="task-042",
    )

    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .env(env)
        .build()
    )

    print(f"AuditPlugin writing to: {audit_path}")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
