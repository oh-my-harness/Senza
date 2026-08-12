"""Tests for @senza.tool decorator."""

import inspect

import pytest

import senza


def test_tool_decorator_basic():
    """@senza.tool creates a Tool from a function with type hints."""

    @senza.tool
    def search(query: str, limit: int = 10) -> str:
        """Search the web."""
        return f"Results for {query} (top {limit})"

    assert search is not None
    assert hasattr(search, "name")
    assert search.name == "search"
    assert search.description == "Search the web."


    @senza.tool
    def search(query: str, limit: int = 10) -> str:
        """Search the web."""
        return f"Results for {query} (top {limit})"

    result = search.drive({"query": "cats", "limit": 5})
    assert len(result["content"]) == 1
    assert "cats" in result["content"][0]["text"]
    assert "5" in result["content"][0]["text"]


def test_tool_decorator_required_vs_optional():
    """Required params have no default; optional params have defaults."""

    @senza.tool
    def fetch(url: str, timeout: float = 30.0, verbose: bool = False) -> str:
        """Fetch a URL."""
        return url

    result = fetch.drive({"url": "http://example.com"})
    assert len(result["content"]) == 1
    assert "example.com" in result["content"][0]["text"]


def test_tool_decorator_str_return():
    """String return is wrapped as text content."""

    @senza.tool
    def greet(name: str) -> str:
        """Greet someone."""
        return f"Hello, {name}!"

    result = greet.drive({"name": "Alice"})
    assert result["content"][0]["text"] == "Hello, Alice!"


def test_tool_function_form():
    """senza.tool() can be called as a function with explicit params."""

    tool = senza.tool(
        name="search",
        description="Search the web",
        parameters={"query": {"type": "string"}},
        callback=lambda args: f"Results for {args['query']}",
    )
    assert tool.name == "search"
    result = tool.drive({"query": "cats"})
    assert "cats" in result["content"][0]["text"]


def test_tool_decorator_async():
    """@senza.tool works with async def callbacks."""

    import asyncio

    @senza.tool
    async def async_search(query: str) -> str:
        """Async search."""
        await asyncio.sleep(0)
        return f"Async results for {query}"

    result = async_search.drive({"query": "dogs"})
    assert "dogs" in result["content"][0]["text"]


def test_tool_decorator_no_hints():
    """Functions without type hints default to string params."""

    @senza.tool
    def plain(query):
        """Plain function."""
        return f"Got: {query}"

    result = plain.drive({"query": "test"})
    assert "test" in result["content"][0]["text"]
