#!/usr/bin/env bash
set -euo pipefail

# Build + install the Senza wheel for local development.
#
# Creates (or reuses) the repo virtualenv at .venv/, builds the wheel
# via build_wheel.sh, and pip-installs it into the venv. All scripts in
# this repo use the repo venv exclusively; if it cannot be created from
# a linkable Python, this script errors out.
#
# Usage:
#   ./scripts/dev_setup.sh
#   VENV=/path/to/venv ./scripts/dev_setup.sh
#   BASE_PYTHON=/opt/homebrew/bin/python3.12 ./scripts/dev_setup.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=_venv.sh
. "$SCRIPT_DIR/_venv.sh"

ensure_venv

# Ensure build/test deps are present in the venv.
echo "==> Ensuring build/test deps ..."
"$PYTHON" -m pip install --quiet --upgrade maturin pytest ruff

# ── Build wheel ──────────────────────────────────────────────────────
echo ""
echo "==> Building wheel ..."
"$SCRIPT_DIR/build_wheel.sh" --test-utils

WHEEL=$(ls -t "$REPO_ROOT"/dist/senza_sdk*.whl "$REPO_ROOT"/dist/senza*.whl 2>/dev/null | head -1)
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
