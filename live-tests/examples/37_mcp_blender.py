"""37 — MCP (Model Context Protocol): connect external tool servers.

Mirrors `examples/agent/16_mcp_blender.py`. Demonstrates Senza's MCP client
surface — the API exists and is verified against `senza/__init__.pyi`:
  - McpServerConfig.stdio() / .http() / .sse() to describe a server
  - HarnessBuilder.mcp_server() to attach a server to an agent (promoted to an
    McpAgentHarness at build time)
  - McpManager for lifecycle inspection (get_status, list_tools, disconnect)

Feature gap (external dependency): the reference example drives a real
blender-mcp server (`uvx blender-mcp`) that must be connected to a running
Blender addon over TCP 9876. That live server is not available in this
environment and `McpManager.add_server()` / `build()` eagerly spawn it, so
the full tool-calling turn is skipped. This example shows the wiring and the
non-connecting lifecycle inspection instead (no build = no server spawn).

Run:
  source ~/.omp_llm_env && python live-tests/examples/37_mcp_blender.py
"""

import senza
from _common import live_model, require_provider


def main() -> None:
    print("=== 37: MCP Blender (wiring + lifecycle; live server is a gap) ===\n")
    require_provider()

    # ── 1. MCP server configuration (pure construction) ─────────────────
    blender = senza.McpServerConfig.stdio(command="uvx", args=["blender-mcp"])
    files = senza.McpServerConfig.http(url="https://example.com/mcp")
    print("Configs:")
    print(f"  {blender}")
    print(f"  {files}")

    # ── 2. McpManager lifecycle inspection (non-connecting) ─────────────
    manager = senza.McpManager()
    print(f"\nstatus('blender', never added): {manager.get_status('blender')}")
    print(f"errors: {manager.errors()}")
    print(f"list_tools (no server connected): {manager.list_tools()}")
    manager.disconnect_all()

    # ── 3. Wire an MCP server onto an agent builder (no build = no spawn) ─
    builder = (
        senza.HarnessBuilder(live_model())
        .system_prompt(
            "You are a 3D scene assistant for Blender. You MUST call the "
            "execute_blender_code tool to run bpy Python code — never write "
            "code as text. Always check the scene with get_scene_info first."
        )
        .max_tokens(2048)
        .mcp_server("blender", blender)
    )
    print(f"\nBuilder records the MCP server without connecting:\n  {builder!r}")

    print(
        "\n[gap] The live tool-calling turn (SCENE_PROMPT to create a desk "
        "scene via blender-mcp) is skipped: it requires a running Blender "
        "with the blender-mcp addon installed and connected, plus uvx on "
        "PATH — none of which are available here. The API surface above is "
        "the runnable subset."
    )


if __name__ == "__main__":
    main()
