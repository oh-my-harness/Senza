"""39 — Executor Steps: run Python code as workflow steps.

Mirrors runtime `03_executor_steps.rs` (原仓库根 examples/runtime/03_executor_steps.py).
Demonstrates:
  - senza.create_executor() with a Python callback
  - Mixing LLM steps and executor steps
  - Shared context variables between steps (prev_output)

Run:
  source ~/.omp_llm_env && python live-tests/examples/39_executor_steps.py
"""

import senza
from _common import live_model, require_provider


def main() -> None:
    print("=== 39: Executor Steps ===\n")
    provider = require_provider()

    # The LLM "generate" step produces a number; the "process" step is not an
    # LLM step but a Python executor that doubles it.
    workflow = {
        "entry_step": "generate",
        "steps": [
            {
                "id": "generate",
                "name": "Generate",
                "prompt": "Generate a random number between 1 and 100. Reply with just the number.",
                "allowed_tools": [],
            },
            {"id": "process", "name": "Process", "executor": "double_it"},
        ],
        "edges": [{"from": "generate", "to": "process"}],
    }

    def double_executor(ctx):
        # Executor callbacks receive the previous step's output under the
        # "prev_output" key (see PyExecutor::execute in pyworkflow.rs), not "output".
        output = ctx.get("prev_output") or "0"
        try:
            num = int(str(output).strip())
        except (ValueError, AttributeError):
            num = 0
        result = num * 2
        return {"output": str(result), "structured": {"original": num, "doubled": result}}

    def judge(ctx):
        # Route generate -> process, then finish after process runs.
        if ctx.get("step_id") == "generate":
            return "to:process"
        return "abort:done"

    engine = senza.WorkflowEngine(
        workflow, provider, live_model(), senza.create_judge(judge)
    ).with_executor("double_it", senza.create_executor(double_executor))

    print("Running mixed LLM + executor workflow...")
    engine.run()
    print(f"Final state: {engine.state()}")

    history = engine.step_history()
    print(f"\nStep history ({len(history)} steps):")
    for record in history:
        result = record.get("result")
        if result:
            print(f"  {record['step_id']}: output={result['output'][:80]}")
            if result.get("structured"):
                print(f"    structured={result['structured']}")


if __name__ == "__main__":
    main()
