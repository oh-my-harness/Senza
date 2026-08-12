"""Tests for Sandbox binding."""
from __future__ import annotations

import platform

import pytest

import senza


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="SeatbeltSandbox is only available on macOS",
)
def test_seatbelt_sandbox_creates():
    sandbox = senza.create_seatbelt_sandbox()
    assert sandbox is not None
    assert sandbox.is_running() is False


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="SeatbeltSandbox is only available on macOS",
)
def test_seatbelt_sandbox_creates_with_config():
    sandbox = senza.create_seatbelt_sandbox(
        {
            "fs_allowlist": ["/tmp"],
            "work_dir": "/tmp/sandbox",
            "max_memory_mb": 512,
            "max_cpus": 2,
            "timeout_seconds": 30.0,
        }
    )
    assert sandbox is not None
    assert sandbox.is_running() is False


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="SeatbeltSandbox is only available on macOS",
)
def test_seatbelt_sandbox_start_fails_closed():
    """SeatbeltSandbox::start() returns error (fail-closed, not yet implemented)."""
    sandbox = senza.create_seatbelt_sandbox()
    with pytest.raises(RuntimeError):
        sandbox.start()
