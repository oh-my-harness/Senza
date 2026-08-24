"""48 — Web / Code Tools: web_search + web_fetch + code_exec.

Demonstrates senza.create_web_tools_plugin() (which bundles web_search and
web_fetch) and senza.create_code_exec_tool(). The agent is asked to:
  1. Search the web for a fact
  2. Fetch a URL for details
  3. Run Python code to compute something

Events are streamed live — text deltas are printed as they arrive, and tool
call names are announced when they start.

Run:
  source ~/.omp_llm_env && python live-tests/examples/48_web_code_tools.py
"""

import asyncio
import os
import sys

import senza
from _common import make_example_harness


async def main() -> None:
    print("=== 48: Web / Code Tools (web_search + web_fetch + code_exec) ===\n")

    if not os.environ.get("OPENAI_API_KEY"):
        print("SKIP: OPENAI_API_KEY not set.")
        sys.exit(0)

    # Web search config: prefer Tavily if API key is set, else fall back to
    # DuckDuckGo (the default provider).
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if tavily_key:
        web_config = {
            "provider": "tavily",
            "base_url": "https://api.tavily.com/search",
            "api_key": tavily_key,
            "max_results": 5,
            "fetch_timeout_secs": 15,
            "max_fetch_chars": 12000,
        }
        print(f"Web search: Tavily (key=...{tavily_key[-4:]})")
    else:
        web_config = None
        print("Web search: DuckDuckGo (set TAVILY_API_KEY for Tavily)")

    harness = make_example_harness(
        lambda b: (
            b.plugin(senza.create_web_tools_plugin(web_config))
            .tool(senza.create_code_exec_tool(timeout_secs=20))
            .env(senza.create_os_env(os.getcwd()))
            .system_prompt(
                "You are a research assistant with web_search, web_fetch, and "
                "code_exec tools. When asked a factual question, search the web "
                "to find current information, fetch relevant pages for detail, "
                "and use code_exec to compute or verify answers. Always cite "
                "your sources."
            )
            .max_tokens(1024)
        )
    )

    prompt = (
        "What is the current population of Tokyo? "
        "Search the web, then fetch a source to confirm. "
        "Finally, use code_exec to calculate the population density "
        "(population / area in km²) of Tokyo."
    )
    print(f'Prompt: "{prompt}"\n')
    print("--- Streaming ---\n")

    tool_names: set[str] = set()
    async for event in senza.stream_prompt(harness, prompt, timeout_ms=120_000):
        etype = event.get("type")
        if etype == "text_delta":
            print(event.get("text", ""), end="", flush=True)
        elif etype == "tool_call_start":
            name = event.get("tool_name", "?")
            tool_names.add(name)
            print(f"\n  [tool: {name}]", flush=True)
        elif etype in ("settled", "aborted", "error"):
            if etype == "error":
                print(f"\n  [ERROR] {event.get('error', '?')}")
            break

    print("\n\n--- Summary ---")
    print(f"Tools used: {sorted(tool_names)}")
    usage = harness.usage()
    cost = harness.usage_ledger()
    print(
        f"Tokens: {usage['total_input_tokens']} in / "
        f"{usage['total_output_tokens']} out"
    )
    if cost:
        print(f"Cost: {cost}")


if __name__ == "__main__":
    asyncio.run(main())
