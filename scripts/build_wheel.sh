#!/usr/bin/env bash
set -euo pipefail

# Build the Senza wheel from this repo.
#
# Reads the runtime commit SHA from senza-pkg/runtime.lock, injects it
# into Cargo.toml (replacing PLACEHOLDER), builds with maturin, then
# restores Cargo.toml.
#
# Usage:
#   ./scripts/build_wheel.sh                  # production wheel (no test-utils)
#   ./scripts/build_wheel.sh --test-utils     # dev wheel with test-utils feature

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3}"
EXTRA_FEATURES=""
if [ "${1:-}" = "--test-utils" ]; then
    EXTRA_FEATURES="test-utils"
fi
DEST="$REPO_ROOT/dist"
LOCK_FILE="$REPO_ROOT/senza-pkg/runtime.lock"
CARGO_TOML="$REPO_ROOT/Cargo.toml"

SHA=$(cat "$LOCK_FILE")
echo "==> Runtime pin: $SHA"

# Inject SHA into Cargo.toml (cp backup, perl for cross-platform in-place edit)
cp "$CARGO_TOML" "$CARGO_TOML.bak"
trap 'mv "$CARGO_TOML.bak" "$CARGO_TOML" 2>/dev/null || true' EXIT
perl -pi -e "s/PLACEHOLDER/$SHA/g" "$CARGO_TOML"

export PYO3_PYTHON="$(command -v $PYTHON)"

cd "$REPO_ROOT"
echo "==> Building wheel..."
if [ -n "$EXTRA_FEATURES" ]; then
    "$PYTHON" -m maturin build --release --features "extension-module,$EXTRA_FEATURES"
else
    "$PYTHON" -m maturin build --release --features extension-module
fi


WHEEL=$(ls "$REPO_ROOT/target/wheels/senza_sdk"*.whl "$REPO_ROOT/target/wheels/senza"*.whl 2>/dev/null | tail -1)
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
