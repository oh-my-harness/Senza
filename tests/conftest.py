"""Pytest config: skip test-utils-dependent tests on production wheels.

The production wheel (built without the `test-utils` Cargo feature) does
not expose `senza.Agent` (its `#[new]` uses `MockLlmClient`) nor
`Tool.drive()` (a test-only helper). Both are gated behind the
`test-utils` feature and only available in the dev wheel built via
`scripts/build_wheel.sh --test-utils`.

When the installed wheel lacks `senza.Agent`, tests that require it are
skipped automatically so that `pytest tests/` against a production
wheel reports a clean skip rather than a failure.
"""
from __future__ import annotations

import pytest

import senza

# `senza.Agent` is registered only under the `test-utils` feature. Its
# absence signals a production wheel, under which `Tool.drive()` is also
# unavailable. Tests in the modules below depend on one or both.
_TEST_UTILS_MODULES = {
    "test_agent",
    "test_event_stream",
    "test_sync_tool",
    "test_async_tool",
    "test_async_stream",
    "test_event_loop_bridge",
}


def pytest_collection_modifyitems(config, items):
    if hasattr(senza, "Agent"):
        return  # test-utils feature active — nothing to skip

    skip = pytest.mark.skip(
        reason="requires the test-utils feature (senza.Agent / Tool.drive); "
        "build with scripts/build_wheel.sh --test-utils",
    )
    for item in items:
        module = item.fspath.basename[:-3]
        if module in _TEST_UTILS_MODULES:
            item.add_marker(skip)
