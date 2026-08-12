"""14 — Rules-Based Approval: RuleChain + approval hook.

Mirrors runtime `14_rules_approval.rs`. Demonstrates declarative, pre-execution
tool-call gating via `senza.rules` (RuleChain of (tool_name, predicate, decision)
rules turned into a BeforeToolCallHook with `senza.rules.approval_hook`). The
first matching rule wins; `fallback` decides when nothing matches. A denied tool
call is never executed — the callback never fires and the LLM sees a failure.

Predicates covered:
  - contains(allowed)         tool_name in `allowed` list
  - regex_field(path, pat)    args[path] matches the regex
  - number_range(path,lo,hi)  args[path] within [lo, hi]
  - rate_limit(max, window)   at most `max` calls per `window` seconds

Three policies, as in the runtime example:
  Part 1  Allowlist  -> only `echo` allowed, fallback Deny (write_file denied)
  Part 2  Denylist   -> `dangerous_tool` denied, everything else allowed
  Part 3  RateLimit  -> `echo` allowed at most 2x / 60s, fallback Deny

Run:
  source ~/.omp_llm_env && python live-tests/examples/14_rules_approval.py
"""

import json

import senza
from _common import make_example_harness, run_prompt, text_of

# Callback-execution counters: a denied call never reaches its callback, so a
# tool that was "attempted" (tool_call_start) but whose counter stayed put was
# denied before execution.
EXECUTED = {"echo": 0, "write_file": 0, "dangerous_tool": 0}


def _exec(name):
    def cb(args, ctx):
        EXECUTED[name] += 1
        extra = {n: args.get(n, "?") for n in args}
        return {
            "content": [{"type": "text", "text": f"{name} executed {extra}"}],
            "terminate": False,
        }

    return cb


def _schema(props, required):
    return json.dumps({"type": "object", "properties": props, "required": required})


def build_tools():
    tools = {
        "echo": senza.create_tool(
            name="echo",
            description="Echo back the provided message verbatim.",
            parameters_schema=_schema(
                {"message": {"type": "string", "description": "Message to echo"}},
                ["message"],
            ),
            callback=_exec("echo"),
        ),
        "write_file": senza.create_tool(
            name="write_file",
            description="Write content to a file at the given path.",
            parameters_schema=_schema(
                {
                    "path": {"type": "string", "description": "Path to write to"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                ["path", "content"],
            ),
            callback=_exec("write_file"),
        ),
        "dangerous_tool": senza.create_tool(
            name="dangerous_tool",
            description="A dangerous tool performing irreversible operations. "
            "Should be denied by policy.",
            parameters_schema=_schema(
                {"action": {"type": "string", "description": "Dangerous action"}},
                ["action"],
            ),
            callback=_exec("dangerous_tool"),
        ),
    }
    return tools


def attempts_and_text(events):
    """Return (attempted [tool names in tool_call_start], final text)."""
    attempted = [
        e.get("tool_name")
        for e in events
        if e.get("type") in ("tool_call_start", "tool_execution_start")
    ]
    return attempted, text_of(events).strip()


def part1_allowlist(tools):
    print("--- Part 1: Allowlist (only `echo` allowed, fallback Deny) ---\n")
    chain = (
        senza.rules.chain()
        .rule("*", senza.rules.contains(["echo"]), "allow")
        .fallback("deny")
        .build()
    )
    harness = make_example_harness(
        lambda b: (
            b.system_prompt(
                "Use the echo tool to answer. Also try the write_file tool. "
                "If a tool is denied, report that."
            )
            .tool(tools["echo"])
            .tool(tools["write_file"])
            .hooks([senza.rules.approval_hook(chain)])
        )
    )
    events = run_prompt(
        harness,
        "Use echo with message 'hello rules'. Then use write_file to write 'test' to '/tmp/x.txt'.",
        timeout_ms=60_000,
    )
    attempted, text = attempts_and_text(events)
    print(f"Tools attempted: {attempted}")
    print(f"echo executed:   {EXECUTED['echo']}")
    print(f"write_file executed: {EXECUTED['write_file']}")
    print(f"Final text: {text[:180]}")
    ok = EXECUTED["echo"] >= 1 and EXECUTED["write_file"] == 0
    print(f"Allowlist enforced (echo ran, write_file denied): {ok}\n")


def part2_denylist(tools):
    print("--- Part 2: Denylist (`dangerous_tool` denied, fallback Allow) ---\n")
    # Deny rule must come BEFORE the wildcard allow, else the wildcard wins.
    chain = (
        senza.rules.chain()
        .rule(
            "dangerous_tool",
            senza.rules.contains(["dangerous_tool"]),
            "deny",
        )
        .rule("*", senza.rules.contains(["echo", "dangerous_tool"]), "allow")
        .fallback("allow")
        .build()
    )
    harness = make_example_harness(
        lambda b: (
            b.system_prompt(
                "Use the echo tool to answer, and try the dangerous_tool too. "
                "If a tool is denied, report that."
            )
            .tool(tools["echo"])
            .tool(tools["dangerous_tool"])
            .hooks([senza.rules.approval_hook(chain)])
        )
    )
    events = run_prompt(
        harness,
        "First try dangerous_tool with action 'delete-everything'. Then echo 'safe echo'.",
        timeout_ms=60_000,
    )
    attempted, text = attempts_and_text(events)
    print(f"Tools attempted: {attempted}")
    print(f"echo executed:           {EXECUTED['echo']}")
    print(f"dangerous_tool executed: {EXECUTED['dangerous_tool']}")
    print(f"Final text: {text[:180]}")
    ok = EXECUTED["dangerous_tool"] == 0
    print(f"Denylist enforced (dangerous_tool denied): {ok}\n")


def part3_rate_limit(tools):
    print("--- Part 3: RateLimit (echo: max 2 calls / 60s, fallback Deny) ---\n")
    chain = (
        senza.rules.chain()
        .rule("*", senza.rules.rate_limit(2, 60), "allow")
        .fallback("deny")
        .build()
    )
    harness = make_example_harness(
        lambda b: (
            b.system_prompt(
                "Call the echo tool as many times as requested. If a call is "
                "rate-limited, report that."
            )
            .tool(tools["echo"])
            .hooks([senza.rules.approval_hook(chain)])
        )
    )
    events = run_prompt(
        harness,
        "Call the echo tool three times with these messages: 'first', 'second', 'third'.",
        timeout_ms=90_000,
    )
    attempted, text = attempts_and_text(events)
    print(f"Tools attempted (in order): {attempted}")
    print(f"echo executed: {EXECUTED['echo']}")
    print(f"Final text: {text[:200]}")
    ok = EXECUTED["echo"] <= 2
    print(f"RateLimit enforced (<= 2 echo executions succeeded): {ok}")


def main() -> None:
    print("=== 14: Rules-Based Approval ===\n")
    tools = build_tools()
    part1_allowlist(tools)
    part2_denylist(tools)
    part3_rate_limit(tools)
    print("\n--- Summary ---")
    print("Allowlist (fallback Deny):  echo allowed, write_file denied")
    print("Denylist (fallback Allow):  dangerous_tool denied, echo allowed")
    print("RateLimit (max 2 / 60s):    3rd echo call denied")


if __name__ == "__main__":
    main()
