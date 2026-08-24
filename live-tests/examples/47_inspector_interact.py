"""47 — Inspector Interactive: human-in-the-loop via Web UI.

Demonstrates the Inspector's interactive endpoints for multi-turn human-agent
collaboration:

  1. Mount Inspector on a port — opens a Web UI at http://localhost:PORT
  2. Start a task via `harness.prompt()` (or POST /api/prompt from the browser)
  3. While the agent works, the user can:
     - POST /api/inject — inject a steering message into the running agent
     - POST /api/abort — cancel the current turn
     - GET /api/agent/usage — check token/cost in real time
     - GET /api/agent/skills — list available skills
  4. WebSocket /api/events streams all agent events live in the browser
  5. When the agent settles, start a new task from the browser

The script stays alive for 5 minutes (or until Ctrl+C), giving you time to
open the browser and interact.

Run:
  source ~/.omp_llm_env && python live-tests/examples/47_inspector_interact.py

Then open http://localhost:8080 in your browser.
"""

import asyncio
import os
import sys

import senza
from _common import make_example_harness


async def main() -> None:
    print("=== 47: Inspector Interactive (human-in-the-loop via Web UI) ===\n")

    if not os.environ.get("OPENAI_API_KEY"):
        print("SKIP: OPENAI_API_KEY not set.")
        sys.exit(0)

    harness = make_example_harness(
        lambda b: (
            b.plugin(senza.create_fs_tools_plugin())
            .plugin(senza.create_web_tools_plugin())
            .tool(senza.create_code_exec_tool(timeout_secs=20))
            .env(senza.create_os_env(os.getcwd()))
            .system_prompt(
                "You are a helpful coding assistant. You can read/write files, "
                "search the web, and execute code. When the user asks you to "
                "do something, use your tools to actually do it. "
                "Be concise in your explanations.\n\n"
                "IMPORTANT: Output only the final result directly. "
                "Do not show your internal reasoning process, "
                "trial-and-error attempts, or step-by-step analysis. "
                "If you need to try multiple approaches, do so silently "
                "and only present the final answer."
            )
            .max_tokens(2048)
        )
    )

    # ── Mount Inspector ─────────────────────────────────────────────────
    port = int(os.environ.get("INSPECTOR_PORT", "8080"))
    inspector = harness.mount_inspector(port)
    addr = inspector.bound_addr
    url = f"http://{addr}" if addr else f"http://127.0.0.1:{port}"

    print(f"Inspector running at {url}")
    print(f"  → Open this URL in your browser to interact with the agent.")
    print()
    print("Available endpoints:")
    print(f"  GET  {url}/                    — Web UI (event stream + controls)")
    print(f"  GET  {url}/api/agent/config    — Agent configuration")
    print(f"  GET  {url}/api/agent/session   — Session history")
    print(f"  GET  {url}/api/agent/usage     — Token/cost usage")
    print(f"  GET  {url}/api/agent/skills    — Skill list")
    print(f"  GET  {url}/api/events          — WebSocket event stream")
    print(f"  POST {url}/api/inject          — Inject message: {{\"text\": \"...\"}}")
    print(f"  POST {url}/api/abort           — Abort current turn")
    print(f"  POST {url}/api/prompt          — Start new task: {{\"text\": \"...\"}}")
    print()
    print("The Inspector is ready. Open the browser and type a task to begin.")
    print("The server will stay alive for 5 minutes. Press Ctrl+C to stop early.")
    print("-" * 60)

    # ── Wait for user interaction via browser ───────────────────────────
    # The user starts tasks by typing in the Inspector Web UI's
    # "Start new task" input box (POST /api/prompt).
    # We just keep the process alive and stream events as they come.
    print("\nWaiting for tasks from the browser...\n")

    # Stream events from the harness to terminal as they arrive.
    try:
        async for event in senza.stream_events(harness, timeout_ms=300_000):
            etype = event.get("type", "")
            if etype == "text_delta":
                print(event.get("text", ""), end="", flush=True)
            elif etype == "tool_call_start":
                print(f"\n  [tool: {event.get('tool_name', '?')}]", flush=True)
            elif etype in ("settled", "aborted", "error"):
                if etype == "error":
                    print(f"\n  [ERROR] {event.get('error', '?')}")
                else:
                    print(f"\n  [{etype}]")
                print("\nWaiting for next task from browser...\n")
    except asyncio.TimeoutError:
        print("\n\n[timeout — 5 minutes elapsed]")
    except KeyboardInterrupt:
        print("\n\n[interrupted by user]")
    # ── Show final usage ───────────────────────────────────────────────
    usage = harness.usage()
    print(f"\n--- Final Usage ---")
    print(f"  Input tokens:  {usage.get('total_input_tokens', 0)}")
    print(f"  Output tokens: {usage.get('total_output_tokens', 0)}")
    print(f"  Cost:          ${usage.get('total_cost', 0):.4f}")

    # ── Shutdown Inspector ─────────────────────────────────────────────
    print(f"\nShutting down Inspector at {url} ...")
    inspector.shutdown()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
