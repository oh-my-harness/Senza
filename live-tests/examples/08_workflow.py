"""08 — Workflow Engine: multi-step LLM workflow with transitions and tools.

Mirrors runtime `08_workflow.rs`. Demonstrates a linear 2-step workflow
(capital query -> summary) with a judge driving transitions, then inspects
state, step history, and token cost via the WorkflowEngine.

Run:
  source ~/.omp_llm_env && python live-tests/examples/08_workflow.py
"""

import senza
from _common import live_model, require_provider


def main() -> None:
    print("=== 08: Workflow Engine ===\n")
    provider = require_provider()

    workflow = {
        "entry_step": "writer",
        "steps": [
            {
                "id": "writer",
                "name": "Writer",
                "prompt": "What is the capital of France? Answer in one sentence.",
                "allowed_tools": [],
            },
            {
                "id": "reviewer",
                "name": "Reviewer",
                "prompt": "Summarize the previous answer in under 10 words.",
                "allowed_tools": [],
            },
        ],
        "edges": [{"from": "writer", "to": "reviewer"}],
    }

    def judge(ctx):
        step = ctx.get("step_id", "")
        return "to:reviewer" if step == "writer" else "done"

    engine = senza.WorkflowEngine(workflow, provider, live_model(), senza.create_judge(judge))
    print(f"Task ID: {engine.task_id()}")
    print(f"Initial state: {engine.state()}")

    engine.run()
    print(f"Final state: {engine.state()}")

    history = engine.step_history()
    print(f"\nStep history ({len(history)} steps):")
    for record in history:
        result = record.get("result") or {}
        output = (result.get("output") or "")[:100]
        print(f"  {record['step_id']}: {output}")

    cost = engine.total_cost()
    print(f"\nTotal tokens: {cost['total_input_tokens']} in / {cost['total_output_tokens']} out")


if __name__ == "__main__":
    main()
