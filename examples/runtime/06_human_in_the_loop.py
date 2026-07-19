"""06 — Human-in-the-Loop: pause for external events.

Demonstrates:
  - create_event_channel() for external event injection
  - The LLM calls wait_for_external_event to pause for human input
  - Submit events from another thread

Run:
  python 06_human_in_the_loop.py
"""
import json
import os
import sys
import threading
import time

import senza as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    # Create an event channel — the wait_for_external_event tool will be
    # available to the LLM. When it calls this tool, execution pauses until
    # handle.submit() is called from another thread.
    handle, wait_tool = lh.create_event_channel("review-task")

    workflow = {
        "entry_step": "draft",
        "steps": [
            {"id": "draft", "name": "Draft", "prompt": "Draft a short email to a client about a project delay. Then call wait_for_external_event to get approval.", "allowed_tools": ["wait_for_external_event"]},
        ],
        "edges": [],
    }

    judge = lh.create_judge(lambda ctx: "abort:done")
    engine = (
        lh.WorkflowEngine(workflow, provider, os.environ.get("SENZA_MODEL", "gpt-4o"), judge)
        .with_external_tool(wait_tool)
    )

    # Simulate a human reviewer responding after 3 seconds
    def human_review():
        time.sleep(3)
        print("\n[Human reviewer: approving...]")
        handle.submit("approved", {"feedback": "Looks good, send it!"})

    review_thread = threading.Thread(target=human_review)
    review_thread.start()

    print("Running workflow with human-in-the-loop...")
    engine.run()
    review_thread.join()

    print(f"\nFinal state: {engine.state()}")
    history = engine.step_history()
    for r in history:
        result = r.get("result")
        if result:
            print(f"  {r['step_id']}: {result['output'][:120]}")


if __name__ == "__main__":
    main()
