"""44 — CompositeJudge: per-step routing without one big decide function.

Mirrors runtime `09_composite_judge.rs` (原仓库根 examples/runtime/09_composite_judge.py).
Demonstrates:
  - senza.create_composite_judge() with .on() per-step handlers
  - Mixing custom routing with declarative Expr edge fallback
  - Steps without an .on() handler automatically use Expr edges

Declarative edge conditions (the "condition" key) evaluate against
StepResult.structured (NOT output). LLM steps produce text output only,
so to use a condition like {"op": "gte", "pointer": "/score", ...} we
parse the LLM's JSON output in an executor step that returns a
"structured" dict. This keeps the composite-judge + declarative-edge
pattern demonstrable end-to-end.

Run:
  source ~/.omp_llm_env && python live-tests/examples/44_composite_judge.py
"""

import re

import senza
from _common import live_model, require_provider


def main() -> None:
    print("=== 44: CompositeJudge ===\n")
    provider = require_provider()

    workflow = {
        "entry_step": "writer",
        "steps": [
            {
                "id": "writer",
                "name": "Writer",
                "prompt": "Write a one-sentence story about a cat.",
                "allowed_tools": [],
            },
            {
                "id": "reviewer",
                "name": "Reviewer",
                "prompt": 'Rate this story 1-5, output JSON {"score": N}.',
                "allowed_tools": [],
            },
            # parse_score is an executor step: it takes the reviewer's
            # text output and returns a structured {"score": N} dict so
            # the declarative condition edges below can match on /score.
            {"id": "parse_score", "name": "ParseScore", "executor": "parse_score"},
            {
                "id": "finalizer",
                "name": "Finalizer",
                "prompt": "Output the final story.",
                "allowed_tools": [],
            },
        ],
        "edges": [
            {"from": "writer", "to": "reviewer"},
            {"from": "reviewer", "to": "parse_score"},
            # Declarative edges for parse_score (no .on() handler needed):
            # conditions read parse_score's structured {"score": N}.
            {
                "from": "parse_score",
                "to": "finalizer",
                "condition": {"op": "gte", "pointer": "/score", "value": 3},
            },
            {
                "from": "parse_score",
                "to": "writer",
                "condition": {"op": "lt", "pointer": "/score", "value": 3},
            },
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

    judge = senza.create_composite_judge()
    # Custom routing for writer and reviewer.
    # parse_score: no .on() handler -> falls back to Expr edges
    # (engine auto-injects EdgeConditionJudge as fallback).
    judge.on("writer", lambda ctx: "to:reviewer")
    judge.on("reviewer", lambda ctx: "to:parse_score")

    engine = (
        senza.WorkflowEngine(workflow, provider, live_model(), judge)
        .with_executor("parse_score", senza.create_executor(parse_score_executor))
        .with_max_tokens(256)
    )

    print(f"Engine: {engine!r}")
    print(f"Judge:  {judge!r}")
    print()

    engine.run()

    for record in engine.step_history():
        r = record.get("result")
        output = r["output"][:80] if r and r.get("output") else "(no result)"
        print(f"  {record['step_id']}: {output}")


if __name__ == "__main__":
    main()
