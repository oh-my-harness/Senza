"""16 — MCP (Model Context Protocol): connect external tool servers.

Demonstrates:
  - McpServerConfig.stdio() to launch a stdio MCP server
  - HarnessBuilder.mcp_server() to attach it to an agent
  - Agent discovers and calls MCP-provided tools (get_scene_info, execute_blender_code)
  - McpManager for lifecycle inspection (status, list_tools, disconnect)

This example uses blender-mcp (https://github.com/ahujasid/blender-mcp) as a
real MCP server. The architecture:

    Senza agent ──stdio──▶ blender-mcp server ──TCP 9876──▶ Blender addon

Prerequisites:
  - Blender running with the blender-mcp addon installed and connected
    (Edit ▸ Preferences ▸ Add-ons ▸ Install from Disk ▸ addon.py,
     then N-panel ▸ BlenderMCP ▸ Connect to Claude)
  - uvx on PATH  (pip install uv)
  - OPENAI_API_KEY / OPENAI_API_BASE / OPENAI_MODEL set

Run:
  python 16_mcp_blender.py
"""

import os
import sys

import senza

SCENE_PROMPT = """\
Create a cozy desk scene in Blender:

1. Clear the default scene (delete all objects)
2. A wooden table (brown, 2m x 1m x 0.05m, at z=0)
3. A red coffee mug (cylinder, 0.08m radius x 0.1m height, on the table)
4. A blue book (cube, 0.2m x 0.15m x 0.03m, on the table)
5. A green potted plant (cone on a cylinder pot, on the table)
6. A warm point light (z=2m, warm white, 100W)
7. A camera angled at the desk

Use execute_blender_code for each object. After creating everything,
call get_scene_info to verify.
"""


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    model = os.environ.get("SENZA_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-4o")

    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

    # ── 1. MCP lifecycle check (no LLM needed) ──────────────────────────
    manager = senza.McpManager()
    manager.add_server(
        "blender",
        senza.McpServerConfig.stdio(command="uvx", args=["blender-mcp"]),
    )

    tools = manager.list_tools()
    print(f"MCP server connected: {len(tools)} tools discovered")
    for t in tools:
        print(f"  - {t}")

    manager.disconnect_all()
    print()

    # ── 2. Build agent with MCP tools ───────────────────────────────────
    harness = (
        senza.HarnessBuilder(model)
        .provider("*", provider)
        .system_prompt(
            "You are a 3D scene assistant for Blender. "
            "You MUST call the execute_blender_code tool to run bpy Python code — "
            "never write code as text. "
            "Always check the scene with get_scene_info first."
        )
        .max_tokens(8192)
        .mcp_server(
            "blender",
            senza.McpServerConfig.stdio(command="uvx", args=["blender-mcp"]),
        )
        .build()
    )

    print("Prompting agent to build a desk scene...")
    events = harness.prompt_and_collect(SCENE_PROMPT, timeout_ms=300_000)

    # ── 3. Extract results ──────────────────────────────────────────────
    text = ""
    tool_calls = []
    for event in events:
        t = event["type"]
        if t == "text_delta":
            text += event.get("text", "")
        elif t == "tool_call_start":
            tool_calls.append(event.get("tool_name", "?"))
        elif t == "tool_execution_end":
            result = event.get("result", {})
            preview = str(result.get("text", ""))[:80]
            tool_calls.append(f"  → {preview}")
        elif t == "error":
            print(f"\n[error] {event.get('message', event)}", file=sys.stderr)

    print(f"\nTool calls ({len(tool_calls)}):")
    for tc in tool_calls:
        print(f"  {tc}")

    print(f"\nAgent response:\n{text}")

    cost = harness.usage()
    print(f"\nTokens: {cost['total_input_tokens']} in / {cost['total_output_tokens']} out")

    harness.shutdown()


if __name__ == "__main__":
    main()
