"""Session viewer for Senza-based agent applications.

Reads on-disk session logs produced by ``JsonlSessionRepo`` (the persistence
layer shared by ``llm-harness-runtime`` and Senza) and renders them as a
self-contained HTML page in the browser.

This module is pure-Python (stdlib only) and does not depend on the PyO3
``.so`` — any application built on Senza or ``llm-harness-runtime`` that
persists sessions via ``JsonlSessionRepo`` can use it.

Usage::

    import senza.viewer
    senza.viewer.serve("/path/to/sessions")

Or from the command line::

    python -m senza.viewer /path/to/sessions [--port PORT]
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any

__all__ = ["read_sessions", "serve", "serve_on", "render_page"]

# Path to the bundled HTML viewer. The HTML is sourced from
# llm-harness-runtime/crates/session-viewer/static/viewer.html and copied
# into this package at build time (see scripts/sync_viewer_html.sh).
_VIEWER_HTML_PATH = Path(__file__).parent / "_viewer.html"


# ── On-disk types (mirror of llm-harness-agent session types) ──────────────────


def _read_meta(meta_path: Path) -> dict[str, Any]:
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_entries(entries_path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with open(entries_path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(
                    f"warning: skip unparseable entry in {entries_path}:{lineno}: {e}",
                    file=sys.stderr,
                )
    return entries


def _compute_branches(entries: list[dict[str, Any]], meta: dict[str, Any]) -> list[dict[str, Any]]:
    by_id: dict[str, int] = {}
    children: dict[str | None, list[int]] = {}
    for i, e in enumerate(entries):
        by_id[e["id"]] = i
        children.setdefault(e.get("parent_id"), []).append(i)

    is_parent = set(e["id"] for e in entries if e["id"] in children)
    active_cursor = meta.get("active_cursor")
    branches: list[dict[str, Any]] = []
    for e in entries:
        if e["id"] not in is_parent:
            # Leaf — walk root-first.
            path = [e["id"]]
            cur = e
            while cur.get("parent_id") is not None:
                pid = cur["parent_id"]
                if pid not in by_id:
                    break
                path.append(pid)
                cur = entries[by_id[pid]]
            path.reverse()
            branches.append({
                "path": path,
                "is_active": active_cursor == e["id"],
                "label": _leaf_label(e.get("payload", {})),
            })
    return branches


def _leaf_label(payload: dict[str, Any]) -> str | None:
    if payload.get("entry_type") == "label":
        name = payload.get("name")
        if isinstance(name, str):
            return name
    return None


def _read_one_session(dir_path: Path) -> dict[str, Any]:
    meta = _read_meta(dir_path / "meta.json")
    entries_path = dir_path / "entries.jsonl"
    entries = _read_entries(entries_path) if entries_path.is_file() else []
    branches = _compute_branches(entries, meta)
    active_cursor = meta.get("active_cursor")
    active_index = None
    if active_cursor is not None:
        for i, e in enumerate(entries):
            if e["id"] == active_cursor:
                active_index = i
                break
    return {
        "meta": meta,
        "entries": entries,
        "branches": branches,
        "active_index": active_index,
    }


def read_sessions(root: str | os.PathLike[str]) -> dict[str, Any]:
    """Read all sessions under *root*.

    *root* may be a sessions root (containing ``<session_id>/`` subdirs) or
    a single session directory (containing ``meta.json`` + ``entries.jsonl``).
    """
    root_path = Path(root).resolve()
    if (root_path / "meta.json").is_file():
        sessions = [_read_one_session(root_path)]
        return {"root": str(root_path), "sessions": sessions}

    sessions: list[dict[str, Any]] = []
    if root_path.is_dir():
        for entry in sorted(root_path.iterdir()):
            if not entry.is_dir():
                continue
            if not (entry / "meta.json").is_file():
                continue
            try:
                sessions.append(_read_one_session(entry))
            except Exception as e:  # noqa: BLE001
                print(f"warning: skip session {entry}: {e}", file=sys.stderr)
    sessions.sort(key=lambda s: s["meta"].get("updated_at", ""), reverse=True)
    return {"root": str(root_path), "sessions": sessions}


# ── HTML rendering ────────────────────────────────────────────────────────────


def render_page(data_json: str) -> str:
    """Return a self-contained HTML page with *data_json* embedded."""
    html = _VIEWER_HTML_PATH.read_text(encoding="utf-8")
    return html.replace("__VIEWER_DATA_JSON__", data_json)


# ── HTTP server ───────────────────────────────────────────────────────────────


def serve(root: str | os.PathLike[str], port: int = 0) -> None:
    """Serve the viewer for *root* and open a browser. Blocks until interrupted."""
    serve_on(root, port)


def serve_on(root: str | os.PathLike[str], port: int = 0) -> None:
    """Like :func:`serve` but binds a specific port (0 = ephemeral)."""
    data = read_sessions(root)
    data_json = json.dumps(data)
    page = render_page(data_json).encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, *args: Any) -> None:
            pass  # silence

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        actual_port = httpd.server_address[1]
        url = f"http://127.0.0.1:{actual_port}"
        print(f"senza session-viewer serving {root} at {url}")
        # Best-effort browser open.
        threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")


# ── CLI ───────────────────────────────────────────────────────────────────────


def _main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("usage: python -m senza.viewer <dir> [--port PORT]")
        return 0 if args else 2
    root = args[0]
    port = 0
    i = 1
    while i < len(args):
        if args[i] == "--port":
            i += 1
            port = int(args[i])
        i += 1
    serve_on(root, port)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
