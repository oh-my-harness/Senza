"""07 — Shell Executor: run shell commands as workflow steps.

Demonstrates:
  - create_shell_executor() with a command allowlist
  - Shell step config: command, args, env, cwd, timeout_ms
  - Security: only allowlisted commands can run

Run:
  python 07_shell_executor.py
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

    # Create a ShellExecutor with a strict command allowlist
    shell_exec = lh.create_shell_executor(
        commands=["echo", "python3"],
        default_timeout_ms=10000,
    )

    workflow = {
        "entry_step": "greet",
        "steps": [
            {
                "id": "greet",
                "name": "Greet",
                "executor": "shell",
                "executor_config": {
                    "command": "echo",
                    "args": ["Hello from shell executor!"],
                },
            },
            {
                "id": "compute",
                "name": "Compute",
                "executor": "shell",
                "executor_config": {
                    "command": "python3",
                    "args": ["-c", "print(2 ** 10)"],
                },
            },
        ],
        "edges": [{"from": "greet", "to": "compute"}],
    }

    judge = lh.create_judge(lambda ctx: "abort:done")
    engine = (
        lh.WorkflowEngine(workflow, provider, "gpt-4o", judge)
        .with_executor("shell", shell_exec)
    )

    print("Running shell executor workflow...")
    engine.run()

    history = engine.step_history()
    for record in history:
        result = record.get("result")
        if result:
            print(f"  {record['step_id']}: {result['output'].strip()}")


if __name__ == "__main__":
    main()
