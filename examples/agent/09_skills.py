"""09 — Skills: load domain knowledge the model can read on demand.

Demonstrates:
  - ``load_skills(path)`` — scan a directory for ``SKILL.md`` files
  - ``HarnessBuilder.skills()`` — attach skills to the harness
  - The auto-registered ``skill_read`` tool the model uses to pull
    detailed content (runbooks, reference files) from a skill's directory
  - ``Skill`` metadata properties: ``name``, ``description``, ``source``,
    ``base_dir``, ``disable_model_invocation``
  - ``HarnessBuilder.disable_skill_read_tool()`` — opt out of the
    auto-registered tool

SKILL.md frontmatter format (YAML, ``---`` delimited):

  ---
  name: my-skill              # lowercase letters/digits/hyphens, <=64 chars
  description: Short summary  # required, <=1024 chars, shown to the model
  label: Human Label          # optional UI label
  disable-model-invocation: true  # optional: hide from system prompt
  ---
  Markdown body — the model sees the description; it must call
  ``skill_read`` to retrieve this body and any referenced sub-files.

Scenario: an incident-response assistant with a ``deploy-rollback`` skill.
The skill body references a ``runbook.md`` sub-file. The model sees the
skill description in its system prompt, then calls ``skill_read`` to fetch
the detailed runbook before answering.

Prerequisites:
  - Set OPENAI_API_KEY env var

Run:
  python 09_skills.py
"""

import os
import sys
import tempfile
import textwrap

import senza


def create_skill_dir(root: str) -> str:
    """Create a ``deploy-rollback`` skill directory under *root*."""
    skill_dir = os.path.join(root, "deploy-rollback")
    os.makedirs(skill_dir, exist_ok=True)

    with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
        f.write(
            textwrap.dedent("""\
            ---
            name: deploy-rollback
            description: Procedures for rolling back a failed production deployment safely.
            label: Production Rollback
            ---

            # Deploy Rollback Skill

            When the user asks about rolling back a deployment, read the
            full runbook via `skill_read` with `skill_name="deploy-rollback"`
            and `path="runbook.md"` before giving instructions.
        """)
        )

    with open(os.path.join(skill_dir, "runbook.md"), "w") as f:
        f.write(
            textwrap.dedent("""\
            # Rollback Runbook

            ## Step 1 — Assess
            - Check the deployment dashboard for the affected service.
            - Identify the last known-good version from the release log.

            ## Step 2 — Execute rollback
            ```bash
            kubectl rollout undo deployment/{service} --to-revision={revision}
            ```

            ## Step 3 — Verify
            - Confirm pods are healthy: `kubectl get pods -l app={service}`
            - Check error rate returns to baseline in the monitoring dashboard.

            ## Step 4 — Post-mortem
            - File an incident report within 24 hours.
            - Tag the bad revision in the artifact registry to prevent re-deploy.
        """)
        )

    return root


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = create_skill_dir(tmpdir)

        # ── Load skills from the directory ────────────────────────────────
        skills = senza.load_skills(skills_dir)
        print(f"Loaded {len(skills)} skill(s):")
        for s in skills:
            print(f"  - name={s.name}")
            print(f"    label={s.label}")
            print(f"    description={s.description}")
            print(f"    source={s.source}")
            print(f"    base_dir={s.base_dir}")
            print(f"    disable_model_invocation={s.disable_model_invocation}")

        # ── Build harness with skills attached ────────────────────────────
        # When skills are present, build() auto-registers a `skill_read`
        # tool so the model can fetch skill content on demand.
        # Use .disable_skill_read_tool() to opt out.
        harness = (
            senza.HarnessBuilder(os.environ.get("SENZA_MODEL", "gpt-4o"))
            .provider("*", provider)
            .system_prompt(
                "You are an incident-response assistant. You have access to "
                "skills. When a skill is relevant, use the skill_read tool to "
                "retrieve its full content before answering."
            )
            .skills(skills)
            .max_tokens(1024)
            .build()
        )

        print("\nPrompting: asking about production rollback...")
        print("(The model should call skill_read to fetch the runbook)\n")

        events = harness.prompt_and_collect(
            "We deployed v2.3 to the checkout service and error rates spiked. How do I roll back?",
            timeout_ms=60000,
        )

        text = ""
        tool_calls = []
        for event in events:
            t = event["type"]
            if t == "text_delta":
                text += event.get("text", "")
            elif t == "tool_call_start":
                tool_calls.append(event.get("tool_name", "?"))
            elif t == "error":
                print(f"\n[error] {event.get('message', event)}", file=sys.stderr)
                sys.exit(1)

        print(f"Tool calls: {tool_calls}")
        if "skill_read" in tool_calls:
            print("[OK] model used skill_read to fetch the runbook")
        else:
            print("[NOTE] model did not call skill_read (may depend on the model's behavior)")
        print(f"\nResponse:\n{text}")

        # ── Inspect conversation messages ─────────────────────────────────
        messages = harness.get_messages()
        print(f"\nSession has {len(messages)} message(s)")


if __name__ == "__main__":
    main()
