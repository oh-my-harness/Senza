"""Tests for JsonlSessionRepo exposure and session_repo builder method."""

import tempfile

import senza


def test_jsonl_session_repo_exists():
    """senza.knowledge.jsonl_session_repo should be callable."""
    assert hasattr(senza.knowledge, "jsonl_session_repo")


def test_jsonl_session_repo_creates_repo():
    """jsonl_session_repo should return a SessionRepo object."""
    with tempfile.TemporaryDirectory() as d:
        repo = senza.knowledge.jsonl_session_repo(d)
        assert repo is not None


def test_session_repo_builder_method_exists():
    """HarnessBuilder should have a session_repo method."""
    assert hasattr(senza.HarnessBuilder, "session_repo")
