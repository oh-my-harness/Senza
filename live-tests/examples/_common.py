# ruff: noqa: I001  (sys.path bootstrap forces base import order)

"""Shared helpers for Senza live-LLM runnable examples.

Mirrors `llm-harness-runtime/.../llm-harness-live-tests/examples/` — these are
human-observable, weakly-asserted runnable demos (the strict behavioural checks
live in the layer test files one level up).

Every example is a standalone script you run directly:

    source ~/.omp_llm_env && python live-tests/examples/01_prompt_streaming.py

Without a key the script prints a clear message and exits 0 (no crash), matching
the tests' "skip without a key" behaviour.
"""

import os
import sys

# Make `base` (the shared test helpers) importable from this subdirectory.
_LIVE_TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIVE_TESTS not in sys.path:
    sys.path.insert(0, _LIVE_TESTS)

from base import (  # noqa: E402  (after sys.path bootstrap)
    MULTI_TURN_TIMEOUT_MS as MULTI_TURN_TIMEOUT_MS,
    SINGLE_TURN_TIMEOUT_MS as SINGLE_TURN_TIMEOUT_MS,
    SMOKE_TIMEOUT_MS as SMOKE_TIMEOUT_MS,
    live_model as live_model,
    make_harness as make_harness,
    providers_from_env as providers_from_env,
    run_prompt as run_prompt,
    text_of as text_of,
    with_timeout as with_timeout,
)


def require_provider():
    """Return the first configured provider, or print a skip notice and exit 0."""
    entries = providers_from_env()
    if not entries:
        print("SKIP: no LLM provider configured (set OPENAI_API_KEY / ANTHROPIC_API_KEY).")
        sys.exit(0)
    name, provider = entries[0]
    print(f"Provider: {name} | Model: {live_model()}")
    return provider


def make_example_harness(customize=None):
    """Build an AgentHarness bound to a real provider (optionally customized)."""
    return make_harness(require_provider(), customize)
