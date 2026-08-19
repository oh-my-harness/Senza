"""09 — Workflow Persistence: TaskStore save and completed-task reload.

Mirrors runtime `09_workflow_recovery.rs`. Demonstrates:
  - WorkflowEngine.with_task_store: persist task state to a disk directory
  - Running a 2-step linear workflow to Succeeded
  - Reloading the completed task from the TaskStore via WorkflowEngine.restore
  - Inspecting state / step history after both run and restore

This successful-run reload verifies persistence. It is not a mid-run crash or
resume/recovery demonstration.

Run:
  source ~/.omp_llm_env && python live-tests/examples/09_workflow_recovery.py
"""

import tempfile

import senza
from _common import live_model, require_provider


def _flow():
    return {
        "entry_step": "writer",
        "steps": [
            {
                "id": "writer",
                "name": "writer",
                "prompt": "Write one short sentence about the ocean.",
                "allowed_tools": [],
            },
            {
                "id": "reviewer",
                "name": "reviewer",
                "prompt": "Repeat the first word of the previous output.",
                "allowed_tools": [],
            },
        ],
        "edges": [{"from": "writer", "to": "reviewer"}],
    }


def _judge():
    def judge(ctx):
        return "done" if ctx["step_id"] == "reviewer" else "to:reviewer"

    return senza.create_judge(judge)


def main() -> None:
    print("=== 09: Workflow Persistence & Reload ===\n")
    provider = require_provider()
    store = tempfile.mkdtemp(prefix="senza_recover_")

    engine = senza.WorkflowEngine(_flow(), provider, live_model(), _judge()).with_task_store(store)
    engine.set_context_variable("note", "persist me")
    engine.run()
    tid = engine.task_id()
    print(f"Task ID: {tid}")
    print(f"State after run: {engine.state()}")

    # Reload a successfully completed task from the persisted TaskStore. This
    # does not simulate a crash in the middle of a running workflow.
    restored = senza.WorkflowEngine.restore(store, tid, provider, live_model(), _judge())
    print(f"State after restore: {restored.state()}")
    history = restored.step_history()
    print(f"Step history after restore ({len(history)} steps):")
    for record in history:
        result = record.get("result") or {}
        print(f"  {record['step_id']}: {(result.get('output') or '')[:60]}")


if __name__ == "__main__":
    main()
