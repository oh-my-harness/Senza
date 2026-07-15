"""08 — HTTP Executor: make HTTP calls as workflow steps.

Demonstrates:
  - create_http_executor() with a host allowlist
  - HTTP step config: method, url, headers, body
  - Security: only allowlisted hosts can be called

Note: The HTTP executor uses the built-in HttpCallExecutor which makes
real HTTP requests. If the target host is unreachable or returns an error
status, the step will fail. This example uses httpbin.org for testing.

Run:
  python 08_http_executor.py
"""
import os
import sys

try:
    import senza as lh
except ImportError:
    import llm_harness_py as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    http_exec = lh.create_http_executor(
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

    judge = lh.create_judge(lambda ctx: "abort:done")
    engine = (
        lh.WorkflowEngine(workflow, provider, "gpt-4o", judge)
        .with_executor("http", http_exec)
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
