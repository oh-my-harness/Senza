"""Tests for McpServerConfig construction."""

import senza


def test_stdio_config_basic():
    config = senza.McpServerConfig.stdio(command="npx")
    assert config is not None
    assert repr(config) == 'McpServerConfig.stdio(command="npx")'


def test_stdio_config_with_args():
    config = senza.McpServerConfig.stdio(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    )
    assert config is not None


def test_stdio_config_with_env():
    config = senza.McpServerConfig.stdio(
        command="node",
        args=["server.js"],
        env={"NODE_ENV": "production"},
        cwd="/srv",
        timeout=5000,
    )
    assert config is not None


def test_http_config_basic():
    config = senza.McpServerConfig.http(url="https://example.com/mcp")
    assert config is not None
    assert repr(config) == 'McpServerConfig.http(url="https://example.com/mcp")'


def test_http_config_with_headers():
    config = senza.McpServerConfig.http(
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer token"},
        timeout=30000,
    )
    assert config is not None


def test_sse_config_basic():
    config = senza.McpServerConfig.sse(url="https://example.com/sse")
    assert config is not None
    assert repr(config) == 'McpServerConfig.http(url="https://example.com/sse")'


def test_sse_config_with_headers():
    config = senza.McpServerConfig.sse(
        url="https://example.com/sse",
        headers={"X-API-Key": "secret"},
        timeout=10000,
    )
    assert config is not None
