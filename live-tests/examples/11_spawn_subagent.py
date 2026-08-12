"""11 — Spawn Sub-Agent / task dispatch.

Mirrors runtime `11_spawn_subagent.rs`. Runtime spawns child sub-agents via
`llm_harness_runtime::spawn`. **Senza's Python surface exposes no sub-agent /
spawn API** (feature gap). The closest available mechanism is WorkflowEngine
step dispatch, which routes a single task through multiple LLM steps (see
08/09). This example shows that dispatch path as the analog and notes the gap.

Run:
  source ~/.omp_llm_env && python live-tests/examples/11_spawn_subagent.py
"""

import senza
from _common import live_model, require_provider


def main() -> None:
    print("=== 11: Spawn Sub-Agent (feature gap note) ===\n")
    print(
        "[gap] Senza Python exposes no sub-agent/spawn API; the runtime's "
        "`spawn` module has no Python binding."
    )
    print(
        "Closest analog: WorkflowEngine step dispatch (single task, "
        "multiple LLM steps). Demonstrating:\n"
    )

    provider = require_provider()
    workflow = {
        "entry_step": "a",
        "steps": [
            {
                "id": "a",
                "name": "a",
                "prompt": "Say the word 'research' then ask for confirmation.",
                "allowed_tools": [],
            },
            {"id": "b", "name": "b", "prompt": "Say the word 'proceed'.", "allowed_tools": []},
        ],
        "edges": [{"from": "a", "to": "b"}],
    }

    def judge(ctx):
        return "done" if ctx["step_id"] == "b" else "to:b"

    engine = senza.WorkflowEngine(workflow, provider, live_model(), senza.create_judge(judge))
    engine.run()
    print(f"State: {engine.state()}")
    for record in engine.step_history():
        result = record.get("result") or {}
        print(f"  {record['step_id']}: {(result.get('output') or '')[:60]}")


if __name__ == "__main__":
    main()
