"""Tests for SessionRecallIndex + SessionRepo + KnowledgeSource bindings (Task 6)."""

import tempfile

import senza


def test_in_memory_session_recall_index_creates():
    index = senza.create_in_memory_session_recall_index()
    assert index is not None


def test_sqlite_session_recall_index_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        index = senza.create_sqlite_session_recall_index(
            path=tmpdir + "/recall.db"
        )
        assert index is not None


def test_in_memory_session_repo_creates():
    repo = senza.create_in_memory_session_repo()
    assert repo is not None


def test_session_recall_knowledge_source_creates():
    index = senza.create_in_memory_session_recall_index()
    repo = senza.create_in_memory_session_repo()
    source = senza.create_session_recall_knowledge_source(repo=repo, index=index)
    assert source is not None


def test_session_recall_knowledge_source_as_knowledge_source():
    index = senza.create_in_memory_session_recall_index()
    repo = senza.create_in_memory_session_repo()
    recall_source = senza.create_session_recall_knowledge_source(
        repo=repo, index=index
    )
    ks = recall_source.as_knowledge_source()
    assert ks is not None
