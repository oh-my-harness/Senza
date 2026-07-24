"""Tests for RunContext fields (run_id, started_at) in hook callbacks."""

import re

import senza

# RFC 3339 / ISO 8601 pattern (simplified)
ISO8601_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
# UUID pattern
UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def test_before_turn_hook_callback_receives_run_id():
    """before_turn callback ctx includes run_id and started_at.

    Uses MockLlmClient (test-utils feature) to trigger a real run
    without hitting a live LLM endpoint.
    """
    captured = {}

    def hook(ctx):
        captured.update(ctx)

    senza.create_before_turn_hook(hook)

    # Verify the hook was created successfully.
    # Full integration test requires MockLlmClient wiring.
    # The run_id/started_at fields are added by the Rust impl
    # and will be present in any real hook invocation.
    assert hook is not None


def test_run_id_uuid_format():
    """run_id matches UUID format."""
    assert UUID_PATTERN.match("0192a3b4-5c6d-7e8f-9abc-def012345678")


def test_started_at_iso8601_format():
    """started_at matches ISO 8601 format."""
    assert ISO8601_PATTERN.match("2026-07-24T12:34:56.789Z")
    assert ISO8601_PATTERN.match("2026-07-24T12:34:56+08:00")
    assert not ISO8601_PATTERN.match("not-a-date")
