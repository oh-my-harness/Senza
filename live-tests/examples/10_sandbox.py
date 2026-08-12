"""10 — Sandbox / OS env: run a harness inside an OS execution environment.

Mirrors runtime `10_sandbox.rs`. Senza's `seatbelt_sandbox` (macOS) is a stub
whose `start()` raises "not yet implemented" — a known feature gap. The working
equivalent is `create_os_env`, which provides an ExecutionEnv that a harness's
tools execute inside. Demonstrates:
  - create_os_env: a real OS environment rooted at a working dir
  - Wiring that env onto the harness (builder.env) so tools run inside it
  - A tool call succeeding under that env

Run:
  source ~/.omp_llm_env && python live-tests/examples/10_sandbox.py
"""

import json
import tempfile

import senza
from _common import make_example_harness, run_prompt, text_of


def echo(args, ctx):
    return {
        "content": [{"type": "text", "text": f"echo:{args.get('msg', '')}"}],
        "terminate": False,
    }


def main() -> None:
    print("=== 10: Sandbox / OS env ===\n")
    # Feature-gap note: seatbelt sandbox is a stub.
    if hasattr(senza.infra, "seatbelt_sandbox"):
        sb = senza.infra.seatbelt_sandbox()
        try:
            sb.start()
        except RuntimeError as e:
            print(f"[gap] seatbelt_sandbox.start(): {e}")
    else:
        print("[gap] no seatbelt_sandbox on this platform")

    workdir = tempfile.mkdtemp(prefix="senza_env_")
    env = senza.create_os_env(working_dir=workdir)
    tool = senza.create_tool(
        name="echo",
        description="Echo a message back verbatim",
        parameters_schema=json.dumps(
            {"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]}
        ),
        callback=echo,
    )
    harness = make_example_harness(
        lambda b: b.env(env).system_prompt("Use the echo tool to respond.").tool(tool)
    )
    events = run_prompt(harness, "Echo the word sandbox and say where you run.", timeout_ms=60_000)
    tools_used = {e.get("tool_name") for e in events if e["type"] == "tool_call_start"}
    print(f"Tools called: {sorted(tools_used)}")
    print(f"Response: {text_of(events).strip()[:120]}")
    print(f"Working dir env: {workdir}")


if __name__ == "__main__":
    main()
