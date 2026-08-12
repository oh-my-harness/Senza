"""01 — JSONL Audit Sink with hash-chain validation.

Demonstrates:
  - JsonlAuditSink: tamper-evident JSONL audit log with SHA-256 chain
  - JsonlAuditSink.validate(path): verify integrity, returns entry count
  - Integration with AuditPlugin for end-to-end audit logging

Each JSON line includes a `prev_hash` field linking to the SHA-256 of the
previous line. Tampering with any entry breaks the chain, detectable via
the static validate() method.
"""

import os
import tempfile

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    audit_path = os.path.join(tempfile.gettempdir(), "senza_infra_audit.jsonl")

    # 1. Create the sink directly (infra-level). The file is opened lazily,
    #    so touch an empty file here so validate() can read it immediately.
    senza.JsonlAuditSink(path=audit_path)
    with open(audit_path, "w"):
        pass
    print(f"JsonlAuditSink created at: {audit_path}")

    # 2. Also wire it via AuditPlugin on a harness
    plugin = senza.strategy.audit(sink_path=audit_path, trace_id="infra-demo", task_id="task-001")
    harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).plugin(plugin).env(env).build()

    # 3. Validate integrity (0 entries since no turns ran)
    count = senza.JsonlAuditSink.validate(audit_path)
    print(f"Validation passed: {count} entries verified.")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
