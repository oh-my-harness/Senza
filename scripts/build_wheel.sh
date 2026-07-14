#!/usr/bin/env bash
set -euo pipefail

# Build the Senza (llm_harness_py) wheel from the runtime repo.
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

echo "==> Runtime: $RUNTIME_DIR"
echo "==> Python:  $PYTHON ($($PYTHON --version 2>&1))"

export PYO3_PYTHON="$(command -v $PYTHON)"

cd "$RUNTIME_DIR/crates/llm-harness-py"

echo "==> Building wheel..."
maturin build --release

WHEEL=$(ls target/wheels/*.whl)
echo "==> Built: $WHEEL"

cp "$WHEEL" "$DEST/"
echo "==> Copied to: $DEST/$(basename $WHEEL)"

echo ""
echo "==> Install with:"
echo "    pip install $DEST/$(basename $WHEEL)"
