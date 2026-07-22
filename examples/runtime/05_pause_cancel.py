"""05 — Pause and Cancel: control a running workflow.

Demonstrates:
  - pause() to request a pause at the next step boundary
  - resume() to continue from a paused state
  - cancel() to abort execution
  - state() / current_step() for monitoring

Note: pause/resume works at step boundaries. When paused, run() raises
RuntimeError. Call resume() then run() again to continue.
cancel() sets the state to "cancelled" but may not interrupt an
in-progress LLM call — it takes effect at the next step boundary.

Run:
  python 05_pause_cancel.py
"""
import os
import sys
import threading
import time

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

    workflow = {
        "entry_step": "step1",
        "steps": [
            {"id": "step1", "name": "Step 1", "prompt": "Write a short paragraph about cats.", "allowed_tools": []},
            {"id": "step2", "name": "Step 2", "prompt": "Write a short paragraph about dogs.", "allowed_tools": []},
        ],
        "edges": [{"from": "step1", "to": "step2"}],
    }

    judge = senza.create_judge(lambda ctx: "to:step2" if ctx.get("step_id") == "step1" else "abort:done")
    engine = senza.WorkflowEngine(workflow, provider, os.environ.get("SENZA_MODEL", "gpt-4o"), judge)

    print(f"Task ID: {engine.task_id()}")
    print(f"Initial state: {engine.state()}")

    # Pause from a separate thread after a short delay
    def pause_after_delay():
        time.sleep(0.3)
        print("\n[Pausing workflow...]")
        engine.pause("demonstration")
        print(f"[State after pause: {engine.state()}]")

    pause_thread = threading.Thread(target=pause_after_delay)
    pause_thread.start()

    print("Running workflow (will pause)...")
    try:
        engine.run()
        print(f"Completed without pause. State: {engine.state()}")
    except RuntimeError as e:
        print(f"Workflow paused: {e}")
        print(f"  State: {engine.state()}")
        print(f"  Current step: {engine.current_step()}")

        # Resume and continue
        time.sleep(0.5)
        print("\n[Resuming workflow...]")
        engine.resume()
        print(f"  State after resume: {engine.state()}")
        engine.run()
        print(f"Completed after resume. State: {engine.state()}")

    pause_thread.join()

    history = engine.step_history()
    print(f"\nSteps recorded: {len(history)}")
    for r in history:
        result = r.get("result")
        status = "completed" if result else "skipped"
        print(f"  {r['step_id']}: {status}")


if __name__ == "__main__":
    main()
