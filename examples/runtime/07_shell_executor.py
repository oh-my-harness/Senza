"""07 — Shell Executor: run external commands as workflow steps.

Demonstrates:
  - Using a Python callback executor to run shell commands
  - Command allowlist pattern for security
  - Mixing executor steps with LLM steps

Note: The built-in ShellExecutor (create_shell_executor) requires a
sandbox ExecutionEnv, which is not configured by default in the PyO3 SDK.
This example shows the equivalent pattern using a Python callback executor
with subprocess, which works without sandbox configuration.

Run:
  python 07_shell_executor.py
"""
import json
import os
import subprocess
import sys

import senza as lh


# Command allowlist — only these commands can be executed.
ALLOWED_COMMANDS = {"echo", "python3", "date", "whoami"}


def shell_executor(ctx):
    """Execute a shell command from executor_config, with an allowlist."""
    config = ctx.get("config", {})
    command = config.get("command", "")
    args = config.get("args", [])

    if command not in ALLOWED_COMMANDS:
        return {
            "output": f"Error: command '{command}' not in allowlist",
            "structured": {"status": "error", "allowed": sorted(ALLOWED_COMMANDS)},
        }

    try:
        result = subprocess.run(
            [command] + args,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {
            "output": result.stdout.strip() or result.stderr.strip(),
            "structured": {
                "status": "ok" if result.returncode == 0 else "error",
                "returncode": result.returncode,
            },
        }
    except subprocess.TimeoutExpired:
        return {"output": "Error: command timed out", "structured": {"status": "timeout"}}


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

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
        .with_executor("shell", lh.create_executor(shell_executor))
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
