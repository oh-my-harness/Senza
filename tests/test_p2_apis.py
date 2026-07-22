"""Tests for P2 advanced APIs — compaction config, queue clearing,
active_tools, and session/branch management."""

import senza


def _make_harness():
    provider = senza.create_openai_provider(api_key="sk-test")
    return senza.HarnessBuilder("gpt-4o").provider("gpt-*", provider).build()


# ── Builder compaction config ────────────────────────────────────────────────


def test_builder_auto_compact():
    provider = senza.create_openai_provider(api_key="sk-test")
    b = senza.HarnessBuilder("gpt-4o").provider("gpt-*", provider).auto_compact(False)
    h = b.build()
    assert h is not None


def test_builder_compaction_reserve_tokens():
    provider = senza.create_openai_provider(api_key="sk-test")
    b = senza.HarnessBuilder("gpt-4o").provider("gpt-*", provider).compaction_reserve_tokens(2048)
    h = b.build()
    assert h is not None


def test_builder_compaction_keep_recent_tokens():
    provider = senza.create_openai_provider(api_key="sk-test")
    b = (
        senza.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .compaction_keep_recent_tokens(1024)
    )
    h = b.build()
    assert h is not None


def test_builder_all_compaction_combined():
    provider = senza.create_openai_provider(api_key="sk-test")
    b = (
        senza.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .auto_compact(True)
        .compaction_reserve_tokens(4096)
        .compaction_keep_recent_tokens(2048)
    )
    h = b.build()
    assert h is not None


# ── Queue clearing ───────────────────────────────────────────────────────────


def test_has_queued_messages_idle():
    h = _make_harness()
    assert h.has_queued_messages() is False


def test_clear_steering_queue():
    h = _make_harness()
    h.clear_steering_queue()


def test_clear_follow_up_queue():
    h = _make_harness()
    h.clear_follow_up_queue()


def test_clear_all_queues():
    h = _make_harness()
    h.clear_all_queues()


# ── Active tools ─────────────────────────────────────────────────────────────


def test_set_active_tools_with_list():
    h = _make_harness()
    h.set_active_tools(["tool_a", "tool_b"])


def test_set_active_tools_none():
    h = _make_harness()
    h.set_active_tools(None)


# ── Session / Branch management ──────────────────────────────────────────────


def test_list_branches_empty():
    h = _make_harness()
    branches = h.list_branches()
    assert isinstance(branches, list)
    assert len(branches) == 0


def test_read_active_path_empty():
    h = _make_harness()
    path = h.read_active_path()
    assert isinstance(path, list)


def test_read_all_entries_empty():
    h = _make_harness()
    entries = h.read_all_entries()
    assert isinstance(entries, list)


def test_delete_branch_invalid_id():
    """delete_branch with an invalid UUID string should raise."""
    import pytest

    h = _make_harness()
    with pytest.raises(Exception):
        h.delete_branch("not-a-uuid")


def test_navigate_tree_invalid_id():
    import pytest

    h = _make_harness()
    with pytest.raises(Exception):
        h.navigate_tree("not-a-uuid")
