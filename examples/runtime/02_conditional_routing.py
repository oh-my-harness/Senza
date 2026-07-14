"""02 — Conditional Routing: declarative edge conditions.

Demonstrates:
  - Using declarative edge conditions ({"op": "eq", ...})
  - A NoopJudge workflow where routing is fully declarative

Run:
  python 02_conditional_routing.py
"""
import os
import sys

try:
    import senza as lh
except ImportError:
    import llm_harness_py as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    workflow = {
        "entry_step": "classify",
        "steps": [
            {"id": "classify", "name": "Classify", "prompt": "Is this urgent? Reply only 'yes' or 'no': A customer is locked out.", "allowed_tools": []},
            {"id": "urgent", "name": "Urgent Handler", "prompt": "Handle this urgent issue: customer locked out.", "allowed_tools": []},
            {"id": "normal", "name": "Normal Handler", "prompt": "Queue this for later: customer locked out.", "allowed_tools": []},
        ],
        "edges": [
            {"from": "classify", "to": "urgent", "condition": {"op": "contains", "field": "output", "value": "yes"}},
            {"from": "classify", "to": "normal", "condition": {"op": "contains", "field": "output", "value": "no"}},
        ],
    }

    # NoopJudge: routing is handled by declarative edges
    judge = lh.create_judge(lambda ctx: "abort:done")
    engine = lh.WorkflowEngine(workflow, provider, "gpt-4o", judge)

    print(f"Task ID: {engine.task_id()}")
    print("Running conditional workflow...")
    engine.run()

    print(f"\nFinal state: {engine.state()}")
    history = engine.step_history()
    print(f"Steps executed: {[r['step_id'] for r in history]}")


if __name__ == "__main__":
    main()
