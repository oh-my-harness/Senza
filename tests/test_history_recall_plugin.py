"""Tests for HistoryRecallPlugin bindings (Task 7)."""

import senza


def test_history_recall_plugin_creates():
    index = senza.create_in_memory_session_recall_index()
    repo = senza.create_in_memory_session_repo()
    recall_source = senza.create_session_recall_knowledge_source(repo=repo, index=index)
    plugin = senza.create_history_recall_plugin(source=recall_source)
    assert plugin is not None


def test_history_recall_plugin_with_config():
    index = senza.create_in_memory_session_recall_index()
    repo = senza.create_in_memory_session_repo()
    recall_source = senza.create_session_recall_knowledge_source(repo=repo, index=index)
    plugin = senza.create_history_recall_plugin(
        source=recall_source,
        config={"max_hits": 5, "timeout_ms": 1000},
    )
    assert plugin is not None


def test_history_recall_plugin_in_builder():
    index = senza.create_in_memory_session_recall_index()
    repo = senza.create_in_memory_session_repo()
    recall_source = senza.create_session_recall_knowledge_source(repo=repo, index=index)
    plugin = senza.create_history_recall_plugin(source=recall_source)
    provider = senza.create_openai_provider(api_key="sk-test")
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
