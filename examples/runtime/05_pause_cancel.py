"""05 — Pause and Cancel: control a running workflow.

Demonstrates:
  - pause() to request a pause at the next step boundary
  - cancel() to abort execution
  - state() / current_step() for monitoring

Note: pause/cancel are designed to be called from a different thread
while run() is blocking. This example uses threading.

Run:
  python 05_pause_cancel.py
"""
import os
import sys
import threading
import time

try:
    import senza as lh
except ImportError:
    import llm_harness_py as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    workflow = {
        "entry_step": "step1",
        "steps": [
            {"id": "step1", "name": "Step 1", "prompt": "Write a long essay about AI.", "allowed_tools": []},
            {"id": "step2", "name": "Step 2", "prompt": "Summarize the previous essay.", "allowed_tools": []},
        ],
        "edges": [{"from": "step1", "to": "step2"}],
    }

    judge = lh.create_judge(lambda ctx: "abort:done")
    engine = lh.WorkflowEngine(workflow, provider, "gpt-4o", judge)

    print(f"Task ID: {engine.task_id()}")
    print(f"Initial state: {engine.state()}")

    # Cancel from a separate thread after 2 seconds
    def cancel_after_delay():
        time.sleep(2)
        print("\n[Cancelling workflow...]")
        engine.cancel("user requested cancel")
        print(f"[State after cancel: {engine.state()}]")

    cancel_thread = threading.Thread(target=cancel_after_delay)
    cancel_thread.start()

    print("Running workflow (will be cancelled)...")
    try:
        engine.run()
    except RuntimeError as e:
        print(f"Run ended: {e}")

    cancel_thread.join()

    print(f"\nFinal state: {engine.state()}")

    history = engine.step_history()
    print(f"Steps recorded: {len(history)}")
    for r in history:
        result = r.get("result")
        status = "completed" if result else "cancelled"
        print(f"  {r['step_id']}: {status}")


if __name__ == "__main__":
    main()
