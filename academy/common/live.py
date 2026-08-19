"""Bridge Academy lessons to the canonical live-tests examples."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def run_live_example(filename: str) -> None:
    """Execute a canonical live example without duplicating its implementation."""

    if Path(filename).name != filename or not filename.endswith(".py"):
        raise ValueError("live example must be a plain .py filename")

    repository_root = Path(__file__).resolve().parents[2]
    examples_dir = repository_root / "live-tests" / "examples"
    example_path = examples_dir / filename
    if not example_path.is_file():
        raise FileNotFoundError(f"canonical live example not found: {example_path}")

    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(examples_dir))
        runpy.run_path(str(example_path), run_name="__main__")
    finally:
        sys.path[:] = previous_path
