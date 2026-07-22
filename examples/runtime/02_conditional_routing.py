"""02 — Conditional Routing: route between steps based on LLM output.

Demonstrates:
  - Custom judge for conditional routing
  - Judge reads step output and returns "to:<step_id>" to route
  - Multiple outgoing edges from a single step

  For declarative edge conditions ({"op": "eq", "pointer": "/field", ...}),
  see the SENZA_DESIGN.md §5 Workflow JSON Schema. Declarative conditions
  evaluate against StepResult.structured (JSON), not output (text).

Run:
  python 02_conditional_routing.py
"""
import os
import sys

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

    workflow = {
        "entry_step": "classify",
        "steps": [
            {"id": "classify", "name": "Classify", "prompt": "Is this urgent? Reply only 'yes' or 'no': A customer is locked out.", "allowed_tools": []},
            {"id": "urgent", "name": "Urgent Handler", "prompt": "Handle this urgent issue: customer locked out. Acknowledge in one sentence.", "allowed_tools": []},
            {"id": "normal", "name": "Normal Handler", "prompt": "Queue this for later: customer locked out. Acknowledge in one sentence.", "allowed_tools": []},
        ],
        "edges": [
            {"from": "classify", "to": "urgent"},
            {"from": "classify", "to": "normal"},
        ],
    }

    def judge(ctx):
        step = ctx.get("step_id", "")
        if step == "classify":
            output = (ctx.get("output") or "").lower().strip()
            if "yes" in output:
                return "to:urgent"
            return "to:normal"
        # urgent / normal steps → done
        return "abort:done"

    judge_obj = senza.create_judge(judge)
    engine = senza.WorkflowEngine(workflow, provider, os.environ.get("SENZA_MODEL", "gpt-4o"), judge_obj)

    print(f"Task ID: {engine.task_id()}")
    print("Running conditional workflow...")
    engine.run()

    print(f"\nFinal state: {engine.state()}")
    history = engine.step_history()
    print(f"Steps executed: {[r['step_id'] for r in history]}")
    for record in history:
        result = record.get("result")
        if result:
            print(f"  {record['step_id']}: {result['output'].strip()[:80]}")


if __name__ == "__main__":
    main()
