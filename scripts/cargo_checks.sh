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
            cargo test --all
            ;;
        *)
            echo "ERROR: unknown stage '$stage' (use: fmt, clippy, test)" >&2
            exit 1
            ;;
    esac
done

echo ""
echo "==> Done."
