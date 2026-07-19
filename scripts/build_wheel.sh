#!/usr/bin/env bash
set -euo pipefail

# Build the Senza wheel from this repo.
#
# Reads the runtime commit SHA from senza-pkg/runtime.lock, injects it
# into Cargo.toml (replacing PLACEHOLDER), builds with maturin, then
# restores Cargo.toml.
#
# Feature model:
#   - pyo3 features (extension-module, abi3-py39, experimental-inspect)
#     come from [tool.maturin] in pyproject.toml — maturin reads them
#     automatically. Do NOT pass them via --features.
#   - Cargo features (test-utils) are passed via --features when needed.
#
# Usage:
#   ./scripts/build_wheel.sh                  # production wheel
#   ./scripts/build_wheel.sh --test-utils     # dev wheel with test-utils feature

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=_venv.sh
. "$SCRIPT_DIR/_venv.sh"
ensure_venv

EXTRA_FEATURES=""
if [ "${1:-}" = "--test-utils" ]; then
    EXTRA_FEATURES="test-utils"
fi
DEST="$REPO_ROOT/dist"
LOCK_FILE="$REPO_ROOT/senza-pkg/runtime.lock"
CARGO_TOML="$REPO_ROOT/Cargo.toml"

SHA=$(cat "$LOCK_FILE")
echo "==> Runtime pin: $SHA"

# Inject SHA into Cargo.toml (backup, perl in-place, restore on exit).
# Never pollute the working tree — Cargo.toml stays PLACEHOLDER in git.
cp "$CARGO_TOML" "$CARGO_TOML.bak"
trap 'mv "$CARGO_TOML.bak" "$CARGO_TOML" 2>/dev/null || true' EXIT
perl -pi -e "s/PLACEHOLDER/$SHA/g" "$CARGO_TOML"

cd "$REPO_ROOT"
echo "==> Building wheel..."
# pyo3 features come from pyproject.toml [tool.maturin]; only pass
# Cargo-level features here.
if [ -n "$EXTRA_FEATURES" ]; then
    "$PYTHON" -m maturin build --release --features "$EXTRA_FEATURES"
else
    "$PYTHON" -m maturin build --release
fi

# Pick the newest wheel by mtime so a stale wheel built for a different
# Python version or feature set never shadows the just-built one.
WHEEL=$(ls -t "$REPO_ROOT"/target/wheels/senza_sdk*.whl "$REPO_ROOT"/target/wheels/senza*.whl 2>/dev/null | head -1)
if [ -z "$WHEEL" ]; then
    echo "ERROR: No wheel found in $REPO_ROOT/target/wheels/"
    exit 1
fi

mkdir -p "$DEST"
cp "$WHEEL" "$DEST/"
echo "==> Built: $WHEEL"
echo "==> Copied to: $DEST/$(basename $WHEEL)"
echo ""
echo "==> Install with:"
echo "    pip install $DEST/$(basename $WHEEL)"
