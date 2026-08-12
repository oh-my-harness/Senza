"""Tests for InMemoryTraceExporter binding."""

from __future__ import annotations

import senza


def test_trace_exporter_creates():
    exporter = senza.InMemoryTraceExporter()
    assert exporter is not None


def test_trace_exporter_empty_spans():
    exporter = senza.InMemoryTraceExporter()
    assert exporter.exported_spans() == []
    assert exporter.exported_span_count() == 0
