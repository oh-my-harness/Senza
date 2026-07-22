"""Tests for senza.viewer.

The JSONL parsing and branch computation are delegated to the Rust
``session-viewer`` crate (exposed via ``senza.read_sessions``). These tests
verify the Python-side rendering and serving logic on top of the Rust
return value, plus a round-trip integration test using the real Rust
``read_sessions`` against synthetic on-disk sessions.
"""

from __future__ import annotations

import json
from pathlib import Path

from senza import read_sessions, viewer, viewer_html


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
    return json.dumps(
        {
            "id": id,
            "parent_id": parent_id,
            "timestamp": "2026-01-01T00:00:00Z",
            "payload": {
                "entry_type": "message",
                "role": role,
                "content": [{"type": "text", "text": f"hello {id}"}],
                "timestamp": "2026-01-01T00:00:00Z",
            },
        }
    )


# ── Rust-backed read_sessions integration ────────────────────────────────────


def test_rust_read_sessions_single_dir(tmp_path: Path) -> None:
    """read_sessions (Rust) reads a single session directory."""
    _write_session(tmp_path, _base_meta(name="test", model="gpt-4o"), [])
    data = read_sessions(str(tmp_path))
    assert data["root"] == str(tmp_path.resolve())
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["meta"]["id"] == "s1"
    assert data["sessions"][0]["entries"] == []


def test_rust_read_sessions_multiple(tmp_path: Path) -> None:
    """read_sessions (Rust) reads a sessions root with multiple subdirs."""
    _write_session(tmp_path / "a", _base_meta(id="a", updated_at="2026-01-01T00:00:00Z"))
    _write_session(tmp_path / "b", _base_meta(id="b", updated_at="2026-01-02T00:00:00Z"))
    data = read_sessions(str(tmp_path))
    assert len(data["sessions"]) == 2
    # Sorted by updated_at desc.
    assert data["sessions"][0]["meta"]["id"] == "b"
    assert data["sessions"][1]["meta"]["id"] == "a"


def test_rust_read_sessions_computes_branches(tmp_path: Path) -> None:
    """read_sessions (Rust) computes branches for a tree with two leaves."""
    # root(e1) -> e2 -> e3 (leaf, active)
    #               \-> e4 (leaf)
    entries = [
        _entry("e1", None),
        _entry("e2", "e1", role="assistant"),
        _entry("e3", "e2"),
        _entry("e4", "e2"),
    ]
    _write_session(tmp_path, _base_meta(active_cursor="e3"), entries)
    data = read_sessions(str(tmp_path))
    s = data["sessions"][0]
    assert len(s["branches"]) == 2
    active = [b for b in s["branches"] if b["is_active"]][0]
    assert active["path"] == ["e1", "e2", "e3"]
    other = [b for b in s["branches"] if not b["is_active"]][0]
    assert other["path"] == ["e1", "e2", "e4"]


def test_rust_read_sessions_non_message_entries(tmp_path: Path) -> None:
    """read_sessions (Rust) includes config entries and extracts leaf labels."""
    entries = [
        json.dumps(
            {
                "id": "e1",
                "parent_id": None,
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {
                    "entry_type": "model_change",
                    "to": "gpt-4o",
                    "provider": "openai",
                    "model_id": None,
                },
            }
        ),
        json.dumps(
            {
                "id": "e2",
                "parent_id": "e1",
                "timestamp": "2026-01-01T00:00:01Z",
                "payload": {"entry_type": "label", "name": "checkpoint-1"},
            }
        ),
    ]
    _write_session(tmp_path, _base_meta(active_cursor="e2"), entries)
    data = read_sessions(str(tmp_path))
    s = data["sessions"][0]
    assert len(s["entries"]) == 2
    assert s["entries"][0]["payload"]["entry_type"] == "model_change"
    branch = s["branches"][0]
    assert branch["label"] == "checkpoint-1"


def test_rust_read_sessions_skips_unreadable(tmp_path: Path) -> None:
    """read_sessions (Rust) skips sessions with invalid meta.json."""
    _write_session(tmp_path / "good", _base_meta(id="good"))
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "meta.json").write_text("{not json", encoding="utf-8")
    data = read_sessions(str(tmp_path))
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["meta"]["id"] == "good"


# ── Python-side rendering ────────────────────────────────────────────────────


def test_viewer_html_contains_placeholder() -> None:
    """viewer_html() returns the HTML with the data placeholder."""
    html = viewer_html()
    assert "__VIEWER_DATA_JSON__" in html
    assert "viewer-data" in html


def test_render_page_replaces_placeholder() -> None:
    """render_page splices data into the HTML."""
    data = {"root": "/tmp/x", "sessions": []}
    page = viewer.render_page(json.dumps(data))
    assert "__VIEWER_DATA_JSON__" not in page
    assert "/tmp/x" in page
    assert "<html" in page.lower()


def test_render_page_with_real_data(tmp_path: Path) -> None:
    """render_page works with real read_sessions output."""
    _write_session(tmp_path, _base_meta(), [_entry("e1", None)])
    data = read_sessions(str(tmp_path))
    page = viewer.render_page(json.dumps(data))
    assert "e1" in page
    assert "viewer-data" in page


def test_html_cache_reused() -> None:
    """_get_html caches the HTML string after first call."""
    h1 = viewer._get_html()
    h2 = viewer._get_html()
    assert h1 is h2  # same object, cached


# ── CLI ──────────────────────────────────────────────────────────────────────


def test_cli_no_args_returns_2() -> None:
    assert viewer._main([]) == 2


def test_cli_help_returns_0() -> None:
    assert viewer._main(["--help"]) == 0
