"""08 — HTTP Executor: make HTTP calls as workflow steps.

Demonstrates:
  - create_http_executor() with a host allowlist
  - HTTP step config: method, url, headers, body
  - Security: only allowlisted hosts can be called

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

    # Create an HttpCallExecutor — only api.github.com is allowed
    http_exec = lh.create_http_executor(
        allowed_hosts=["api.github.com"],
        allowed_schemes=["https"],
        max_timeout_ms=15000,
    )

    workflow = {
        "entry_step": "fetch",
        "steps": [
            {
                "id": "fetch",
                "name": "Fetch API",
                "executor": "http",
                "executor_config": {
                    "method": "GET",
                    "url": "https://api.github.com/repos/octocat/Hello-World",
                    "headers": {"Accept": "application/vnd.github.v3+json"},
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
    engine.run()

    history = engine.step_history()
    for record in history:
        result = record.get("result")
        if result:
            output = result["output"][:200]
            print(f"  {record['step_id']}: {output}...")


if __name__ == "__main__":
    main()
