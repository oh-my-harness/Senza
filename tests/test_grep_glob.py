"""Verify grep/glob tools are auto-registered in FsToolsPlugin (runtime v0.5.0).

Runtime v0.5.0's FsToolsPlugin::register_tools pushes 6 tools:
read/write/edit/bash/grep/glob. Senza's create_fs_tools_plugin() calls
FsToolsPlugin::new(Some(store)), so grep and glob are included
automatically — no Senza code change is needed. These tests pin that
contract from the Python side.

The plugin wrapper is opaque (only exposes ``name``), and the built
harness exposes no tool-name introspection. We verify grep/glob
registration by calling ``set_tools([])`` to replace the tool list,
which emits a ``tools_update`` event whose ``removed`` field lists
every tool name that was registered before the replacement.
"""

import tempfile

import senza


def _make_provider():
    return senza.providers.openai(api_key="test-key")


def _build_harness(td):
    """Build a harness with fs-tools plugin + os env in a temp dir."""
    env = senza.create_os_env(td)
    plugin = senza.create_fs_tools_plugin()
    provider = _make_provider()
    return (
        senza.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .plugin(plugin)
        .env(env)
        .build()
    )


# ── Plugin-level checks ───────────────────────────────────────────────


def test_create_fs_tools_plugin_returns_valid_plugin():
    """create_fs_tools_plugin() returns a non-None plugin named 'fs-tools'."""
    plugin = senza.create_fs_tools_plugin()
    assert plugin is not None
    assert plugin.name == "fs-tools"


def test_fs_tools_plugin_harness_builds():
    """A harness built with the plugin + env enters idle (register_tools
    completed without error)."""
    with tempfile.TemporaryDirectory() as td:
        harness = _build_harness(td)
        assert harness is not None
        assert harness.phase() == "idle"


# ── Tool-name verification via set_tools probe ────────────────────────


def test_fs_tools_plugin_registers_grep_and_glob():
    """grep and glob are auto-registered by FsToolsPlugin.

    Calling ``set_tools([])`` replaces the entire tool list, emitting a
    ``tools_update`` event whose ``removed`` field contains every tool
    name that was registered before the replacement. If grep/glob are
    not in ``removed``, they were never registered.
    """
    with tempfile.TemporaryDirectory() as td:
        harness = _build_harness(td)
        assert harness.phase() == "idle"

        events_iter = harness.events(timeout_ms=2000)
        harness.set_tools([])
        collected = []
        for ev in events_iter:
            collected.append(ev)
            if isinstance(ev, dict) and ev.get("type") in ("settled", "aborted"):
                break

        removed = []
        for ev in collected:
            if isinstance(ev, dict) and ev.get("type") == "tools_update":
                removed = ev.get("removed", [])
                break

        assert "grep" in removed, f"grep not in registered tools; removed={removed}"
        assert "glob" in removed, f"glob not in registered tools; removed={removed}"


def test_fs_tools_plugin_registers_all_six_tools():
    """All six fs-tools (read/write/edit/bash/grep/glob) are registered.

    Same probe as above, but asserts the full expected tool set.
    """
    with tempfile.TemporaryDirectory() as td:
        harness = _build_harness(td)
        assert harness.phase() == "idle"

        events_iter = harness.events(timeout_ms=2000)
        harness.set_tools([])
        collected = []
        for ev in events_iter:
            collected.append(ev)
            if isinstance(ev, dict) and ev.get("type") in ("settled", "aborted"):
                break

        removed = []
        for ev in collected:
            if isinstance(ev, dict) and ev.get("type") == "tools_update":
                removed = ev.get("removed", [])
                break

        expected = {"read", "write", "edit", "bash", "grep", "glob"}
        assert set(removed) == expected, (
            f"registered tools mismatch; removed={sorted(removed)}, "
            f"expected={sorted(expected)}"
        )
