#!/usr/bin/env bash
set -euo pipefail

# Run Rust checks: fmt, clippy, and tests.
#
# Injects the runtime SHA from senza-pkg/runtime.lock into Cargo.toml
# (replacing PLACEHOLDER), runs the requested checks, then restores
# Cargo.toml. This mirrors the build_wheel.sh injection pattern.
#
# Usage:
#   ./scripts/cargo_checks.sh              # fmt + clippy + test
#   ./scripts/cargo_checks.sh fmt          # cargo fmt --check only
#   ./scripts/cargo_checks.sh clippy       # cargo clippy only
#   ./scripts/cargo_checks.sh test         # cargo test only
#   ./scripts/cargo_checks.sh fmt clippy   # fmt + clippy

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCK_FILE="$REPO_ROOT/senza-pkg/runtime.lock"
CARGO_TOML="$REPO_ROOT/Cargo.toml"

# PyO3 needs PYO3_PYTHON to locate libpython for linking test binaries
# (cargo test links against libpython; without this, symbols like
# _PyBaseObject_Type are undefined). Prefer the venv python if present.
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    export PYO3_PYTHON="$REPO_ROOT/.venv/bin/python"
elif [ -z "${PYO3_PYTHON:-}" ]; then
    export PYO3_PYTHON="$(command -v python3)"
fi

if [ ! -f "$LOCK_FILE" ]; then
    echo "ERROR: $LOCK_FILE not found" >&2
    exit 1
fi

SHA=$(cat "$LOCK_FILE")
echo "==> Runtime pin: $SHA"

# Inject SHA into Cargo.toml (cp backup, perl for cross-platform in-place edit)
cp "$CARGO_TOML" "$CARGO_TOML.bak"
trap 'mv "$CARGO_TOML.bak" "$CARGO_TOML" 2>/dev/null || true' EXIT
perl -pi -e "s/PLACEHOLDER/$SHA/g" "$CARGO_TOML"

cd "$REPO_ROOT"

# Default: run all three
if [ "$#" -eq 0 ]; then
    STAGES=("fmt" "clippy" "test")
else
    STAGES=("$@")
fi

for stage in "${STAGES[@]}"; do
    case "$stage" in
        fmt)
            echo ""
            echo "==> cargo fmt --check ..."
            cargo fmt --check
            ;;
        clippy)
            echo ""
            echo "==> cargo clippy ..."
            cargo clippy --all-targets -- -D warnings
            ;;
        test)
            echo ""
            echo "==> cargo test ..."
            # PyO3 extension-module tests need a Python with a linkable
            # libpython (framework or shared). The default feature set
            # keeps `extension-module` off so the test binary links
            # against libpython; `auto-initialize` (dev-dep) boots the
            # interpreter. If the venv Python lacks a linkable library
            # (e.g. Xcode-bundled Python3.framework with no lib), cargo
            # test fails at link time with "library 'python3.x' not
            # found". That is an environment issue, not a code defect;
            # install python.org or Homebrew Python and recreate the
            # venv to fix. Capture output to keep the failure concise.
            if ! cargo test --all 2>&1 | tee /tmp/senza_cargo_test.log; then
                if grep -q "library 'python" /tmp/senza_cargo_test.log; then
                    echo "" >&2
                    echo "ERROR: cargo test failed to link libpython." >&2
                    echo "       The venv Python ($PYO3_PYTHON) lacks a linkable shared library." >&2
                    echo "       Install python.org or Homebrew Python, recreate .venv, and retry." >&2
                    echo "       (pytest tests/ covers functional verification in the meantime.)" >&2
                    exit 1
                fi
                exit 1
            fi
            ;;
        *)
            echo "ERROR: unknown stage '$stage' (use: fmt, clippy, test)" >&2
            exit 1
            ;;
    esac
done

echo ""
echo "==> Done."
