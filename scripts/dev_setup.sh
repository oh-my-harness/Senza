#!/usr/bin/env bash
set -euo pipefail

# Build + install the Senza wheel for local development.
#
# Creates (or reuses) a virtualenv at .venv/, builds the wheel via
# build_wheel.sh, and pip-installs it into the venv.
# After this, run check_stubs.py or examples directly.
#
# Usage:
#   ./scripts/dev_setup.sh                  # use .venv, python3
#   PYTHON=/path/to/python ./scripts/dev_setup.sh
#   VENV=/path/to/venv ./scripts/dev_setup.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3}"
VENV="${VENV:-$REPO_ROOT/.venv}"

# ── Create / reuse venv ──────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
    echo "==> Creating virtualenv at $VENV ..."
    "$PYTHON" -m venv "$VENV"
fi

# Activate and pick the venv interpreter
# shellcheck disable=SC1091
source "$VENV/bin/activate"
PYTHON="$(command -v python)"

# Ensure pip + maturin + pytest are present in the venv
echo "==> Ensuring build/test deps ..."
"$PYTHON" -m pip install --quiet --upgrade pip
"$PYTHON" -m pip install --quiet --upgrade maturin pytest

# ── Build wheel ──────────────────────────────────────────────────────
echo ""
echo "==> Building wheel ..."
"$SCRIPT_DIR/build_wheel.sh" --test-utils

WHEEL=$(ls "$REPO_ROOT"/dist/senza_sdk*.whl "$REPO_ROOT"/dist/senza*.whl 2>/dev/null | tail -1)
if [ -z "$WHEEL" ]; then
    echo "ERROR: No wheel found in $REPO_ROOT/dist/"
    exit 1
fi

# ── Install wheel into venv ──────────────────────────────────────────
echo ""
echo "==> Installing wheel ..."
"$PYTHON" -m pip install "$WHEEL" --force-reinstall

echo ""
echo "==> Setup complete."
echo "    Venv:  $VENV"
echo "    Wheel: $WHEEL"
echo ""
echo "Next steps:"
echo "    source $VENV/bin/activate"
echo "    python scripts/check_stubs.py              # verify .pyi stubs"
echo "    python -m pytest tests/ -v                 # run tests"
echo "    python examples/agent/01_basic_prompt.py   # run an example"
