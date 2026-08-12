"""12 — Context-Aware Compaction Prompt.

Demonstrates:
  - create_context_aware_compaction_prompt: returns (system, user_template)
  - Smarter compaction that preserves key entities and decisions

Standard compaction summarises the context window blindly. The context-aware
variant generates a system prompt and user template that instruct the
compaction model to preserve named entities, user decisions, and open tasks
while discarding boilerplate.
"""

import os

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.create_openai_provider(api_key=api_key)
    env = senza.create_os_env(".")

    system_prompt, user_template = senza.create_context_aware_compaction_prompt()

    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .auto_compact(True)
        .compaction_prompt(
            system_prompt=system_prompt,
            user_template=user_template,
        )
        .env(env)
        .build()
    )

    print("Context-aware compaction prompt installed on harness.")
    print(f"  system prompt length:   {len(system_prompt)} chars")
    print(f"  user template length:   {len(user_template)} chars")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
