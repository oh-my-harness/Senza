"""43 — HTTP Executor: make HTTP calls as workflow steps.

Mirrors runtime `43_http_executor.rs` (原仓库根 examples/runtime/08_http_executor.py).
Demonstrates:
  - create_http_executor() with a host allowlist
  - HTTP step config: method, url, headers, body
  - Security: only allowlisted hosts can be called

Note: The HTTP executor uses the built-in HttpCallExecutor which makes
real HTTP requests. If the target host is unreachable or returns an error
status, the step will fail. This example uses httpbin.org for testing.

Run:
  source ~/.omp_llm_env && python live-tests/examples/43_http_executor.py
"""

import senza
from _common import live_model, require_provider


def main() -> None:
    print("=== 43: HTTP Executor ===\n")
    provider = require_provider()

    http_exec = senza.create_http_executor(
        allowed_hosts=["httpbin.org"],
        allowed_schemes=["https"],
    )

    workflow = {
        "entry_step": "fetch",
        "steps": [
            {
                "id": "fetch",
                "name": "Fetch Data",
                "executor": "http",
                "executor_config": {
                    "method": "GET",
                    "url": "https://httpbin.org/get",
                    "headers": {"Accept": "application/json"},
                },
            },
        ],
        "edges": [],
    }

    judge = senza.create_judge(lambda ctx: "abort:done")
    engine = senza.WorkflowEngine(workflow, provider, live_model(), judge).with_executor(
        "http", http_exec
    )

    print("Running HTTP executor workflow...")
    try:
        engine.run()
    except RuntimeError as e:
        print(f"  Step failed (expected if network is restricted): {e}")
        print("  This is normal — the HTTP executor requires network access.")
        return

    history = engine.step_history()
    for record in history:
        result = record.get("result")
        if result:
            output = result["output"][:200]
            print(f"  {record['step_id']}: {output}")


if __name__ == "__main__":
    main()
