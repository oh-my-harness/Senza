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
# _PyBaseObject_Type are undefined). The chosen Python must ship a
# linkable libpython (python.org or Homebrew builds do; Xcode-bundled
# Python3.framework does not, causing "library 'python3.x' not found").
#
# Selection order (first viable wins):
#   1. explicit $PYO3_PYTHON from the environment
#   2. Homebrew python3 on PATH (known to ship a linkable framework)
#   3. the venv python (may be unviable; see #2 rationale)
#   4. python3 on PATH
# Viability check: LIBDIR resolves to a directory that actually exists
# (Xcode-bundled Python reports a LIBDIR under Python3.framework that
# is never present on disk).
py_libdir_exists() {
    "$1" -c "import sysconfig,os;print('1' if os.path.isdir(sysconfig.get_config_var('LIBDIR') or '') else '0')" 2>/dev/null
}
if [ -z "${PYO3_PYTHON:-}" ]; then
    for candidate in \
        "/opt/homebrew/bin/python3.12" \
        "/usr/local/bin/python3.12" \
        "$REPO_ROOT/.venv/bin/python" \
        "$(command -v python3)"; do
        [ -x "$candidate" ] || continue
        if [ "$(py_libdir_exists "$candidate")" = "1" ]; then
            PYO3_PYTHON="$candidate"
            break
        fi
    done
    if [ -z "${PYO3_PYTHON:-}" ]; then
        # No viable Python found; fall back to venv/python3 so the
        # link-failure diagnostic below names a concrete path.
        PYO3_PYTHON="${REPO_ROOT:+$REPO_ROOT/.venv/bin/python}"
        [ -x "$PYO3_PYTHON" ] || PYO3_PYTHON="$(command -v python3)"
    fi
fi
export PYO3_PYTHON

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
            echo "==> cargo test (with --ignored for embedded-Python tests) ..."
            # PyO3 extension-module tests need a Python with a linkable
            # libpython (framework or shared). The default feature set
            # keeps `extension-module` off so the test binary links
            # against libpython; `auto-initialize` (dev-dep) boots the
            # interpreter. Integration tests are #[ignore]'d because
            # they embed a Python interpreter; `-- --ignored` runs them.
            #
            # If PYO3_PYTHON lacks a linkable libpython (e.g.
            # Xcode-bundled Python3.framework with no lib), cargo test
            # fails at link time with "library 'python3.x' not found".
            # That is an environment issue, not a code defect; install
            # python.org or Homebrew Python and point PYO3_PYTHON at it.
            # Capture output to keep the failure concise.
            if ! cargo test --all -- --ignored 2>&1 | tee /tmp/senza_cargo_test.log; then
                if grep -q "library 'python" /tmp/senza_cargo_test.log; then
                    echo "" >&2
                    echo "ERROR: cargo test failed to link libpython." >&2
                    echo "       PYO3_PYTHON=$PYO3_PYTHON lacks a linkable shared library." >&2
                    echo "       Install python.org or Homebrew Python, then:" >&2
                    echo "         PYO3_PYTHON=/opt/homebrew/bin/python3.12 $0 test" >&2
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
