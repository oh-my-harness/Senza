"""Tests for WorkflowEngine.list_tasks() classmethod (issue #74)."""

import json
import os
import tempfile

import senza


def _make_provider():
    return senza.create_openai_provider(api_key="test-key")


def _make_judge():
    return senza.create_judge(lambda ctx: "abort:done")


def test_list_tasks_empty_dir():
    """list_tasks on a non-existent dir returns empty list."""
    with tempfile.TemporaryDirectory() as d:
        tasks = senza.WorkflowEngine.list_tasks(os.path.join(d, "nonexistent"))
        assert tasks == []


def test_list_tasks_returns_tasks():
    """list_tasks returns task summaries from the store dir."""
    with tempfile.TemporaryDirectory() as d:
        # Simulate a task store by writing workflow.json files
        task1_dir = os.path.join(d, "task-aaa")
        os.makedirs(task1_dir)
        with open(os.path.join(task1_dir, "workflow.json"), "w") as f:
            json.dump(
                {
                    "status": "succeeded",
                    "current_step": "step3",
                    "step_history": [
                        {
                            "step_id": "s1",
                            "started_at": "2026-07-21T10:00:00Z",
                            "ended_at": "2026-07-21T10:05:00Z",
                            "transition": {"to": "s2"},
                        },
                        {
                            "step_id": "s2",
                            "started_at": "2026-07-21T10:05:00Z",
                            "ended_at": "2026-07-21T10:15:00Z",
                            "transition": {"to": "s3"},
                        },
                        {
                            "step_id": "s3",
                            "started_at": "2026-07-21T10:15:00Z",
                            "ended_at": "2026-07-21T10:30:00Z",
                            "transition": {"abort": {"reason": "done"}},
                        },
                    ],
                    "started_at": "2026-07-21T10:00:00Z",
                    "ended_at": "2026-07-21T10:30:00Z",
                },
                f,
            )

        task2_dir = os.path.join(d, "task-bbb")
        os.makedirs(task2_dir)
        with open(os.path.join(task2_dir, "workflow.json"), "w") as f:
            json.dump(
                {
                    "status": "running",
                    "current_step": "step1",
                    "step_history": [],
                },
                f,
            )

        tasks = senza.WorkflowEngine.list_tasks(d)
        assert len(tasks) == 2

        ids = [t["task_id"] for t in tasks]
        assert "task-aaa" in ids
        assert "task-bbb" in ids

        task1 = next(t for t in tasks if t["task_id"] == "task-aaa")
        assert task1["status"] == "succeeded"
        assert task1["current_step"] == "step3"
        assert task1["step_count"] == 3
        assert task1["started_at"] is not None

        task2 = next(t for t in tasks if t["task_id"] == "task-bbb")
        assert task2["status"] == "running"
        assert task2["step_count"] == 0


def test_list_tasks_skips_corrupt():
    """list_tasks skips dirs with corrupt workflow.json."""
    with tempfile.TemporaryDirectory() as d:
        good_dir = os.path.join(d, "task-good")
        os.makedirs(good_dir)
        with open(os.path.join(good_dir, "workflow.json"), "w") as f:
            json.dump({"status": "idle", "current_step": "s1", "step_history": []}, f)

        bad_dir = os.path.join(d, "task-bad")
        os.makedirs(bad_dir)
        with open(os.path.join(bad_dir, "workflow.json"), "w") as f:
            f.write("not json")

        empty_dir = os.path.join(d, "task-empty")
        os.makedirs(empty_dir)  # no workflow.json

        tasks = senza.WorkflowEngine.list_tasks(d)
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "task-good"


def test_list_tasks_sorted_by_started_at_desc():
    """list_tasks sorts most recent first."""
    with tempfile.TemporaryDirectory() as d:
        old_dir = os.path.join(d, "task-old")
        os.makedirs(old_dir)
        with open(os.path.join(old_dir, "workflow.json"), "w") as f:
            json.dump(
                {
                    "status": "succeeded",
                    "current_step": "s1",
                    "step_history": [],
                    "started_at": "2026-07-21T08:00:00Z",
                },
                f,
            )

        new_dir = os.path.join(d, "task-new")
        os.makedirs(new_dir)
        with open(os.path.join(new_dir, "workflow.json"), "w") as f:
            json.dump(
                {
                    "status": "succeeded",
                    "current_step": "s1",
                    "step_history": [],
                    "started_at": "2026-07-21T10:00:00Z",
                },
                f,
            )

        tasks = senza.WorkflowEngine.list_tasks(d)
        assert len(tasks) == 2
        assert tasks[0]["task_id"] == "task-new"
        assert tasks[1]["task_id"] == "task-old"
