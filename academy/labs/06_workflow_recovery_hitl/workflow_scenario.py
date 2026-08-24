"""Provider-free checkpoint/recovery model for the Workflow lesson."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STEP_ORDER = ("draft", "check", "approve", "publish")


def _write(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_checkpoint(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def create_paused_checkpoint(path: Path) -> dict[str, Any]:
    """Run deterministic draft/check steps and pause at human approval."""

    state = {
        "task_id": "academy-release-001",
        "status": "paused",
        "current_step": "approve",
        "context": {"draft": "Release note v1", "policy_check": "passed"},
        "history": [
            {"step": "draft", "attempt": 1, "state": "completed"},
            {"step": "check", "attempt": 1, "state": "completed"},
            {"step": "approve", "attempt": 1, "state": "paused"},
        ],
    }
    _write(path, state)
    return state


def restore_from_step(path: Path, step: str) -> dict[str, Any]:
    """Invalidate downstream history and deterministically replay to approval."""

    if step not in STEP_ORDER[:-1]:
        raise ValueError(f"cannot restore from unsupported step: {step}")

    state = load_checkpoint(path)
    cutoff = STEP_ORDER.index(step)
    retained = [
        entry for entry in state["history"] if STEP_ORDER.index(entry["step"]) < cutoff
    ]
    attempts = {
        entry["step"]: max(
            item["attempt"] for item in state["history"] if item["step"] == entry["step"]
        )
        for entry in state["history"]
    }

    replayed = []
    for replay_step in STEP_ORDER[cutoff:2]:
        replayed.append(
            {
                "step": replay_step,
                "attempt": attempts.get(replay_step, 0) + 1,
                "state": "completed",
            }
        )
    replayed.append(
        {
            "step": "approve",
            "attempt": attempts.get("approve", 0) + 1,
            "state": "paused",
        }
    )
    state["history"] = retained + replayed
    state["status"] = "paused"
    state["current_step"] = "approve"
    _write(path, state)
    return state


def approve_and_publish(path: Path, reviewer: str) -> dict[str, Any]:
    """Resume a paused checkpoint after an explicit approval event."""

    state = load_checkpoint(path)
    if state["status"] != "paused" or state["current_step"] != "approve":
        raise RuntimeError("workflow is not waiting for approval")
    state["context"]["approval"] = {"approved": True, "reviewer": reviewer}
    state["history"].append(
        {
            "step": "approve",
            "attempt": state["history"][-1]["attempt"],
            "state": "completed",
        }
    )
    state["history"].append({"step": "publish", "attempt": 1, "state": "completed"})
    state["status"] = "succeeded"
    state["current_step"] = None
    _write(path, state)
    return state
