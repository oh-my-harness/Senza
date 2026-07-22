"""Session viewer for Senza-based agent applications.

Renders on-disk session logs produced by ``JsonlSessionRepo`` (the persistence
layer shared by ``llm-harness-runtime`` and Senza) as a self-contained HTML
page in the browser.

The JSONL parsing and branch-tree computation are delegated to the Rust
``session-viewer`` crate (exposed via ``senza.read_sessions``) so there is a
single source of truth for the on-disk format. This module only handles
HTTP serving and browser launching.

Usage::

    import senza.viewer
    senza.viewer.serve("/path/to/sessions")

Or from the command line::

    python -m senza.viewer /path/to/sessions [--port PORT]
"""

from __future__ import annotations

import http.server
import json
import socketserver
import sys
import threading
import webbrowser
from typing import Any

from . import read_sessions, viewer_html

__all__ = ["read_sessions", "render_page", "serve", "serve_on"]

# Path to the bundled HTML viewer, as returned by the Rust crate.
# Kept as a module-level cache after first access.
_HTML_CACHE: str | None = None


def _get_html() -> str:
    global _HTML_CACHE
    if _HTML_CACHE is None:
        _HTML_CACHE = viewer_html()
    return _HTML_CACHE


def render_page(data_json: str) -> str:
    """Return a self-contained HTML page with *data_json* embedded."""
    return _get_html().replace("__VIEWER_DATA_JSON__", data_json)


def serve(root: str | Any, port: int = 0) -> None:
    """Serve the viewer for *root* and open a browser. Blocks until interrupted."""
    serve_on(root, port)


def serve_on(root: str | Any, port: int = 0) -> None:
    """Like :func:`serve` but binds a specific port (0 = ephemeral)."""
    root_str = str(root)
    data = read_sessions(root_str)
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
        print(f"senza session-viewer serving {root_str} at {url}")
        # Best-effort browser open.
        threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")


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
