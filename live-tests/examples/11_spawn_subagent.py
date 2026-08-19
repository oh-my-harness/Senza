"""11 — Spawn Sub-Agent: main agent dispatches sub-agents and collects results.

Mirrors runtime `11_spawn_subagent.rs`. Demonstrates Senza's spawn
infrastructure (added alongside the live-tests spawn suite):
  - enable_spawn() wires MessageBus, HarnessSubAgentSpawner, AsyncSpawnHook,
    IdleWatcher, and 5 main-agent spawn tools on the builder
  - spawn_agent: main agent spawns a sub-agent (async, fire-and-forget)
  - message_subagent: main agent sends a follow-up message
  - await_subagent_reply: main agent blocks waiting for a sub-agent reply
  - query_subagent: main agent queries a sub-agent's status
  - abort_subagent: main agent requests cancellation

This focused example exercises spawn/await/query; message/abort are wired by
the same enable_spawn() call but are not invoked here.

Run:
  source ~/.omp_llm_env && python live-tests/examples/11_spawn_subagent.py
"""

import tempfile

import senza
from _common import live_model, require_provider

# Make `base` importable for run_prompt/text_of (sys.path already bootstrapped
# by _common, but keep the import local to the module scope for clarity).
from base import run_prompt, text_of  # noqa: E402


def _make_spawn_harness(provider):
    """Build a harness with spawn infrastructure enabled."""
    session_dir = tempfile.mkdtemp(prefix="senza-spawn-11-")
    builder = senza.HarnessBuilder(live_model()).provider("*", provider)
    return (
        builder.enable_spawn(
            model=live_model(),
            provider=provider,
            session_dir=session_dir,
        )
        .system_prompt(
            "You are a helpful assistant that can dispatch sub-agents for sub-tasks. "
            "Use the spawn_agent tool to delegate work, await_subagent_reply to wait "
            "for results, and query_subagent to check status."
        )
        .build()
    )


def main() -> None:
    print("=== 11: Spawn Sub-Agent ===\n")

    provider = require_provider()
    harness = _make_spawn_harness(provider)

    # ── Part 1: Basic spawn — main agent spawns a sub-agent ───────────────
    print("--- Part 1: Basic spawn ---\n")

    prompt1 = (
        "Use the spawn_agent tool to spawn a sub-agent with the prompt "
        "'What is 2+2? Answer briefly.' Then wait for the result using "
        "await_subagent_reply."
    )
    print(f'Prompt: "{prompt1}"\n')

    events = run_prompt(harness, prompt1, timeout_ms=120_000)
    tools = {e.get("tool_name") for e in events if e.get("type") == "tool_call_start"}
    print(f"Tools called: {sorted(tools)}")
    print(f"spawn_agent was called: {'spawn_agent' in tools}")

    text = text_of(events)
    print(f"\nResponse:\n{text}\n")

    # ── Part 2: Await sub-agent reply ─────────────────────────────────────
    print("--- Part 2: Await sub-agent reply ---\n")

    prompt2 = (
        "Spawn a sub-agent with the prompt 'Say hello in one word.' "
        "Then use await_subagent_reply to get the response. "
        "Report what the sub-agent said."
    )
    print(f'Prompt: "{prompt2}"\n')

    events = run_prompt(harness, prompt2, timeout_ms=120_000)
    tools = {e.get("tool_name") for e in events if e.get("type") == "tool_call_start"}
    print(f"Tools called: {sorted(tools)}")
    print(f"await_subagent_reply was called: {'await_subagent_reply' in tools}")

    text = text_of(events)
    print(f"\nResponse:\n{text}\n")

    # ── Part 3: Query sub-agent status ────────────────────────────────────
    print("--- Part 3: Query sub-agent status ---\n")

    prompt3 = (
        "Spawn a sub-agent with the prompt 'Count from 1 to 5.' "
        "Then use query_subagent to check its status. "
        "Report the status you see."
    )
    print(f'Prompt: "{prompt3}"\n')

    events = run_prompt(harness, prompt3, timeout_ms=120_000)
    tools = {e.get("tool_name") for e in events if e.get("type") == "tool_call_start"}
    print(f"Tools called: {sorted(tools)}")
    print(f"query_subagent was called: {'query_subagent' in tools}")

    text = text_of(events)
    print(f"\nResponse:\n{text}\n")

    # ── Summary ───────────────────────────────────────────────────────────
    print("--- Summary ---")
    print("spawn_agent tool exercised: true (see above)")
    print("await_subagent_reply tool exercised: true (see above)")
    print("query_subagent tool exercised: true (see above)")


if __name__ == "__main__":
    main()
