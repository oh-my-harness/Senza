"""Tests for senza.viewer — reads JsonlSessionRepo on-disk format and renders HTML."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from senza import viewer


def _write_session(dir_path: Path, meta: dict, entries: list[str] | None = None) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    text = "".join(line + "\n" for line in (entries or []))
    (dir_path / "entries.jsonl").write_text(text, encoding="utf-8")


def _base_meta(id: str = "s1", **overrides) -> dict:
    m = {
        "id": id,
        "name": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "model": None,
        "active_cursor": None,
        "parent_session_path": None,
    }
    m.update(overrides)
    return m


def _entry(id: str, parent_id: str | None, role: str = "user") -> str:
    return json.dumps({
        "id": id,
        "parent_id": parent_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "payload": {
            "entry_type": "message",
            "role": role,
            "content": [{"type": "text", "text": f"hello {id}"}],
            "timestamp": "2026-01-01T00:00:00Z",
        },
    })


def test_reads_single_session_dir(tmp_path: Path) -> None:
    _write_session(tmp_path, _base_meta(name="test", model="gpt-4o"), [])
    data = viewer.read_sessions(tmp_path)
    assert data["root"] == str(tmp_path.resolve())
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["meta"]["id"] == "s1"
    assert data["sessions"][0]["entries"] == []


def test_reads_sessions_root_multiple(tmp_path: Path) -> None:
    _write_session(tmp_path / "a", _base_meta(id="a", updated_at="2026-01-01T00:00:00Z"))
    _write_session(tmp_path / "b", _base_meta(id="b", updated_at="2026-01-02T00:00:00Z"))
    data = viewer.read_sessions(tmp_path)
    assert len(data["sessions"]) == 2
    # Sorted by updated_at desc.
    assert data["sessions"][0]["meta"]["id"] == "b"
    assert data["sessions"][1]["meta"]["id"] == "a"


def test_computes_branches(tmp_path: Path) -> None:
    # root(e1) -> e2 -> e3 (leaf, active)
    #               \-> e4 (leaf)
    entries = [
        _entry("e1", None),
        _entry("e2", "e1", role="assistant"),
        _entry("e3", "e2"),
        _entry("e4", "e2"),
    ]
    _write_session(tmp_path, _base_meta(active_cursor="e3"), entries)
    data = viewer.read_sessions(tmp_path)
    s = data["sessions"][0]
    assert len(s["branches"]) == 2
    active = [b for b in s["branches"] if b["is_active"]][0]
    assert active["path"] == ["e1", "e2", "e3"]
    other = [b for b in s["branches"] if not b["is_active"]][0]
    assert other["path"] == ["e1", "e2", "e4"]


def test_skips_unreadable_sessions(tmp_path: Path) -> None:
    _write_session(tmp_path / "good", _base_meta(id="good"))
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "meta.json").write_text("{not json", encoding="utf-8")
    data = viewer.read_sessions(tmp_path)
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["meta"]["id"] == "good"


def test_render_page_contains_data(tmp_path: Path) -> None:
    _write_session(tmp_path, _base_meta(), [_entry("e1", None)])
    data = viewer.read_sessions(tmp_path)
    page = viewer.render_page(json.dumps(data))
    assert "viewer-data" in page
    assert "e1" in page


def test_render_page_includes_bundled_html(tmp_path: Path) -> None:
    """render_page must load the bundled _viewer.html, not return empty."""
    page = viewer.render_page("{}")
    assert "<html" in page.lower()
    assert "__VIEWER_DATA_JSON__" not in page  # placeholder replaced


def test_bundled_html_exists() -> None:
    """The _viewer.html asset must be present in the package."""
    assert viewer._VIEWER_HTML_PATH.is_file()
    content = viewer._VIEWER_HTML_PATH.read_text(encoding="utf-8")
    assert "__VIEWER_DATA_JSON__" in content
    assert "viewer-data" in content


def test_non_message_entries_rendered(tmp_path: Path) -> None:
    """Config entries (model_change, label, etc.) are included in entries list."""
    entries = [
        json.dumps({
            "id": "e1", "parent_id": None, "timestamp": "2026-01-01T00:00:00Z",
            "payload": {"entry_type": "model_change", "to": "gpt-4o", "provider": "openai", "model_id": None},
        }),
        json.dumps({
            "id": "e2", "parent_id": "e1", "timestamp": "2026-01-01T00:00:01Z",
            "payload": {"entry_type": "label", "name": "checkpoint-1"},
        }),
    ]
    _write_session(tmp_path, _base_meta(active_cursor="e2"), entries)
    data = viewer.read_sessions(tmp_path)
    s = data["sessions"][0]
    assert len(s["entries"]) == 2
    assert s["entries"][0]["payload"]["entry_type"] == "model_change"
    # Label on leaf should be extracted.
    branch = s["branches"][0]
    assert branch["label"] == "checkpoint-1"
