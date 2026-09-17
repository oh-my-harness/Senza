"""Verification tests for issues #3 and #4.

Issue #4: create_shell_executor was unusable because WorkflowEngine used
         UnsupportedEnvFactory, whose execute_shell always errors.
         Fix: expose create_os_env(working_dir) + optional env= parameter
         on WorkflowEngine that injects an OS-backed ExecutionEnv.

Issue #3: with_max_retries semantics were undocumented and the judge ctx
         did not expose retry_count. Fix: docstrings clarify per-step
         semantics; judge ctx now includes retry_count.
"""

import pytest
import senza

# ── #4: create_os_env + env= parameter ──────────────────────────────────────


def test_create_os_env_returns_execution_env():
    """create_os_env returns an opaque ExecutionEnv wrapper (#4)."""
    env = senza.create_os_env(working_dir=".")
    assert env is not None
    assert type(env).__name__ == "ExecutionEnv"


def test_create_os_env_default_working_dir():
    """create_os_env defaults working_dir to '.' (#4)."""
    env = senza.create_os_env()
    assert env is not None


def test_workflow_engine_accepts_env_parameter():
    """WorkflowEngine.__new__ accepts an optional env= argument (#4)."""
    workflow = {
        "entry_step": "s1",
        "steps": [
            {
                "id": "s1",
                "name": "S1",
                "executor": "shell",
                "executor_config": {"command": "echo", "args": ["hi"]},
            }
        ],
        "edges": [],
    }
    env = senza.create_os_env(working_dir=".")
    engine = senza.WorkflowEngine(
        workflow,
        senza.providers.openai(api_key="test-key"),
        "gpt-4o",
        senza.create_judge(lambda ctx: "abort:done"),
        env=env,
    )
    assert engine.task_id().startswith("task-")


def test_shell_executor_runs_real_command_with_os_env():
    """ShellExecutor executes a real echo command when an OsEnv is provided (#4).

    This is the end-to-end verification that the issue is fixed: the
    built-in ShellExecutor (not a Python subprocess callback) runs `echo`
    against the host shell via the injected OsEnv.
    """
    workflow = {
        "entry_step": "greet",
        "steps": [
            {
                "id": "greet",
                "name": "Greet",
                "executor": "shell",
                "executor_config": {
                    "command": "echo",
                    "args": ["hello-from-shell"],
                },
            }
        ],
        "edges": [],
    }
    judge = senza.create_judge(lambda ctx: "abort:done")
    env = senza.create_os_env(working_dir=".")
    engine = senza.WorkflowEngine(
        workflow,
        senza.providers.openai(api_key="test-key"),
        "gpt-4o",
        judge,
        env=env,
    ).with_executor("shell", senza.create_shell_executor(["echo"]))
    engine.run()
    history = engine.step_history()
    assert len(history) == 1
    result = history[0]["result"]
    assert "hello-from-shell" in result["output"]
    assert result["structured"]["exit_code"] == 0


def test_shell_executor_without_env_fails():
    """Without env=, ShellExecutor cannot run shell commands (#4 regression guard).

    The engine uses UnsupportedEnv, whose execute_shell returns an error.
    The step should fail rather than silently executing commands.
    """
    workflow = {
        "entry_step": "greet",
        "steps": [
            {
                "id": "greet",
                "name": "Greet",
                "executor": "shell",
                "executor_config": {
                    "command": "echo",
                    "args": ["should-not-run"],
                },
            }
        ],
        "edges": [],
    }
    judge = senza.create_judge(lambda ctx: "abort:done")
    # No env= → UnsupportedEnv → execute_shell errors.
    engine = senza.WorkflowEngine(
        workflow,
        senza.providers.openai(api_key="test-key"),
        "gpt-4o",
        judge,
    ).with_executor("shell", senza.create_shell_executor(["echo"]))
    with pytest.raises(RuntimeError):
        engine.run()


# ── #3: retry_count in judge ctx + max_retries semantics ────────────────────
#
# Tests use a 2-step workflow so the engine invokes the judge (a single-step
# workflow with no edges is treated as a "free task" and skips the judge).


