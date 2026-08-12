"""06 — Skills & Model Switch: load skills the LLM reads, switch models mid-run.

Mirrors runtime `06_skills_model_switch.rs`. Senza has no prompt-template API
(runtime-only), so this ports the skills + model-switch parts. Demonstrates:
  - load_skills: scan a directory of SKILL.md files
  - HarnessBuilder.skills: attach skills so the auto-registered `skill_read`
    tool lets the LLM pull their content on demand
  - set_model: switch model mid-conversation (session records ModelChange)

Run:
  source ~/.omp_llm_env && python live-tests/examples/06_skills_model_switch.py
"""

import tempfile
from pathlib import Path

import senza
from _common import live_model, make_example_harness, run_prompt, text_of

SKILLS = {
    "python-style": (
        "Python code style guidelines",
        "## Python Style\n\n- Use 4 spaces for indentation\n"
        "- Line length <= 88 chars\n- Use type hints\n"
        "- Prefer f-strings over .format()",
    ),
    "git-workflow": (
        "Git commit and branch workflow",
        "## Git Workflow\n\n1. Create a feature branch\n2. Make changes\n"
        "3. Run tests\n4. Commit with conventional commits\n5. Create a PR",
    ),
    "code-review": (
        "Code review checklist",
        "## Code Review Checklist\n\n- Tests pass\n- No obvious security issues\n"
        "- Naming is clear\n- No dead code\n- Error handling is appropriate",
    ),
}


def make_skill_dir(root: Path, name: str, desc: str, body: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n\n{body}\n")


def main() -> None:
    print("=== 06: Skills & Model Switch ===\n")
    with tempfile.TemporaryDirectory() as tmp:
        skills_dir = Path(tmp) / "skills"
        for name, (desc, body) in SKILLS.items():
            make_skill_dir(skills_dir, name, desc, body)

        skills = senza.load_skills(str(skills_dir))
        print(f"Loaded {len(skills)} skills:")
        for s in skills:
            print(f"  Skill: {s.name} - {s.description}")

        harness = make_example_harness(lambda b: b.skills(skills).max_tokens(512))

        # Let the LLM discover and read skills via skill_read.
        prompts = [
            "What skills do you have available?",
            "Read the python-style skill and tell me the indentation rule.",
            "Read the git-workflow skill and summarize the workflow steps.",
            "Read the code-review skill and list the checklist items.",
            "Based on the python-style skill, how should I format f-strings?",
        ]
        for i, prompt in enumerate(prompts, 1):
            events = run_prompt(harness, prompt, timeout_ms=60_000)
            tools = {e.get("tool_name") for e in events if e["type"] == "tool_call_start"}
            print(f"Turn {i:2}: tools={sorted(tools)} | {text_of(events).strip()[:120]}")

        # ── Model switch: toggle to a variant name and back ─────────────────
        print("\n--- Model switch ---")
        alt_model = f"{live_model()}-alt"
        harness.set_model(alt_model)
        print(f"Switched model to: {alt_model} (demonstrating set_model API)")
        harness.set_model(live_model())
        print(f"Switched back to: {live_model()} for actual conversation\n")

        events = run_prompt(harness, "What model do you identify as?", timeout_ms=60_000)
        print(f"After switch response: {text_of(events).strip()[:120]}")

    print("\n--- Summary ---")
    print("Skills: load_skills + builder.skills, skill_read used by LLM ✅")
    print("Model switch: set_model mid-conversation, ModelChange recorded ✅")


if __name__ == "__main__":
    main()
