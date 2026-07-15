#!/usr/bin/env bash
set -euo pipefail

# Build the Senza wheel from the runtime repo.
#
# The runtime crate's #[pymodule] is named `senza`, so the native extension
# is directly importable as `import senza`. maturin reads pyproject.toml
# from the Cargo.toml's directory, so we copy the Senza pyproject.toml
# (with package name, metadata, and maturin features) into the runtime
# crate directory before building.
#
# Usage:
#   ./scripts/build_wheel.sh                    # use local runtime checkout
#   ./scripts/build_wheel.sh /path/to/runtime   # specify runtime path
#   ./scripts/build_wheel.sh <git-rev>          # clone + checkout rev

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DIR="${RUNTIME_DIR:-/data/leiqiaojie2/oh-my-harness/llm-harness-runtime}"
PYTHON="${PYTHON:-python3.14}"
DEST="$REPO_ROOT/dist"

mkdir -p "$DEST"

# If arg is a directory, use it as runtime path
if [ -n "${1:-}" ] && [ -d "$1" ]; then
    RUNTIME_DIR="$1"
elif [ -n "${1:-}" ]; then
    # Arg is a git rev — clone fresh
    RUNTIME_DIR="/tmp/runtime-build"
    rm -rf "$RUNTIME_DIR"
    git clone --depth 1 https://github.com/oh-my-harness/llm-harness-runtime.git "$RUNTIME_DIR"
    cd "$RUNTIME_DIR"
    git fetch --depth 1 origin "$1"
    git checkout "$1"
fi

PY_CRATE_DIR="$RUNTIME_DIR/crates/llm-harness-py"

if [ ! -f "$PY_CRATE_DIR/Cargo.toml" ]; then
    echo "ERROR: Cargo.toml not found at $PY_CRATE_DIR/Cargo.toml"
    exit 1
fi

echo "==> Senza repo:  $REPO_ROOT"
echo "==> Runtime:     $RUNTIME_DIR"
echo "==> Py crate:    $PY_CRATE_DIR"
echo "==> Python:      $PYTHON ($($PYTHON --version 2>&1))"

# Copy Senza pyproject.toml (package metadata + maturin features) into the
# runtime crate directory. maturin reads pyproject.toml from there.
echo "==> Copying Senza pyproject.toml into runtime crate..."
cp "$REPO_ROOT/pyproject.toml" "$PY_CRATE_DIR/pyproject.toml"

export PYO3_PYTHON="$(command -v $PYTHON)"

cd "$PY_CRATE_DIR"

echo "==> Building wheel..."
maturin build --release

WHEEL=$(ls "$RUNTIME_DIR/target/wheels/senza"*.whl)
echo "==> Built: $WHEEL"

cp "$WHEEL" "$DEST/"
echo "==> Copied to: $DEST/$(basename $WHEEL)"

# Clean up: restore runtime crate's original pyproject.toml
git -C "$RUNTIME_DIR" checkout -- "$PY_CRATE_DIR/pyproject.toml" 2>/dev/null || true

echo ""
echo "==> Install with:"
echo "    pip install $DEST/$(basename $WHEEL)"
echo "    python -c 'import senza; print(senza.version())'"
