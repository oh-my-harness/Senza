"""Tests for McpManager lifecycle (no real server needed)."""

import senza


def test_manager_creation():
    manager = senza.McpManager()
    assert manager is not None


def test_manager_list_tools_empty():
    manager = senza.McpManager()
    assert manager.list_tools() == []


def test_manager_get_status_disconnected():
    manager = senza.McpManager()
    assert manager.get_status("nonexistent") == "disconnected"


def test_manager_errors_empty():
    manager = senza.McpManager()
    assert manager.errors() == {}


def test_manager_repr():
    manager = senza.McpManager()
    repr_str = repr(manager)
    assert "McpManager" in repr_str
    assert "servers=0" in repr_str
