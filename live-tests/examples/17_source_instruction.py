"""17 — Source Instruction: SourceTagPlugin + ProjectInstructionPlugin.

Mirrors runtime `17_source_instruction.rs`. Demonstrates two strategy plugins:
  - source_tag([...]): wraps selected tool results in
    <external_content source="label">...</external_content> XML tags, so
    downstream defenses can tell external tool output from trusted text.
  - project_instruction(env, config): scans for CLAUDE.md / AGENTS.md /
    .cursorrules / SOUL.md in env.working_dir() and parents, then appends the
    merged content to the system prompt before each LLM call.
Both are attached to the same harness; the prompt exercises an external-source
tool so you can observe the injected instruction steering the model's reply.

Run:
  source ~/.omp_llm_env && python live-tests/examples/17_source_instruction.py
"""

import json
import tempfile
from pathlib import Path

import senza
from _common import make_example_harness, run_prompt, text_of


def lookup(args, ctx):
    """A stand-in for an external data source (web doc, file, etc.)."""
    return {
        "content": [{"type": "text", "text": "Company reported 2026 revenue of $1.2B."}],
        "terminate": False,
    }


def main() -> None:
    print("=== 17: Source Instruction ===\n")

    # ProjectInstructionPlugin reads project-instruction files out of the env's
    # working dir, so we build a temp dir, drop a CLAUDE.md there, then root the
    # env at it. The plugin needs the env at construction time.
    workdir = tempfile.mkdtemp(prefix="senza_proj_")
    Path(workdir, "CLAUDE.md").write_text(
        "# Project Instructions\n\n"
        "- Always respond in a friendly tone.\n"
        "- When you use the lookup tool, mention the data came from an external source.\n"
        "- End every response with the phrase: 'Project instructions applied.'\n",
        encoding="utf-8",
    )
    env = senza.create_os_env(working_dir=workdir)

    # A tool that returns external content; tag it so its output gets wrapped.
    lookup_tool = senza.create_tool(
        name="lookup",
        description="Fetch an external fact",
        parameters_schema=json.dumps(
            {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}
        ),
        callback=lookup,
    )

    source_tag = senza.strategy.source_tag([{"tool": "lookup", "label": "external-docs"}])
    proj_instruction = senza.strategy.project_instruction(env)

    harness = make_example_harness(
        lambda b: (
            b.env(env)
            .system_prompt("Answer using the lookup tool when you need an external fact.")
            .tool(lookup_tool)
            .plugin(source_tag)
            .plugin(proj_instruction)
        )
    )

    prompt = (
        "Use the lookup tool to find the company's 2026 revenue, then restate it in your reply."
    )
    print(f'Prompt: "{prompt}"\n')
    events = run_prompt(harness, prompt, timeout_ms=60_000)

    tools_used = sorted({e.get("tool_name") for e in events if e["type"] == "tool_call_start"})
    print(f"Tools called: {tools_used}")

    # SourceTagPlugin wraps lookup's result in <external_content source="...">.
    tagged = any(
        "external-docs" in (e.get("text") or "") for e in events if e["type"] == "tool_call_end"
    )
    print(f"External tool output source-tagged: {tagged}")

    response = text_of(events).strip()
    print(f"\nResponse: {response[:300]}")

    injected = "Project instructions applied." in response
    print(f"\nProject instruction reflected in response: {injected}")


if __name__ == "__main__":
    main()
