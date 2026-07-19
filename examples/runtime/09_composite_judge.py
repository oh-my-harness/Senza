"""09 — CompositeJudge: per-step routing without one big decide function.

Demonstrates:
  - create_composite_judge() with .on() per-step handlers
  - Mixing custom routing with declarative Expr edge fallback
  - Steps without .on() handler automatically use Expr edges

Declarative edge conditions (the "condition" key) evaluate against
StepResult.structured (NOT output). LLM steps produce text output only,
so to use a condition like {"op": "gte", "pointer": "/score", ...} we
parse the LLM's JSON output in an executor step that returns a
"structured" dict. This keeps the composite-judge + declarative-edge
pattern demonstrable end-to-end.

Run:
  OPENAI_API_KEY=sk-... python 09_composite_judge.py
"""
import json
import os
import re

import senza as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    workflow = {
        "entry_step": "writer",
        "steps": [
            {"id": "writer", "name": "写作", "prompt": "写一句关于猫的故事。", "allowed_tools": []},
            {"id": "reviewer", "name": "审阅", "prompt": "给这个故事打分 1-5，输出 JSON {\"score\": N}。", "allowed_tools": []},
            # parse_score is an executor step: it takes the reviewer's
            # text output and returns a structured {"score": N} dict so
            # the declarative condition edges below can match on /score.
            {"id": "parse_score", "name": "解析分数", "executor": "parse_score"},
            {"id": "finalizer", "name": "定稿", "prompt": "输出最终故事。", "allowed_tools": []},
        ],
        "edges": [
            {"from": "writer", "to": "reviewer"},
            {"from": "reviewer", "to": "parse_score"},
            # Declarative edges for parse_score (no .on() handler needed):
            # conditions read parse_score's structured {"score": N}.
            {"from": "parse_score", "to": "finalizer", "condition": {"op": "gte", "pointer": "/score", "value": 3}},
            {"from": "parse_score", "to": "writer", "condition": {"op": "lt", "pointer": "/score", "value": 3}},
        ],
    }

    def parse_score_executor(ctx):
        # Executor callbacks receive the previous step's output under
        # "prev_output" (the reviewer's text, e.g. '{"score": 4}').
        raw = ctx.get("prev_output") or ""
        match = re.search(r"\{[^}]*\"?score\"?\s*:\s*(\d+)[^}]*\}", raw)
        score = int(match.group(1)) if match else 0
        return {
            "output": f"score={score}",
            "structured": {"score": score},
        }

    judge = lh.create_composite_judge()
    # Custom routing for writer only.
    # reviewer -> parse_score via a simple .on() handler.
    # parse_score: no .on() handler -> falls back to Expr edges
    # (engine auto-injects EdgeConditionJudge as fallback).
    judge.on("writer", lambda ctx: "to:reviewer")
    judge.on("reviewer", lambda ctx: "to:parse_score")

    engine = (
        lh.WorkflowEngine(workflow, provider, os.environ.get("SENZA_MODEL", "gpt-4o"), judge)
        .with_executor("parse_score", lh.create_executor(parse_score_executor))
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
