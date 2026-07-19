#!/usr/bin/env python3
"""Verify senza .pyi stubs match runtime __text_signature__.

Usage:
    python scripts/check_stubs.py
    ./scripts/check_stubs.py

Must be run after `pip install` the senza wheel. Reads
senza-pkg/senza/__init__.pyi, introspects the installed senza
module, and exits 1 if signatures diverge.

This script always runs under the repo virtualenv (.venv/). If invoked
from another interpreter, it re-executes itself under .venv/bin/python.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VENV_PY = _REPO_ROOT / ".venv" / "bin" / "python"
if _VENV_PY.exists() and os.path.realpath(sys.executable) != os.path.realpath(str(_VENV_PY)):
    # Repo venv exists but we're not running under it — re-exec into it.
    # (Local dev: always use the repo venv. CI: no venv is created, so
    # the existence check above is false and we fall through to the
    # current interpreter, which has senza installed via setup-python.)
    os.execv(str(_VENV_PY), [str(_VENV_PY), __file__, *sys.argv[1:]])
import ast
from dataclasses import dataclass, field


@dataclass
class FuncSig:
    """A function/method signature extracted from .pyi or runtime."""
    params: list[str] = field(default_factory=list)
    defaults: set[str] = field(default_factory=set)


SKIP_DUNDER = {"__init__", "__enter__", "__exit__"}

# Methods that only exist when built with --features test-utils.
# The .pyi (production stubs) correctly omits them.
SKIP_RUNTIME_ONLY = {
    "Tool.drive",
    "Agent.prompt",
    "Agent.events",
    "Agent.abort",
    "Agent.message_count",
    "Agent.phase",
}

REPO_ROOT = Path(__file__).resolve().parent.parent
PYI_PATH = REPO_ROOT / "senza-pkg" / "senza" / "__init__.pyi"


def _is_property(func: ast.FunctionDef) -> bool:
    """Check if a function is decorated with @property."""
    for dec in func.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "property":
            return True
    return False

def _parse_pyi_from_string(pyi_source: str) -> dict[str, FuncSig]:
    """Parse .pyi source text into {qualified_name: FuncSig}."""
    tree = ast.parse(pyi_source)
    sigs: dict[str, FuncSig] = {}

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            if not _is_property(node):
                sigs[node.name] = _ast_func_to_sig(node)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not _is_property(item):
                    key = f"{node.name}.{item.name}"
                    sigs[key] = _ast_func_to_sig(item)

    return sigs


def _ast_func_to_sig(func: ast.FunctionDef) -> FuncSig:
    """Convert an ast.FunctionDef to FuncSig."""
    params: list[str] = []
    defaults_count = len(func.args.defaults)

    # positional args (posonly + regular)
    all_args = func.args.posonlyargs + func.args.args
    # In .pyi we don't use *args/**kwargs for senza API, but handle gracefully
    for i, arg in enumerate(all_args):
        params.append(arg.arg)

    # The last `defaults_count` positional args have defaults
    defaults: set[str] = set()
    if defaults_count > 0:
        for arg in all_args[-defaults_count:]:
            defaults.add(arg.arg)

    # *args / **kwargs — include in params if present (rare in .pyi)
    if func.args.vararg:
        params.append(f"*{func.args.vararg.arg}")
    if func.args.kwarg:
        params.append(f"**{func.args.kwarg.arg}")

    return FuncSig(params=params, defaults=defaults)


# Expose from_string for testing
parse_pyi_signatures = type("parse_pyi_signatures", (), {
    "from_string": staticmethod(_parse_pyi_from_string),
    "__call__": staticmethod(lambda path: _parse_pyi_from_string(Path(path).read_text())),
})


import inspect


def introspect_runtime_signatures() -> dict[str, FuncSig]:
    """Import senza and extract __text_signature__ from all public symbols."""
    import senza  # type: ignore

    sigs: dict[str, FuncSig] = {}

    # Module-level functions
    for name in dir(senza):
        if name.startswith("_"):
            continue
        obj = getattr(senza, name)
        if not callable(obj) or isinstance(obj, type):
            continue
        ts = getattr(obj, "__text_signature__", None)
        if ts and ts != ():
            sigs[name] = _parse_text_signature(ts)

    # Class methods
    for name in dir(senza):
        if name.startswith("_"):
            continue
        obj = getattr(senza, name)
        if not isinstance(obj, type):
            continue
        for mname in dir(obj):
            if mname.startswith("_") and mname not in SKIP_DUNDER:
                continue
            if mname not in SKIP_DUNDER and mname.startswith("_"):
                continue
            mobj = getattr(obj, mname, None)
            if not callable(mobj):
                continue
            ts = getattr(mobj, "__text_signature__", None)
            if ts and ts != ():
                sigs[f"{name}.{mname}"] = _parse_text_signature(ts)

    return sigs


def _parse_text_signature(ts: str) -> FuncSig:
    """Parse a __text_signature__ string like '($self, pattern, provider)'.

    PyO3 injects '$self' for methods. We normalize to 'self'.
    """
    # Strip outer parens
    inner = ts.strip()
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1]

    if not inner.strip():
        return FuncSig(params=[], defaults=set())

    params: list[str] = []
    defaults: set[str] = set()
    in_default = False

    # Split by comma, but respect nested parens/brackets
    parts: list[str] = []
    depth = 0
    current = ""
    for ch in inner:
        if ch in "([{":
            depth += 1
            current += ch
        elif ch in ")]}":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())

    for part in parts:
        # Skip positional-only marker and bare keyword-only separator
        if part == "/" or part == "*":
            continue
        if "=" in part:
            pname = part.split("=")[0].strip()
            # Normalize $self → self
            pname = pname.replace("$", "")
            params.append(pname)
            defaults.add(pname)
            in_default = True
        else:
            pname = part.strip().replace("$", "")
            if pname:
                params.append(pname)

    return FuncSig(params=params, defaults=defaults)


def _is_synthetic_init(sig: FuncSig) -> bool:
    """Check if a signature is PyO3's synthetic *args/**kwargs placeholder."""
    return set(sig.params) == {"self", "*args", "**kwargs"} or set(sig.params) == {"*args", "**kwargs"}

