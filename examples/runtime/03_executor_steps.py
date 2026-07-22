"""03 — Executor Steps: run Python code as workflow steps.

Demonstrates:
  - create_executor() with a Python callback
  - Mixing LLM steps and executor steps
  - Shared context variables between steps

Run:
  OPENAI_API_KEY=sk-... python 03_executor_steps.py
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

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
        "edges": [
            {"from": "generate", "to": "process"},
        ],
    }

    def double_executor(ctx):
        # Executor callbacks receive the previous step's output under
        # the "prev_output" key (see PyExecutor::execute in pyworkflow.rs),
        # NOT "output".
        output = ctx.get("prev_output") or "0"
        try:
            num = int(output.strip())
        except (ValueError, AttributeError):
            num = 0
        result = num * 2
        return {"output": str(result), "structured": {"original": num, "doubled": result}}

    def judge(ctx):
        # Route generate -> process, then finish after process runs.
        if ctx["step_id"] == "generate":
            return "to:process"
        return "abort:done"

    engine = senza.WorkflowEngine(
        workflow, provider, os.environ.get("SENZA_MODEL", "gpt-4o"), senza.create_judge(judge)
    ).with_executor("double_it", senza.create_executor(double_executor))

    print("Running mixed LLM + executor workflow...")
    engine.run()

    history = engine.step_history()
    for record in history:
        result = record.get("result")
        if result:
            print(f"  {record['step_id']}: output={result['output'][:80]}")
            if result.get("structured"):
                print(f"    structured={result['structured']}")


if __name__ == "__main__":
    main()
