"""04 — Crash Recovery: persist and restore a workflow.

Demonstrates:
  - with_task_store(dir) for persistence
  - WorkflowEngine.restore() classmethod for recovery
  - State survives across engine instances

Run:
  python 04_crash_recovery.py
"""

import os
import tempfile

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

    workflow = {
        "entry_step": "step1",
        "steps": [
            {"id": "step1", "name": "Step 1", "prompt": "Say 'hello'", "allowed_tools": []},
            {"id": "step2", "name": "Step 2", "prompt": "Say 'world'", "allowed_tools": []},
        ],
        "edges": [{"from": "step1", "to": "step2"}],
    }

    judge = senza.create_judge(lambda ctx: "abort:done")

    with tempfile.TemporaryDirectory() as store_dir:
        # Phase 1: Create and run the workflow with persistence
        print("=== Phase 1: Initial run ===")
        engine = senza.WorkflowEngine(
            workflow, provider, os.environ.get("SENZA_MODEL", "gpt-4o"), judge
        ).with_task_store(store_dir)
        task_id = engine.task_id()
        print(f"Task ID: {task_id}")

        # Set a context variable that should survive restore
        engine.set_context_variable("session_name", "crash-recovery-demo")
        engine.checkpoint("before_run", {"note": "about to start"})

        print("Running workflow...")
        engine.run()
        print(f"Final state: {engine.state()}")

        # Phase 2: Simulate a crash — create a NEW engine from the store
        print("\n=== Phase 2: Restore from TaskStore ===")
        restored = senza.WorkflowEngine.restore(
            store_dir, task_id, provider, os.environ.get("SENZA_MODEL", "gpt-4o"), judge
        )
        print(f"Restored task ID: {restored.task_id()}")
        assert restored.task_id() == task_id, "task_id should match"
        print(f"Restored state: {restored.state()}")
        print(f"Restored current_step: {restored.current_step()}")

        history = restored.step_history()
        print(f"Step history recovered: {len(history)} steps")
        for r in history:
            print(f"  {r['step_id']}")

        print("\nCrash recovery verified! ✓")


if __name__ == "__main__":
    main()