def _two_step_shell_workflow():
    return {
        "entry_step": "s",
        "steps": [
            {
                "id": "s",
                "name": "S",
                "executor": "shell",
                "executor_config": {"command": "echo", "args": ["x"]},
            },
            {
                "id": "done",
                "name": "Done",
                "executor": "shell",
                "executor_config": {"command": "echo", "args": ["done"]},
            },
        ],
        "edges": [{"from": "s", "to": "done"}],
    }


def _make_engine(judge, *, max_retries=3):
    """Build a 2-step shell workflow engine with OsEnv + ShellExecutor."""
    env = senza.create_os_env(working_dir=".")
    return (
        senza.WorkflowEngine(
            _two_step_shell_workflow(),
            senza.providers.openai(api_key="test-key"),
            "gpt-4o",
            judge,
            env=env,
        )
        .with_executor("shell", senza.create_shell_executor(["echo"]))
        .with_max_retries(max_retries)
    )


def test_judge_ctx_exposes_retry_count():
    """Judge callback ctx contains retry_count (#3).

    Judge retries step `s` once, then routes to `done` (and aborts there).
    retry_count must be 0 on the first call (after the initial execution)
    and 1 on the retry.
    """
    seen_counts = []

    def judge_cb(ctx):
        seen_counts.append(ctx["retry_count"])
        if ctx["step_id"] == "done":
            return "abort:done"
        if ctx["retry_count"] < 1:
            return "retry"
        return "to:done"

    engine = _make_engine(senza.create_judge(judge_cb), max_retries=3)
    engine.run()
    assert seen_counts == [0, 1, 0]


def test_max_retries_exceeded_fails_workflow():
    """with_max_retries(N) fails the workflow after N+1 retries (#3).

    Per-step semantics: max_retries=1 allows 1 retry; the 2nd retry triggers
    Failed. Judge always returns "retry".
    """
    engine = _make_engine(senza.create_judge(lambda ctx: "retry"), max_retries=1)
    # engine.run() raises because the task fails.
    with pytest.raises(RuntimeError, match="max_retries"):
        engine.run()
    assert engine.state() == "failed"


def test_composite_judge_ctx_exposes_retry_count():
    """CompositeJudge handler ctx also exposes retry_count (#3)."""
    seen_counts = []

    def on_s(ctx):
        seen_counts.append(ctx["retry_count"])
        return "retry"

    judge = senza.create_composite_judge()
    judge.on("s", on_s)

    engine = _make_engine(judge, max_retries=2)
    with pytest.raises(RuntimeError, match="max_retries"):
        engine.run()
    # max_retries=2 → 2 retries allowed, 3rd retry → Failed.
    # Judge is called after each execution of `s`: counts 0, 1, 2.
    assert seen_counts == [0, 1, 2]


def test_max_steps_exceeded_fails_workflow():
    """Regression: with_max_steps(N) is the workflow-level final backstop.

    A looping workflow (self-edge s → s, judge always routes back) runs until
    step_history reaches the cap, then the engine must terminate cleanly as
    Failed with the max_steps reason — no hang, no runaway.
    """
    workflow = {
        "entry_step": "s",
        "steps": [
            {
                "id": "s",
                "name": "S",
                "executor": "shell",
                "executor_config": {"command": "echo", "args": ["loop"]},
            },
        ],
        "edges": [{"from": "s", "to": "s"}],  # self-cycle: legal rework edge
    }
    judge = senza.create_judge(lambda ctx: "to:s")
    env = senza.create_os_env(working_dir=".")
    engine = (
        senza.WorkflowEngine(
            workflow,
            senza.providers.openai(api_key="test-key"),
            "gpt-4o",
            judge,
            env=env,
        )
        .with_executor("shell", senza.create_shell_executor(["echo"]))
        .with_max_steps(5)
    )
    with pytest.raises(RuntimeError, match="max_steps"):
        engine.run()
    assert engine.state() == "failed"
    # The valve fires exactly at the cap: 5 records in step_history.
    assert len(engine.step_history()) == 5


# ── terminal-safe cancel: late cancel must not overwrite terminal state ──────


