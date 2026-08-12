"""Tests for HarnessBuilder.tools() plural method."""

import senza


def test_tools_method_exists():
    """HarnessBuilder should have a tools() method accepting a list."""
    assert hasattr(senza.HarnessBuilder, "tools")


def test_tools_accepts_list():
    """tools() should accept a list of tools."""
    tool1 = senza.create_tool("t1", "test", {"type": "object", "properties": {}}, lambda a, c: None)
    tool2 = senza.create_tool("t2", "test", {"type": "object", "properties": {}}, lambda a, c: None)
    builder = senza.HarnessBuilder("gpt-4o").tools([tool1, tool2])
    assert builder is not None
