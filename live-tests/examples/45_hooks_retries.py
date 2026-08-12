"""45 — Workflow Hooks, Retries & Step-level Restore.

Mirrors runtime `10_hooks_retries.py`. Demonstrates three WorkflowEngine
capabilities:

  - ``with_hooks(...)`` — attach lifecycle hooks to the workflow engine
    (same hook types as the agent layer). Here ``before_turn`` / ``after_turn``
    log each LLM turn across all steps.
  - ``with_max_retries(max)`` — cap retries per step. When a step's judge
    returns ``"retry"`` the engine re-runs the step up to this many times;
    we force one retry on the review step to make it observable.
    (For provider-error retries at the agent/harness level, the builder also
    exposes ``.retry(max_retries, base_delay_ms)``.)
  - ``restore_from_step(store_dir, task_id, step, ...)`` — recover a workflow
    from a *specific* step, skipping ones already completed (unlike
    ``restore()`` which resumes wherever the engine left off).

Scenario: a 3-step document pipeline (draft → review → finalize) run with
hooks + retries, persisted to a TaskStore, then restored from 'review' to
re-run review and finalize without re-doing the draft.

Run:
  source ~/.omp_llm_env && python live-tests/examples/45_hooks_retries.py
"""

import tempfile

import senza
from _common import live_model, require_provider


def _workflow():
    return {
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


def _judge():
    # Force one retry on 'review' so with_max_retries is observably exercised.
    calls = {"review": 0}

    def judge(ctx):
        step_id = ctx.get("step_id", "")
        if step_id == "draft":
            return "to:review"
        if step_id == "review":
            calls["review"] += 1
            return "to:finalize" if calls["review"] > 1 else "retry"
        return "done"

    return senza.create_judge(judge)


def main() -> None:
    print("=== 45: Workflow Hooks, Retries & Step-level Restore ===\n")
    provider = require_provider()
    model = live_model()
    judge = _judge()

    # ── Hooks: log each LLM turn within the workflow ──────────────────────
    turn_counter = {"n": 0}

    def on_before_turn(ctx):
        turn_counter["n"] += 1
        print(f"  [before_turn] turn #{turn_counter['n']} model={ctx.get('model', '?')}")

    def on_after_turn(ctx):
        n = len(ctx.get("new_messages", []))
        print(f"  [after_turn]  turn #{turn_counter['n']} new_messages={n}")

    hooks = [
        senza.hooks.before_turn(on_before_turn),
        senza.hooks.after_turn(on_after_turn),
    ]

    with tempfile.TemporaryDirectory() as store_dir:
        # ── Phase 1: Run with hooks + retries + persistence ────────────────
        print("=" * 60)
        print("Phase 1: Initial run (hooks + max_retries + task_store)")
        print("=" * 60)

        engine = (
            senza.WorkflowEngine(_workflow(), provider, model, judge)
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

        # Simulate a crash: discard the engine, restore from step 'review'.
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