def _two_step_engine(judge):
    """2-step shell workflow (edges required so the judge drives transitions;
    free tasks short-circuit the judge)."""
    env = senza.create_os_env(working_dir=".")
    return (
        senza.WorkflowEngine(
            _two_step_shell_workflow(),
            senza.providers.openai(api_key="test-key"),
            "gpt-4o",
            judge,
            env=env,
        )
        .with_executor("shell", senza.create_shell_executor(["echo"]))
    )


def test_cancel_after_succeeded_remains_succeeded():
    """Runtime terminal-safety through the Python binding: cancel after a
    successful run must be a no-op, preserving Succeeded and the result."""
    engine = _two_step_shell_workflow()
    engine = (
        senza.WorkflowEngine(
            _two_step_shell_workflow(),
            senza.providers.openai(api_key="test-key"),
            "gpt-4o",
            senza.create_judge(lambda ctx: "abort:done"),
            env=senza.create_os_env(working_dir="."),
        )
        .with_executor("shell", senza.create_shell_executor(["echo"]))
    )
    engine.run()
    assert engine.state() == "succeeded"
    history_before = engine.step_history()

    engine.cancel("late timeout")

    assert engine.state() == "succeeded"
    assert len(engine.step_history()) == len(history_before)


def test_cancel_after_failed_preserves_error():
    """Late cancel on a Failed workflow must not overwrite it as Cancelled."""
    judge = senza.create_judge(lambda ctx: "fail:route broken")
    engine = _make_engine(judge)
    with pytest.raises(RuntimeError):
        engine.run()
    assert engine.state() == "failed"
    history_before = engine.step_history()

    engine.cancel("late timeout")

    assert engine.state() == "failed"
    assert len(engine.step_history()) == len(history_before)
    # The original failure reason is preserved: the transition is still a
    # Fail record (a Cancelled overwrite would replace it with Abort).
    first = engine.step_history()[0]
    assert first["transition"]["type"] == "fail"
    assert first["transition"]["reason"] == "route broken"


def _chain_workflow(n_steps):
    """Linear chain of n_exec executor steps (no terminal stage — the judge
    aborts at the last one, matching Studio's abort-at-done routing)."""
    steps = [
        {"id": f"s{i}", "name": f"S{i}", "executor": "noop_exec"}
        for i in range(n_steps)
    ]
    edges = [{"from": steps[i]["id"], "to": steps[i + 1]["id"]} for i in range(n_steps - 1)]
    return {"entry_step": "s0", "steps": steps, "edges": edges}


def _chain_engine(n_steps, cap):
    def judge(ctx):
        sid = ctx["step_id"]
        return "abort:done" if sid == f"s{n_steps - 1}" else f"to:s{int(sid[1:]) + 1}"

    env = senza.create_os_env(working_dir=".")
    return (
        senza.WorkflowEngine(
            _chain_workflow(n_steps),
            senza.providers.openai(api_key="test-key"),
            "gpt-4o",
            senza.create_judge(judge),
            env=env,
        )
        .with_executor("noop_exec", senza.create_executor(lambda ctx: {"output": "ok", "structured": {}}))
        .with_max_steps(cap)
    )


def test_max_steps_boundary_exactly_at_cap_succeeds():
    """Boundary regression (Studio contract): a workflow that legitimately
    consumes exactly `cap` records — 75 executor transitions with the Studio
    max_steps=75 — must SUCCEED. Guards against off-by-one changes in the
    max_steps enforcement (e.g. counting the completion transition against
    the budget, which would fail a legitimately-completing workflow)."""
    engine = _chain_engine(75, 75)
    engine.run()
    assert engine.state() == "succeeded"
    assert len(engine.step_history()) == 75


def test_max_steps_boundary_one_over_budget_fails():
    """Symmetry: consuming one record beyond the cap must fail cleanly with
    the max_steps reason (proves the boundary is `>=`, not a lax `>`)."""
    engine = _chain_engine(76, 75)
    with pytest.raises(RuntimeError, match="max_steps \\(75\\) exceeded"):
        engine.run()
    assert engine.state() == "failed"
    assert len(engine.step_history()) == 75
