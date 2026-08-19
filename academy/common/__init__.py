"""Shared contracts used by every Academy lab."""

from .live import run_live_example
from .trace import load_trace, render_trace, validate_trace

__all__ = ["load_trace", "render_trace", "run_live_example", "validate_trace"]
