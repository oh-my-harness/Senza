"""07 — Shell Executor: run external commands as workflow steps.

Demonstrates:
  - Using the built-in ShellExecutor (create_shell_executor)
  - Command allowlist pattern for security
  - Injecting an OS-backed ExecutionEnv so ShellExecutor can run real commands
  - Mixing executor steps with LLM steps

Run:
  python 07_shell_executor.py
"""
import os
import sys

import senza


# Command allowlist — only these commands can be executed by ShellExecutor.
ALLOWED_COMMANDS = ["echo", "python3", "date", "whoami"]


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

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

    judge = senza.create_judge(lambda ctx: "abort:done")

    # Create an OS-backed ExecutionEnv so ShellExecutor can run real commands.
    # Without `env=...`, the engine uses UnsupportedEnv, whose execute_shell
    # always returns an error.
    env = senza.create_os_env(working_dir=".")

    engine = (
        senza.WorkflowEngine(workflow, provider, os.environ.get("SENZA_MODEL", "gpt-4o"), judge, env=env)
        .with_executor("shell", senza.create_shell_executor(ALLOWED_COMMANDS))
    )

    print("Running shell executor workflow...")
    engine.run()

    history = engine.step_history()
    for record in history:
        result = record.get("result")
        if result:
            print(f"  {record['step_id']}: {result['output']}")


if __name__ == "__main__":
    main()
