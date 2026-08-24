"""Deterministic coding-loop replay used by the provider-free lesson."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


FIXTURE_PROJECT = Path(__file__).resolve().parent / "fixtures" / "project"
BUGGY_LINE = "    return left - right\n"
FIXED_LINE = "    return left + right\n"


def evaluate_command(command: str) -> dict[str, Any]:
    """Return a teaching decision without ever executing the command."""

    normalized = " ".join(command.lower().split())
    destructive_fragments = (
        "rm -rf /",
        "remove-item -recurse c:\\",
        "format c:",
        "del /s /q c:\\",
    )
    matched = next((item for item in destructive_fragments if item in normalized), None)
    if matched:
        return {
            "action": "deny",
            "reason": f"destructive command pattern: {matched}",
            "executed": False,
        }
    return {"action": "allow", "reason": "no teaching deny rule matched", "executed": False}


def _run_tests(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "calculator_spec.py", "-q"],
        cwd=project,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )


def _apply_minimal_fix(project: Path) -> None:
    target = project / "calculator.py"
    source = target.read_text(encoding="utf-8")
    if source.count(BUGGY_LINE) != 1:
        raise RuntimeError("fixture no longer contains exactly one expected bug")
    target.write_text(source.replace(BUGGY_LINE, FIXED_LINE, 1), encoding="utf-8")


def run_scenario() -> dict[str, Any]:
    """Copy the fixture, reproduce the bug, patch one line, and re-run tests."""

    with tempfile.TemporaryDirectory(prefix="senza-academy-coding-") as tmp:
        project = Path(tmp) / "project"
        shutil.copytree(FIXTURE_PROJECT, project)

        before = _run_tests(project)
        _apply_minimal_fix(project)
        after = _run_tests(project)
        denied = evaluate_command("rm -rf /")

        return {
            "before_returncode": before.returncode,
            "before_output": (before.stdout + before.stderr).strip(),
            "after_returncode": after.returncode,
            "after_output": (after.stdout + after.stderr).strip(),
            "changed_line": "return left - right  ->  return left + right",
            "dangerous_command": denied,
        }
