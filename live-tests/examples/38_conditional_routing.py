"""38 — Conditional Routing: route between steps based on LLM output.

Ported from 原仓库根 examples/runtime/02_conditional_routing.py. Demonstrates:
  - Custom judge for conditional routing
  - Judge reads step output and returns "to:<step_id>" to route
  - Multiple outgoing edges from a single step
  - A terminal "done" outcome ends the workflow

  For declarative edge conditions ({"op": "eq", "pointer": "/field", ...}),
  see the workflow JSON schema. Declarative conditions evaluate against
  StepResult.structured (JSON), not output (text).

Run:
  source ~/.omp_llm_env && python live-tests/examples/38_conditional_routing.py
"""

import senza
from _common import live_model, require_provider


def main() -> None:
    print("=== 38: Conditional Routing ===\n")
    provider = require_provider()

    workflow = {
        "entry_step": "classify",
        "steps": [
            {
                "id": "classify",
                "name": "Classify",
                "prompt": "Is this urgent? Reply only 'yes' or 'no': A customer is locked out.",
                "allowed_tools": [],
            },
            {
                "id": "urgent",
                "name": "Urgent Handler",
                "prompt": "Handle this urgent issue: customer locked out. Acknowledge in one sentence.",
                "allowed_tools": [],
            },
            {
                "id": "normal",
                "name": "Normal Handler",
                "prompt": "Queue this for later: customer locked out. Acknowledge in one sentence.",
                "allowed_tools": [],
            },
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
            return "to:urgent" if "yes" in output else "to:normal"
        # urgent / normal steps → done
        return "done"

    engine = senza.WorkflowEngine(workflow, provider, live_model(), senza.create_judge(judge))
    print(f"Task ID: {engine.task_id()}")
    print("Running conditional workflow...")
    engine.run()

    print(f"\nFinal state: {engine.state()}")
    history = engine.step_history()
    print(f"Steps executed: {[r['step_id'] for r in history]}")
    for record in history:
        result = record.get("result") or {}
        output = (result.get("output") or "").strip()[:80]
        print(f"  {record['step_id']}: {output}")


if __name__ == "__main__":
    main()
