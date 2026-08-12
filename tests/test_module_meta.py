"""Tests for senza module metadata (__doc__, __all__)."""

import senza


def test_module_has_docstring():
    """senza.__doc__ should be a non-empty string."""
    assert isinstance(senza.__doc__, str)
    assert len(senza.__doc__) > 0


def test_module_has_all():
    """senza.__all__ should be a non-empty list of strings."""
    assert isinstance(senza.__all__, list)
    assert len(senza.__all__) > 0
    for name in senza.__all__:
        assert isinstance(name, str)


def test_all_entries_exist_in_module():
    """Every name in __all__ must be an attribute of senza."""
    for name in senza.__all__:
        assert hasattr(senza, name), f"senza.__all__ contains '{name}' but it's not an attribute"


def test_key_apis_in_all():
    """Core public APIs must be in __all__."""
    expected = {
        "HarnessBuilder",
        "AgentHarness",
        "WorkflowEngine",
        "create_tool",
        "create_judge",
        "create_plugin",
        "tool",
        "extract_text",
        "providers",
        "hooks",
        "strategy",
        "knowledge",
        "infra",
        "rules",
    }
    assert expected.issubset(set(senza.__all__))
