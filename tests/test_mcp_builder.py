"""Tests for MCP builder integration (no real server connection)."""

import senza


def test_builder_mcp_server_records_config():
    """mcp_server() records config without building."""
    builder = senza.HarnessBuilder("test-model")
    builder = builder.mcp_server(
        "fs",
        senza.McpServerConfig.stdio(command="echo", args=["hello"]),
    )
    assert "pending" in repr(builder)
    assert "mcp" in repr(builder)


def test_builder_mcp_config_file_records_path():
    """mcp_config_file() records path without reading."""
    builder = senza.HarnessBuilder("test-model")
    builder = builder.mcp_config_file("/nonexistent/mcp.json")
    assert "pending" in repr(builder)
    assert "mcp" in repr(builder)


def test_builder_multiple_mcp_servers():
    """Multiple mcp_server() calls accumulate."""
    builder = senza.HarnessBuilder("test-model")
    builder = builder.mcp_server("fs", senza.McpServerConfig.stdio(command="echo")).mcp_server(
        "remote", senza.McpServerConfig.http(url="https://example.com/mcp")
    )
    assert "pending" in repr(builder)
    assert "mcp" in repr(builder)


def test_builder_chains_fluent_after_mcp():
    """Fluent methods work after mcp_server()."""
    builder = (
        senza.HarnessBuilder("test-model")
        .mcp_server("fs", senza.McpServerConfig.stdio(command="echo"))
        .system_prompt("You are helpful.")
        .max_tokens(1000)
    )
    assert "pending" in repr(builder)
    assert "mcp" in repr(builder)


def test_builder_with_mcp_manager():
    """with_mcp_manager() accepts an external manager."""
    manager = senza.McpManager()
    builder = senza.HarnessBuilder("test-model").with_mcp_manager(manager)
    assert "pending" in repr(builder)
    assert "mcp" in repr(builder)


def test_builder_no_mcp_shows_no_mcp_flag():
    """Builder without MCP config doesn't show mcp flag."""
    builder = senza.HarnessBuilder("test-model")
    assert "mcp" not in repr(builder)
