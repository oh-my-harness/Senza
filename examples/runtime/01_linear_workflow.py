"""01 — Linear Workflow: step A → step B → done.

Demonstrates the minimal WorkflowEngine flow:
  - Define a workflow dict with steps and edges
  - Create a judge for step transitions
  - Build and run the engine
  - Subscribe to events

Run:
  python 01_linear_workflow.py
"""
import os
import sys

import senza as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    workflow = {
        "entry_step": "writer",
        "steps": [
            {"id": "writer", "name": "Writer", "prompt": "Write a one-sentence story about a cat.", "allowed_tools": []},
            {"id": "reviewer", "name": "Reviewer", "prompt": "Review this story and rate it 1-5: ", "allowed_tools": []},
        ],
        "edges": [
            {"from": "writer", "to": "reviewer"},
        ],
    }

    def judge(ctx):
        step = ctx.get("step_id", "")
        if step == "writer":
            return "to:reviewer"
        return "abort:done"

    judge_obj = lh.create_judge(judge)
    engine = lh.WorkflowEngine(workflow, provider, "gpt-4o", judge_obj)

    print(f"Task ID: {engine.task_id()}")
    print(f"Initial state: {engine.state()}")
    print(f"Current step: {engine.current_step()}")
    print("\nRunning workflow...")

    # Subscribe to events in a separate thread would be ideal for real-time
    # monitoring. Here we run synchronously and check history after.
    engine.run()

    print(f"\nFinal state: {engine.state()}")
    print(f"Final step: {engine.current_step()}")

    history = engine.step_history()
    print(f"\nStep history ({len(history)} steps):")
    for record in history:
        result = record.get("result")
        output = result["output"][:80] if result else "(no result)"
        print(f"  {record['step_id']}: {output}")

    cost = engine.total_cost()
    print(f"\nTotal tokens: {cost['total_input_tokens']} in / {cost['total_output_tokens']} out")


if __name__ == "__main__":
    main()
