"""09 — CompositeJudge: per-step routing without one big decide function.

Demonstrates:
  - create_composite_judge() with .on() per-step handlers
  - Mixing custom routing with declarative Expr edge fallback
  - Steps without .on() handler automatically use Expr edges

This is cleaner than writing a single judge function with a giant
match/match block for every step.

Run:
  python 09_composite_judge.py
"""
import os
import sys

import senza as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    workflow = {
        "entry_step": "writer",
        "steps": [
            {"id": "writer", "name": "写作", "prompt": "写一句关于猫的故事。", "allowed_tools": []},
            {"id": "reviewer", "name": "审阅", "prompt": "给这个故事打分 1-5，输出 JSON {score: N}。", "allowed_tools": []},
            {"id": "finalizer", "name": "定稿", "prompt": "输出最终故事。", "allowed_tools": []},
        ],
        "edges": [
            {"from": "writer", "to": "reviewer"},
            # Declarative edges for reviewer (no .on() handler needed)
            {"from": "reviewer", "to": "finalizer", "condition": {"op": "gte", "pointer": "/score", "value": 3}},
            {"from": "reviewer", "to": "writer", "condition": {"op": "lt", "pointer": "/score", "value": 3}},
        ],
    }

    judge = lh.create_composite_judge()
    # Custom routing for writer only
    judge.on("writer", lambda ctx: "to:reviewer")
    # reviewer and finalizer: no .on() handler → falls back to Expr edges / Abort
    # (engine auto-injects EdgeConditionJudge as fallback)

    engine = (
        lh.WorkflowEngine(workflow, provider, "gpt-4o", judge)
        .with_max_tokens(256)
    )

    print(f"Engine: {engine!r}")
    print(f"Judge:  {judge!r}")
    print()

    engine.run()

    for record in engine.step_history():
        r = record.get("result")
        output = r["output"][:80] if r and r.get("output") else "(无结果)"
        print(f"  {record['step_id']}: {output}")


if __name__ == "__main__":
    main()
