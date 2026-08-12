"""02 — Memory Service: MemoryPlugin with secure write policy.

Demonstrates:
  - InMemoryStore: volatile memory backend keyed by read_source_id
  - SecureMemoryWritePolicy: validates writes against a schema/config
  - MemoryPlugin: gives the LLM a `memory_write` tool with guardrails

The memory plugin lets the LLM persist facts across turns. Writes pass
through SecureMemoryWritePolicy, which can enforce field schemas, size
limits, and content redaction before data hits the store.
"""

import os
import tempfile

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    doc_dir = tempfile.mkdtemp(prefix="senza_mem_")
    source = senza.knowledge.local_source(
        path=doc_dir, source_id="memory-store"
    )
    store = senza.knowledge.memory_store(read_source_id="memory-store")

    policy_config = {
        "max_value_bytes": 2048,
        "allowed_keys": ["preference", "fact", "decision", "entity"],
    }
    policy = senza.knowledge.secure_write_policy(config=policy_config)
    gate = senza.knowledge.allow_all_gate()

    plugin = senza.knowledge.memory_plugin(
        source=source, store=store, policy=policy, gate=gate
    )

    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .env(env)
        .build()
    )

    print("MemoryPlugin installed (InMemoryStore + SecureWritePolicy).")
    print(f"  allowed keys: {policy_config['allowed_keys']}")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
