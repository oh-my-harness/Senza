"""23 — Infrastructure Integration: local knowledge + memory + session recall.

Mirrors runtime `23_infra_integration.rs`. The Rust example demonstrates four
parts — EventStream (TimerStream / WebhookStream), Knowledge, and a Memory +
SessionRecall construction demo. Senza's Python surface wires the same
infrastructure differently:

  - Event streams have Python analogs (`senza.strategy.webhook_stream(buffer)`
    -> (WebhookChannel, EventStream) and `senza.create_event_channel(task_id)`
    -> (EventStreamHandle, WaitForExternalEventTool)), but there is no one-shot
    TimerStream in the Python SDK — the nearest analog is the webhook /
    human-in-the-loop event channel.
  - Knowledge: `senza.knowledge.local_source(path, source_id)` +
    `senza.knowledge.plugin(sources=[...])` -> the model gets a `knowledge_search`
    tool.
  - Memory: `senza.knowledge.memory_store(read_source_id)` + `memory_plugin`
    -> `memory_write` / `memory_forget` tools. Requires an explicit write policy
    (`secure_write_policy`) and a mutation gate (`allow_all_gate`); there is no
    permissive default, mirroring the Rust `MemoryMutationGate` boundary.
  - Session recall: `in_memory_session_repo` + a recall index +
    `session_recall_knowledge_source` + `history_recall_plugin` -> auto-injects
    relevant past-session snippets via TransformContextHook (registers no tool).

This example builds a single harness wired with all three (knowledge + memory +
session recall), seeds a local .md knowledge doc, and runs a RAG-style prompt so
the answer reflects the injected source.
Demonstrates:
  - Making local documents searchable via the knowledge plugin
  - Attaching a long-term memory store (memory_write / memory_forget)
  - Walking the session-recall wiring (repo + index -> auto-injecting plugin)
  - Answering a RAG prompt from the seeded knowledge doc

Run:
  source ~/.omp_llm_env && python live-tests/examples/23_infra_integration.py
"""

import tempfile

import senza
from _common import make_example_harness, run_prompt, text_of


def main() -> None:
    print("=== 23: Infrastructure Integration (Knowledge + Memory + SessionRecall) ===\n")

    # Seed a small local knowledge base: the fact the RAG prompt is asked to find.
    with tempfile.TemporaryDirectory() as doc_dir:
        with open(f"{doc_dir}/deploy_guide.md", "w") as f:
            f.write(
                "# Deployment Guide\n\n"
                "The production deployment command is `senza deploy --env prod`.\n"
                "Blue-green deployment reduces downtime.\n"
            )
        with open(f"{doc_dir}/rust_tips.md", "w") as f:
            f.write("# Rust Tips\n\nAlways run cargo fmt before committing code.\n")

        # ── 1. Knowledge: local .md source + knowledge plugin (knowledge_search).
        source = senza.knowledge.local_source(
            path=doc_dir, source_id="deploy-docs", name="Deployment Docs"
        )
        knowledge_plugin = senza.knowledge.plugin(sources=[source])

        # ── 2. Memory: write store keyed to the same read source + explicit
        #    write policy and mutation gate (no permissive default).
        store = senza.knowledge.memory_store(read_source_id="deploy-docs")
        policy = senza.knowledge.secure_write_policy()
        gate = senza.knowledge.allow_all_gate()
        memory_plugin = senza.knowledge.memory_plugin(
            source=source, store=store, policy=policy, gate=gate
        )

        # ── 3. Session recall: index past sessions, then auto-inject via hook.
        repo = senza.knowledge.in_memory_session_repo()
        index = senza.knowledge.in_memory_session_recall_index()
        recall_source = senza.knowledge.session_recall_knowledge_source(repo=repo, index=index)
        recall_plugin = senza.knowledge.history_recall_plugin(source=recall_source)

        # One harness wired with all three plugins.
        harness = make_example_harness(
            lambda b: (
                b.system_prompt(
                    "Use the knowledge_search tool to answer questions. "
                    "You may also use memory_write for long-term facts."
                )
                .plugin(knowledge_plugin)
                .plugin(memory_plugin)
                .plugin(recall_plugin)
            )
        )
        print(f"  Knowledge source: {doc_dir} (deploy_guide.md, rust_tips.md)")
        print("  Plugins installed: knowledge, memory, session-recall\n")

        prompt = "Search the knowledge source for the production deployment command. What is it?"
        print(f'Prompt: "{prompt}"\n')
        events = run_prompt(harness, prompt, timeout_ms=60_000)
        text = text_of(events).strip()
        print(f"Answer: {text}")

        tools_called = sorted(
            {
                e.get("tool_name")
                for e in events
                if e.get("type") in ("tool_call_start", "tool_execution_start")
            }
        )
        print(f"\nTools called: {tools_called}")

        searched = "knowledge_search" in tools_called
        reflects_source = "senza deploy --env prod" in text or "deploy --env prod" in text
        print("\nObservation:")
        print(f"  knowledge_search called: {searched}")
        print(f"  answer reflects injected source: {reflects_source}")


if __name__ == "__main__":
    main()
