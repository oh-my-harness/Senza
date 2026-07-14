"""03 — Executor Steps: run Python code as workflow steps.

Demonstrates:
  - create_executor() with a Python callback
  - Mixing LLM steps and executor steps
  - Shared context variables between steps

Run:
  python 03_executor_steps.py
"""
import json
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
        "entry_step": "generate",
        "steps": [
            {"id": "generate", "name": "Generate", "prompt": "Generate a random number between 1 and 100. Reply with just the number.", "allowed_tools": []},
            {"id": "process", "name": "Process", "executor": "double_it"},
        ],
        "edges": [
            {"from": "generate", "to": "process"},
        ],
    }

    def double_executor(ctx):
        output = ctx.get("output", "0")
        try:
            num = int(output.strip())
        except ValueError:
            num = 0
        result = num * 2
        return {"output": str(result), "structured": {"original": num, "doubled": result}}

    judge = lh.create_judge(lambda ctx: "abort:done")
    engine = (
        lh.WorkflowEngine(workflow, provider, "gpt-4o", judge)
        .with_executor("double_it", lh.create_executor(double_executor))
    )

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
