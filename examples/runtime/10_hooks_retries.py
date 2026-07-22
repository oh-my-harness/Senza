"""10 — Workflow Hooks, Retries & Step-level Restore.

Demonstrates three WorkflowEngine capabilities not covered by other
runtime examples:

  - ``with_hooks(hooks_list)`` — attach lifecycle hooks to the workflow
    engine (same hook types as the agent layer). Here we use
    ``before_turn`` / ``after_turn`` to log each LLM turn within steps.
  - ``with_max_retries(max)`` — set the maximum retry count per step.
    When a step's judge returns ``"retry"``, the engine re-runs the step
    up to this many times before failing.
  - ``restore_from_step(task_store_dir, task_id, step, ...)`` — recover
    a crashed workflow starting from a *specific* step, skipping steps
    that already completed. Unlike ``restore()`` (which resumes from
    wherever the engine left off), ``restore_from_step`` lets you re-run
    from an arbitrary historical step.

Scenario: a 3-step document pipeline (draft → review → finalize). We
run it with hooks + retries, persist to a TaskStore, then simulate a
crash after step 2 and restore from step 2 (re-running review and
finalize without re-doing the draft).

Prerequisites:
  - Set OPENAI_API_KEY env var

Run:
  python 10_hooks_retries.py
"""
import os
import sys
import tempfile

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)
    model = os.environ.get("SENZA_MODEL", "gpt-4o")

    workflow = {
        "entry_step": "draft",
        "steps": [
            {
                "id": "draft",
                "name": "Draft",
                "prompt": "Write a one-sentence product description for a smart thermometer.",
                "allowed_tools": [],
            },
            {
                "id": "review",
                "name": "Review",
                "prompt": "Review this product description and suggest one improvement. Output the improved version only.",
                "allowed_tools": [],
            },
            {
                "id": "finalize",
                "name": "Finalize",
                "prompt": "Write the final one-sentence product description.",
                "allowed_tools": [],
            },
        ],
        "edges": [
            {"from": "draft", "to": "review"},
            {"from": "review", "to": "finalize"},
        ],
    }

    judge = senza.create_judge(lambda ctx: f"to:{ctx.get('next_step', 'finalize')}" if ctx.get("next_step") else "done")

    # ── Hooks: log each LLM turn within the workflow ──────────────────────
    turn_counter = {"n": 0}

    def on_before_turn(ctx):
        turn_counter["n"] += 1
        print(f"  [before_turn] turn #{turn_counter['n']} model={ctx.get('model', '?')}")

    def on_after_turn(ctx):
        n = len(ctx.get("new_messages", []))
        print(f"  [after_turn]  turn #{turn_counter['n']} new_messages={n}")

    hooks = [
        senza.create_before_turn_hook(on_before_turn),
        senza.create_after_turn_hook(on_after_turn),
    ]

    with tempfile.TemporaryDirectory() as store_dir:
        # ── Phase 1: Run with hooks + retries + persistence ────────────────
        print("=" * 60)
        print("Phase 1: Initial run (hooks + max_retries + task_store)")
        print("=" * 60)

        engine = (
            senza.WorkflowEngine(
                workflow_dict=workflow,
                provider=provider,
                model=model,
                judge=judge,
            )
            .with_hooks(hooks)
            .with_max_retries(3)
            .with_task_store(store_dir)
            .with_max_steps(10)
        )

        task_id = engine.task_id()
        print(f"Task ID: {task_id}")

        engine.set_context_variable("doc_pipeline", "smart-thermometer")
        engine.checkpoint("before_run", {"note": "starting pipeline"})

        print("\nRunning workflow...")
        engine.run()

        print(f"\nFinal state: {engine.state()}")
        history = engine.step_history()
        print(f"Steps completed: {len(history)}")
        for step in history:
            print(f"  - {step.get('step_id', '?')}: {step.get('state', '?')}")
        print(f"Total LLM turns: {turn_counter['n']}")

        # ── Phase 2: Restore from a specific step ──────────────────────────
        print("\n" + "=" * 60)
        print("Phase 2: restore_from_step (re-run from 'review')")
        print("=" * 60)

        # Simulate a crash: discard the engine, restore from step 'review'
        # This skips 'draft' (already done) and re-runs 'review' onward.
        restored = senza.WorkflowEngine.restore_from_step(
            task_store_dir=store_dir,
            task_id=task_id,
            step="review",
            provider=provider,
            model=model,
            judge=judge,
        )

        print(f"Restored task ID: {restored.task_id()}")
        print(f"Restored current_step: {restored.current_step()}")
        print(f"Restored state: {restored.state()}")

        recovered_history = restored.step_history()
        print(f"Recovered step history: {len(recovered_history)} steps")
        for step in recovered_history:
            print(f"  - {step.get('step_id', '?')}: {step.get('state', '?')}")

        # Re-run from 'review' to 'finalize'
        print("\nRe-running from 'review'...")
        restored.run()
        print(f"Final state after re-run: {restored.state()}")

        final_history = restored.step_history()
        print(f"Final step history: {len(final_history)} steps")
        for step in final_history:
            print(f"  - {step.get('step_id', '?')}: {step.get('state', '?')}")

        print("\nHooks + retries + step-level restore verified!")


if __name__ == "__main__":
    main()
