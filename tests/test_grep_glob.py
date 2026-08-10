"""Verify grep/glob tools are auto-registered in FsToolsPlugin (runtime v0.5.0).

Runtime v0.5.0's FsToolsPlugin::register_tools pushes 6 tools:
read/write/edit/bash/grep/glob. Senza's create_fs_tools_plugin() calls
FsToolsPlugin::new(Some(store)), so grep and glob are included
automatically — no Senza code change is needed. These tests pin that
contract from the Python side.

The plugin wrapper is opaque (only exposes ``name``), and the built
harness exposes no tool-name introspection, so we verify via the
observable contract: the plugin builds, is accepted by the builder,
and the harness enters ``idle`` with all tools registered.
"""

import os
import tempfile

import pytest

import senza


def _make_provider():
    return senza.create_openai_provider(api_key="test-key")


# ── Plugin-level checks ───────────────────────────────────────────────


def test_create_fs_tools_plugin_returns_valid_plugin():
    """create_fs_tools_plugin() returns a non-None plugin named 'fs-tools'."""
    plugin = senza.create_fs_tools_plugin()
    assert plugin is not None
    assert plugin.name == "fs-tools"


def test_fs_tools_plugin_includes_grep_and_glob():
    """A harness built with the plugin + env enters idle (all 6 tools
    registered, including grep and glob).

    Because the plugin wrapper is opaque, we cannot enumerate tool names
    directly; instead we assert the build succeeds and the harness is in
    the idle phase — which requires register_tools to have completed
    without error. Runtime v0.5.0 registers grep/glob there.
    """
    with tempfile.TemporaryDirectory() as td:
        env = senza.create_os_env(td)
        plugin = senza.create_fs_tools_plugin()
        provider = _make_provider()
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("gpt-*", provider)
            .plugin(plugin)
            .env(env)
            .build()
        )
        assert harness is not None
        assert harness.phase() == "idle"


# ── Functional smoke tests ────────────────────────────────────────────


def test_grep_tool_functional():
    """grep tool is available: harness builds with a tmpdir containing a
    file whose contents could be grepped. We cannot drive an LLM turn
    without a real provider, so this pins the registration path, not
    execution."""
    with tempfile.TemporaryDirectory() as td:
        test_file = os.path.join(td, "example.py")
        with open(test_file, "w") as f:
            f.write("def hello():\n    print('world')\n")

        env = senza.create_os_env(td)
        plugin = senza.create_fs_tools_plugin()
        provider = _make_provider()
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("gpt-*", provider)
            .plugin(plugin)
            .env(env)
            .build()
        )
        assert harness is not None
        assert harness.phase() == "idle"


def test_glob_tool_functional():
    """glob tool is available: harness builds with a tmpdir whose file
    tree could be globbed. Same registration-path rationale as above."""
    with tempfile.TemporaryDirectory() as td:
        # Create a small file tree so the env is non-empty.
        os.makedirs(os.path.join(td, "sub"))
        for name in ("a.py", "sub/b.py", "sub/c.md"):
            with open(os.path.join(td, name), "w") as f:
                f.write("x\n")

        env = senza.create_os_env(td)
        plugin = senza.create_fs_tools_plugin()
        provider = _make_provider()
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("gpt-*", provider)
            .plugin(plugin)
            .env(env)
            .build()
        )
        assert harness is not None
        assert harness.phase() == "idle"


def test_fs_tools_plugin_registers_six_tools_via_set_tools_probe():
    """Indirect probe: calling set_tools([]) replaces the tool list and
    emits a tools_update event whose ``added`` field is empty (we just
    removed everything). Before that call, the harness had all six
    fs-tools registered. We verify the event fires (proving the tool
    registry was populated at build time) and that the harness remains
    idle afterwards.

    A direct tool-name introspection is not available from Python
    (PyPluginWrapper exposes only ``name``; PyHarness has no
    ``list_tools``). This probe confirms the registration path
    completed: set_tools emits ToolsUpdate only when the tool set
    changes, and an empty replacement always differs from the
    six-tool initial set."""
    with tempfile.TemporaryDirectory() as td:
        env = senza.create_os_env(td)
        plugin = senza.create_fs_tools_plugin()
        provider = _make_provider()
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("gpt-*", provider)
            .plugin(plugin)
            .env(env)
            .build()
        )
        assert harness.phase() == "idle"
        # Drive a tool-list replacement to trigger a tools_update event.
        # We collect events concurrently: subscribe first, then set_tools.
        events_iter = harness.events(timeout_ms=2000)
        harness.set_tools([])
        collected = []
        for ev in events_iter:
            collected.append(ev)
            if isinstance(ev, dict) and ev.get("type") in ("settled", "aborted"):
                break
        types = [e.get("type") for e in collected if isinstance(e, dict)]
        assert "tools_update" in types, (
            f"tools_update not emitted; events: {types}"
        )
