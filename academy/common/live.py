"""Compatibility bridge for historical Academy live-example filenames."""

from __future__ import annotations

from .catalog import run_legacy_live_example


def run_live_example(filename: str) -> None:
    """Run an old filename through ``python -m examples run``.

    The signature stays compatible with the original Academy helper. Provider
    preflight, including the no-key structured skip, now belongs to the unified
    runner rather than an in-process ``runpy`` execution.
    """

    run_legacy_live_example(filename)
