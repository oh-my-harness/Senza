# shellcheck shell=bash
# Shared venv helpers for Senza scripts.
#
# Every script in this repo MUST source this file and call
# `ensure_venv` before invoking Python. This guarantees a single
# source of truth for the repo virtualenv:
#
#   - The venv lives at $REPO_ROOT/.venv (override with $VENV).
#   - If it is missing, it is created from a base Python that ships
#     a linkable libpython (required for PyO3 `cargo test`). We probe
#     known locations; the Xcode-bundled Python3.framework is skipped
#     because its LIBDIR does not exist on disk.
#   - If no linkable base Python is found, we error out.
#   - If the venv exists but its Python is not linkable, we error out
#     with a rebuild hint (delete .venv and rerun).
#
# After `ensure_venv` returns, these are set:
#   PYTHON     — absolute path to the venv interpreter
#   PYO3_PYTHON — same as PYTHON (for PyO3 build-config)
#
# Scripts should invoke Python via "$PYTHON" rather than `python3`.

# REPO_ROOT is expected to be set by the sourcing script.
: "${REPO_ROOT:?REPO_ROOT must be set before sourcing scripts/_venv.sh}"
VENV="${VENV:-$REPO_ROOT/.venv}"
VENV_PYTHON="$VENV/bin/python"

# Print "1" if the given interpreter ships a linkable libpython
# (sysconfig.LIBDIR exists on disk), else "0".
_py_libdir_exists() {
    "$1" -c "import sysconfig,os;print('1' if os.path.isdir(sysconfig.get_config_var('LIBDIR') or '') else '0')" 2>/dev/null
}

# Find a base Python that can create a linkable venv.
# Honors $BASE_PYTHON if set; otherwise probes known locations.
_resolve_base_python() {
    local candidate
    if [ -n "${BASE_PYTHON:-}" ]; then
        [ -x "$BASE_PYTHON" ] || { echo "ERROR: BASE_PYTHON=$BASE_PYTHON is not executable" >&2; return 1; }
        if [ "$(_py_libdir_exists "$BASE_PYTHON")" = "1" ]; then
            echo "$BASE_PYTHON"
            return 0
        fi
        echo "ERROR: BASE_PYTHON=$BASE_PYTHON has no linkable libpython (LIBDIR missing)." >&2
        echo "       Install python.org or Homebrew Python 3.12+ and rerun." >&2
        return 1
    fi
    for candidate in \
        "/opt/homebrew/bin/python3.12" \
        "/usr/local/bin/python3.12" \
        "/opt/homebrew/bin/python3.13" \
        "/usr/local/bin/python3.13" \
        "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12" \
        "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13"; do
        [ -x "$candidate" ] || continue
        [ "$(_py_libdir_exists "$candidate")" = "1" ] || continue
        echo "$candidate"
        return 0
    done
    return 1
}

ensure_venv() {
    # Existing venv: verify it is linkable.
    if [ -x "$VENV_PYTHON" ]; then
        if [ "$(_py_libdir_exists "$VENV_PYTHON")" = "1" ]; then
            PYTHON="$VENV_PYTHON"
            export PYO3_PYTHON="$PYTHON"
            return 0
        fi
        echo "ERROR: venv at $VENV is not linkable (its Python reports a" >&2
        echo "       LIBDIR that does not exist on disk). This typically" >&2
        echo "       happens when the venv was created from the Xcode-bundled" >&2
        echo "       Python3.framework. Rebuild it:" >&2
        echo "         rm -rf $VENV && ./scripts/dev_setup.sh" >&2
        return 1
    fi

    # No venv: create one from a linkable base Python.
    echo "==> Creating virtualenv at $VENV ..."
    local base
    if ! base="$(_resolve_base_python)"; then
        echo "ERROR: no linkable Python found. Install python.org or" >&2
        echo "       Homebrew Python 3.12+ (e.g. 'brew install python@3.12')" >&2
        echo "       then rerun this script. The Xcode-bundled Python3.framework" >&2
        echo "       cannot be used because it lacks a linkable libpython." >&2
        return 1
    fi
    echo "    Using base Python: $base"
    "$base" -m venv "$VENV" || { echo "ERROR: venv creation failed" >&2; return 1; }
    PYTHON="$VENV_PYTHON"
    "$PYTHON" -m pip install --quiet --upgrade pip || { echo "ERROR: pip upgrade failed" >&2; return 1; }
    export PYO3_PYTHON="$PYTHON"
}