def compare_signatures(
    pyi_sigs: dict[str, FuncSig],
    rt_sigs: dict[str, FuncSig],
) -> list[str]:
    diffs: list[str] = []
    all_keys = set(pyi_sigs) | set(rt_sigs)

    for key in sorted(all_keys):
        if key in SKIP_RUNTIME_ONLY:
            continue
        if key not in rt_sigs:
            diffs.append(f"  {key}: in .pyi but not in runtime")
            continue
        if key not in pyi_sigs:
            # For dunder methods with synthetic *args/**kwargs signatures,
            # .pyi may legitimately omit them (e.g. classes constructed via
            # factory functions). Skip existence check for SKIP_DUNDER.
            method_name = key.split(".")[-1] if "." in key else key
            rt_sig = rt_sigs[key]
            if method_name in SKIP_DUNDER and _is_synthetic_init(rt_sig):
                continue
            diffs.append(f"  {key}: in runtime but not in .pyi")
            continue

        # For dunder methods, only check existence (skip param comparison)
        method_name = key.split(".")[-1] if "." in key else key
        if method_name in SKIP_DUNDER:
            continue

        pyi_sig = pyi_sigs[key]
        rt_sig = rt_sigs[key]

        if pyi_sig.params != rt_sig.params:
            diffs.append(
                f"  {key}: param mismatch\n"
                f"    .pyi:     {pyi_sig.params}\n"
                f"    runtime:  {rt_sig.params}"
            )
        elif pyi_sig.defaults != rt_sig.defaults:
            diffs.append(
                f"  {key}: default mismatch\n"
                f"    .pyi defaults:     {pyi_sig.defaults}\n"
                f"    runtime defaults: {rt_sig.defaults}"
            )

    return diffs


def main() -> int:
    """Run full stub verification. Returns 0 if OK, 1 if drift."""
    pyi_sigs = _parse_pyi_from_string(PYI_PATH.read_text())
    rt_sigs = introspect_runtime_signatures()
    diffs = compare_signatures(pyi_sigs, rt_sigs)

    if diffs:
        print(f"Stub drift detected ({len(diffs)} difference(s)):\n")
        for d in diffs:
            print(d)
        return 1

    print(f"OK — {len(pyi_sigs)} signatures verified, no drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
