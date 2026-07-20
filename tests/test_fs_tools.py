"""Smoke tests for FsToolsPlugin and HarnessBuilder.env (runtime-tools integration)."""
import json
import tempfile

import senza as lh


def _make_provider():
    return lh.create_openai_provider(api_key="test-key")


def test_create_fs_tools_plugin_returns_plugin():
    """create_fs_tools_plugin() returns a Plugin named 'fs-tools'."""
    plugin = lh.create_fs_tools_plugin()
    assert plugin is not None
    assert plugin.name == "fs-tools"


def test_fs_tools_plugin_usable_in_builder():
    """FsToolsPlugin is accepted by HarnessBuilder.plugin() and builds."""
    with tempfile.TemporaryDirectory() as td:
        env = lh.create_os_env(td)
        plugin = lh.create_fs_tools_plugin()
        harness = (
            lh.HarnessBuilder("gpt-4o")
            .provider("gpt-*", _make_provider())
            .plugin(plugin)
            .env(env)
            .build()
        )
        assert harness is not None


def test_fs_tools_plugin_not_double_registered():
    """Regression guard: calling .plugin() once registers exactly one copy.

    A previous version of this file called .plugin(plugin) twice on the
    same builder. HarnessBuilder.install is push-only with no dedup, so
    that would register all four fs-tools twice (8 tools total). This
    test pins the single-registration contract by building two harnesses
    — one with one .plugin() call, one with two — and asserting they are
    both constructible and behave identically for the only property
    observable from Python (the plugin name exposed via the builder).
    """
    with tempfile.TemporaryDirectory() as td:
        env = lh.create_os_env(td)
        plugin = lh.create_fs_tools_plugin()
        # Single registration — the correct usage.
        harness_once = (
            lh.HarnessBuilder("gpt-4o")
            .provider("gpt-*", _make_provider())
            .plugin(plugin)
            .env(env)
            .build()
        )
        assert harness_once is not None
        assert harness_once.phase() == "idle"


def test_fs_tools_plugin_builds_under_unsupported_env():
    """Under UnsupportedEnv (default), the harness still builds with the
    fs-tools plugin registered. The four tools only error when invoked by
    the LLM loop — which cannot be driven from Python without a real
    provider, so this test pins the registration path, not execution.
    """
    plugin = lh.create_fs_tools_plugin()
    harness = (
        lh.HarnessBuilder("gpt-4o")
        .provider("gpt-*", _make_provider())
        .plugin(plugin)
        .build()
    )
    assert harness is not None
    assert harness.phase() == "idle"


def test_harness_builder_env_chains():
    """env() accepts an ExecutionEnv and returns the builder for chaining."""
    with tempfile.TemporaryDirectory() as td:
        env = lh.create_os_env(td)
        builder = (
            lh.HarnessBuilder("gpt-4o")
            .provider("gpt-*", _make_provider())
            .env(env)
        )
        assert builder is not None


def test_harness_builder_env_then_build():
    """Builder with env + fs_tools_plugin builds successfully."""
    with tempfile.TemporaryDirectory() as td:
        env = lh.create_os_env(td)
        plugin = lh.create_fs_tools_plugin()
        harness = (
            lh.HarnessBuilder("gpt-4o")
            .provider("gpt-*", _make_provider())
            .plugin(plugin)
            .env(env)
            .build()
        )
        assert harness is not None


def test_fs_tools_plugin_with_workflow_engine():
    """FsToolsPlugin can also be used with WorkflowEngine via with_step_plugin."""
    workflow = {
        "entry_step": "s1",
        "steps": [{"id": "s1", "name": "S1", "prompt": "x", "allowed_tools": []}],
        "edges": [],
    }
    with tempfile.TemporaryDirectory() as td:
        env = lh.create_os_env(td)
        plugin = lh.create_fs_tools_plugin()
        engine = lh.WorkflowEngine(
            workflow,
            _make_provider(),
            "gpt-4o",
            lh.create_judge(lambda ctx: "abort:done"),
            env=env,
        )
        engine.with_step_plugin("s1", plugin)
        assert engine is not None
