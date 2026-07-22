#!/usr/bin/env bash
set -euo pipefail

# Run all checks: Rust (fmt, clippy, test) and Python (pytest).
#
# Injects the runtime SHA from senza-pkg/runtime.lock into Cargo.toml
# (replacing PLACEHOLDER), runs the requested checks, then restores
# Cargo.toml. This mirrors the build_wheel.sh injection pattern.
#
# Usage:
#   ./scripts/cargo_checks.sh              # fmt + clippy + cargo test + pytest
#   ./scripts/cargo_checks.sh fmt          # cargo fmt --check only
#   ./scripts/cargo_checks.sh clippy       # cargo clippy only
#   ./scripts/cargo_checks.sh test         # cargo test only (Rust integration tests)
#   ./scripts/cargo_checks.sh pytest       # pytest only (Python tests in tests/)
#   ./scripts/cargo_checks.sh fmt clippy   # fmt + clippy

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCK_FILE="$REPO_ROOT/senza-pkg/runtime.lock"
CARGO_TOML="$REPO_ROOT/Cargo.toml"

# shellcheck source=_venv.sh
. "$SCRIPT_DIR/_venv.sh"
ensure_venv
# PYO3_PYTHON is exported by ensure_venv and points at the repo venv
# interpreter, which ships a linkable libpython (guaranteed by
# _venv.sh's viability check). cargo test links against it.

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
# Default: run all five stages
if [ "$#" -eq 0 ]; then
    STAGES=("fmt" "pyfmt" "clippy" "test" "pytest")
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
        pyfmt)
            echo ""
            echo "==> ruff format --check + ruff check ..."
            "$PYTHON" -m ruff format --check examples/ tests/ senza-pkg/senza/viewer.py
            "$PYTHON" -m ruff check examples/ tests/ senza-pkg/senza/viewer.py
            ;;
        clippy)
            echo ""
            echo "==> cargo clippy ..."
            cargo clippy --all-targets -- -D warnings
            ;;
        test)
            echo ""
            echo "==> cargo test (with --ignored for embedded-Python tests) ..."
            # The default feature set keeps `extension-module` off so the
            # test binary links against libpython; `auto-initialize`
            # (dev-dep) boots the interpreter. Integration tests are
            # #[ignore]'d because they embed a Python interpreter;
            # `-- --ignored` runs them. PYO3_PYTHON (from _venv.sh)
            # points at the repo venv, whose linkability is verified
            # upfront by ensure_venv.
            if ! cargo test --all -- --ignored 2>&1 | tee /tmp/senza_cargo_test.log; then
                if grep -q "library 'python" /tmp/senza_cargo_test.log; then
                    echo "" >&2
                    echo "ERROR: cargo test failed to link libpython." >&2
                    echo "       PYO3_PYTHON=$PYO3_PYTHON is not linkable." >&2
                    echo "       Rebuild the repo venv from a linkable base Python:" >&2
                    echo "         rm -rf $REPO_ROOT/.venv && ./scripts/dev_setup.sh" >&2
                    exit 1
                fi
                exit 1
            fi
            ;;
        pytest)
            echo ""
            echo "==> pytest tests/ ..."
            # Python tests live alongside the Rust integration tests in
            # tests/*.py. They exercise the Senza Python API (built into
            # the venv by dev_setup.sh / build_wheel.sh --test-utils).
            # The repo venv (from _venv.sh) provides both the interpreter
            # and the installed senza module.
            if ! "$PYTHON" -m pytest tests/ -q 2>&1 | tee /tmp/senza_pytest.log; then
                exit 1
            fi
            ;;
        *)
            echo "ERROR: unknown stage '$stage' (use: fmt, pyfmt, clippy, test, pytest)" >&2
            exit 1
    esac
done

echo ""
echo "==> Done."
