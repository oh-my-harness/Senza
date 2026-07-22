#!/usr/bin/env bash
set -euo pipefail

# Build Senza wheel for Android aarch64.
#
# Prerequisites:
#   - rustup target add aarch64-linux-android
#   - Android NDK installed
#   - NDK_HOME env var set
#
# Usage:
#   NDK_HOME=/path/to/ndk ./scripts/build_android_wheel.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -z "${NDK_HOME:-}" ]; then
    echo "ERROR: NDK_HOME is not set"
    exit 1
fi

NDK_TOOLCHAIN="$NDK_HOME/toolchains/llvm/prebuilt/darwin-x86_64"

LOCK_FILE="$REPO_ROOT/senza-pkg/runtime.lock"
CARGO_TOML="$REPO_ROOT/Cargo.toml"

SHA=$(cat "$LOCK_FILE")
echo "==> Runtime pin: $SHA"

# Inject SHA into Cargo.toml (backup, inject, restore on exit).
cp "$CARGO_TOML" "$CARGO_TOML.bak"
trap 'mv "$CARGO_TOML.bak" "$CARGO_TOML" 2>/dev/null || true' EXIT
perl -pi -e "s/PLACEHOLDER/$SHA/g" "$CARGO_TOML"

# Write Android linker config into .cargo/config.toml
# The rustflags add -lpython3.12 so the .so declares a dependency on
# Chaquopy's libpython3.12.so, making PyExc_* symbols resolvable at runtime.
mkdir -p "$REPO_ROOT/.cargo"
cat > "$REPO_ROOT/.cargo/config.toml" << EOF
[net]
git-fetch-with-cli = true

[target.aarch64-linux-android]
linker = "$NDK_TOOLCHAIN/bin/aarch64-linux-android24-clang"
ar = "$NDK_TOOLCHAIN/bin/llvm-ar"
rustflags = ["-C", "link-arg=-lpython3.12"]
EOF

cd "$REPO_ROOT"
echo "==> Building Android aarch64 wheel..."

# Use maturin to build for Android target.
# PYO3_PYTHON must point to a Python 3.9+ for abi3 compatibility.
export PYO3_PYTHON="${PYO3_PYTHON:-python3}"

"$PYO3_PYTHON" -m maturin build --release --target aarch64-linux-android

# Pick the newest wheel
WHEEL=$(ls -t "$REPO_ROOT"/target/wheels/senza*.whl 2>/dev/null | head -1)
if [ -z "$WHEEL" ]; then
    echo "ERROR: No wheel found in $REPO_ROOT/target/wheels/"
    ls -la "$REPO_ROOT/target/wheels/" 2>/dev/null || true
    exit 1
fi

mkdir -p "$REPO_ROOT/dist"
cp "$WHEEL" "$REPO_ROOT/dist/"
echo "==> Built: $WHEEL"
echo "==> Copied to: $REPO_ROOT/dist/$(basename $WHEEL)"
echo ""
echo "==> Install with:"
echo "    pip install $REPO_ROOT/dist/$(basename $WHEEL)"
