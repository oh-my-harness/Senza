"""Tests for JsonlAuditSink binding."""

from __future__ import annotations

import os
import tempfile

import senza


def test_jsonl_audit_sink_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "audit.jsonl")
        sink = senza.JsonlAuditSink(path)
        assert sink is not None


def test_jsonl_audit_sink_validate_empty_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "audit.jsonl")
        # Create empty file
        with open(path, "w"):
            pass
        count = senza.JsonlAuditSink.validate(path)
        assert count == 0


def test_jsonl_audit_sink_validate_nonexistent_file():
    import pytest

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "nope.jsonl")
        with pytest.raises(Exception):
            senza.JsonlAuditSink.validate(path)
