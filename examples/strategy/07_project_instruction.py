"""07 — Project Instruction Plugin.

Demonstrates:
  - ProjectInstructionPlugin: injects CLAUDE.md / AGENTS.md into system prompt
  - Reads instruction files from the execution environment's working directory

ProjectInstructionPlugin scans the working directory for convention files
(CLAUDE.md, AGENTS.md, .cursorrules) and prepends their content to the system
prompt, ensuring the LLM follows project-specific coding standards.
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.create_openai_provider(api_key=api_key)

    working_dir = os.getcwd()
    env = senza.create_os_env(working_dir)

    config = {
        "files": ["CLAUDE.md", "AGENTS.md"],
        "max_bytes": 8192,
    }
    plugin = senza.create_project_instruction_plugin(env=env, config=config)

    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .system_prompt("You are a coding assistant.")
        .plugin(plugin)
        .env(env)
        .build()
    )

    print(f"ProjectInstructionPlugin scanning: {working_dir}")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
