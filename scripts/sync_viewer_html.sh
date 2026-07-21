#!/usr/bin/env bash
# Sync the session-viewer HTML from the llm-harness-runtime checkout into
# the Senza Python package. The HTML is the single source of truth, authored
# in the runtime repo at crates/session-viewer/static/viewer.html.
#
# Usage:
#   ./scripts/sync_viewer_html.sh [PATH_TO_RUNTIME_REPO]
#
# If PATH_TO_RUNTIME_REPO is omitted, defaults to ../llm-harness-runtime.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DIR="${1:-$REPO_ROOT/../llm-harness-runtime}"
SRC="$RUNTIME_DIR/crates/session-viewer/static/viewer.html"
DEST="$REPO_ROOT/senza-pkg/senza/_viewer.html"

if [ ! -f "$SRC" ]; then
    echo "ERROR: viewer.html not found at $SRC" >&2
    echo "Pass the runtime repo path as an argument:" >&2
    echo "  $0 /path/to/llm-harness-runtime" >&2
    exit 1
fi

cp "$SRC" "$DEST"
echo "==> Synced viewer.html -> $DEST"
