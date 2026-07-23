#!/usr/bin/env bash
set -euo pipefail

# Build Senza wheels for Android (arm64 + x86_64).
#
# Prerequisites:
#   - rustup target add aarch64-linux-android x86_64-linux-android
#   - Android NDK installed
#   - NDK_HOME env var set
#
# Usage:
#   NDK_HOME=/path/to/ndk ./scripts/build_android_wheel.sh
#
# To build only one target:
#   NDK_HOME=/path/to/ndk TARGETS="aarch64-linux-android" ./scripts/build_android_wheel.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -z "${NDK_HOME:-}" ]; then
    echo "ERROR: NDK_HOME is not set"
    exit 1
fi

# Detect NDK prebuilt directory name based on host OS.
# macOS (Intel & Apple Silicon) → darwin-x86_64
# Linux → linux-x86_64
# Windows → windows-x86_64
HOST_OS="$(uname -s)"
case "$HOST_OS" in
    Darwin) PREBUILT="darwin-x86_64" ;;
    Linux)  PREBUILT="linux-x86_64" ;;
    MINGW*|MSYS*|CYGWIN*) PREBUILT="windows-x86_64" ;;
    *) echo "ERROR: Unsupported host OS: $HOST_OS"; exit 1 ;;
esac

NDK_TOOLCHAIN="$NDK_HOME/toolchains/llvm/prebuilt/$PREBUILT"

# Targets to build (override with TARGETS env var).
DEFAULT_TARGETS="aarch64-linux-android x86_64-linux-android"
TARGETS="${TARGETS:-$DEFAULT_TARGETS}"

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
{
    echo '[net]'
    echo 'git-fetch-with-cli = true'
    echo ''
    echo '[target.aarch64-linux-android]'
    echo "linker = \"$NDK_TOOLCHAIN/bin/aarch64-linux-android24-clang\""
    echo "ar = \"$NDK_TOOLCHAIN/bin/llvm-ar\""
    echo 'rustflags = ["-C", "link-arg=-Wl,--no-as-needed", "-C", "link-arg=-lpython3.12"]'
    echo ''
    echo '[target.x86_64-linux-android]'
    echo "linker = \"$NDK_TOOLCHAIN/bin/x86_64-linux-android24-clang\""
    echo "ar = \"$NDK_TOOLCHAIN/bin/llvm-ar\""
    echo 'rustflags = ["-C", "link-arg=-Wl,--no-as-needed", "-C", "link-arg=-lpython3.12"]'
} > "$REPO_ROOT/.cargo/config.toml"

cd "$REPO_ROOT"

# Use maturin to build for each Android target.
# PYO3_PYTHON must point to a Python 3.9+ for abi3 compatibility.
export PYO3_PYTHON="${PYO3_PYTHON:-python3}"

mkdir -p "$REPO_ROOT/dist"

for target in $TARGETS; do
    echo ""
    echo "==> Building Android $target wheel..."

    # Set CC/CXX/AR for cc-rs (used by ring, etc.) — NDK clang has API-level suffix,
    # and NDK only ships llvm-ar (no per-target ar).
    # cc-rs looks for <VAR>_<target> with hyphens → underscores.
    target_underscore="${target//-/_}"
    export "CC_${target_underscore}=$NDK_TOOLCHAIN/bin/${target}24-clang"
    export "CXX_${target_underscore}=$NDK_TOOLCHAIN/bin/${target}24-clang++"
    export "AR_${target_underscore}=$NDK_TOOLCHAIN/bin/llvm-ar"

    "$PYO3_PYTHON" -m maturin build --release --target "$target"

    # Pick the newest wheel for this target.
    # maturin names Android wheels like: senza_sdk-1.0.0-cp39-abi3-android_24_x86_64.whl
    # Map target triple to the ABI tag used in the filename.
    case "$target" in
        aarch64-linux-android) abi_tag="arm64_v8a" ;;
        x86_64-linux-android)  abi_tag="x86_64" ;;
        *) abi_tag="$target" ;;
    esac
    WHEEL=$(ls -t "$REPO_ROOT"/target/wheels/senza*"$abi_tag"*.whl 2>/dev/null | head -1)
    if [ -z "$WHEEL" ]; then
        echo "ERROR: No wheel found in $REPO_ROOT/target/wheels/ for target $target (abi_tag=$abi_tag)"
        ls -la "$REPO_ROOT/target/wheels/" 2>/dev/null || true
        exit 1
    fi

    cp "$WHEEL" "$REPO_ROOT/dist/"
    echo "==> Built: $WHEEL"
    echo "==> Copied to: $REPO_ROOT/dist/$(basename "$WHEEL")"
done

echo ""
echo "==> All wheels built in $REPO_ROOT/dist/:"
ls -1 "$REPO_ROOT"/dist/senza*android*.whl 2>/dev/null || true
