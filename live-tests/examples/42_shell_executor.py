"""42 — Shell Executor: run external commands as workflow steps.

Mirrors 原仓库根 examples/runtime/07_shell_executor.py. Demonstrates:
  - Using the built-in ShellExecutor (create_shell_executor)
  - Command allowlist pattern for security
  - Injecting an OS-backed ExecutionEnv so ShellExecutor can run real commands
  - Mixing executor steps with LLM steps

Run:
  source ~/.omp_llm_env && python live-tests/examples/42_shell_executor.py
"""

import senza
from _common import live_model, require_provider

# Command allowlist — only these commands can be executed by ShellExecutor.
ALLOWED_COMMANDS = ["echo", "python3", "date", "whoami"]


def main() -> None:
    print("=== 42: Shell Executor ===\n")
    provider = require_provider()

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

    engine = senza.WorkflowEngine(workflow, provider, live_model(), judge, env=env).with_executor(
        "shell", senza.create_shell_executor(ALLOWED_COMMANDS)
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
