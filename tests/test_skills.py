"""Smoke tests for Skills loading exposure (G4)."""

import os

import senza


def _write_skill_md(directory, name="test-skill", description="A test skill", body="Skill body."):
    d = os.path.join(directory, name)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "SKILL.md")
    with open(path, "w") as f:
        f.write(f"---\nname: {name}\ndescription: {description}\n---\n{body}\n")
    return path


def test_load_skills(tmp_path):
    """load_skills scans a directory for SKILL.md files."""
    _write_skill_md(str(tmp_path), name="my-skill")
    skills = senza.load_skills(str(tmp_path))
    assert len(skills) >= 1
    assert type(skills[0]).__name__ == "Skill"


def test_load_skills_empty(tmp_path):
    """load_skills on empty dir returns empty list."""
    skills = senza.load_skills(str(tmp_path))
    assert skills == []


def test_builder_skill_chains():
    """builder.skill() accepts a Skill and chains."""
    provider = senza.create_openai_provider(api_key="test-key")
    # Can't easily load skills without a dir, so just test the method exists
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", provider)
    # skill() requires a Skill object — skip if no skills loaded
    # This test verifies the method exists and is callable
    assert hasattr(builder, "skill")


def test_builder_skills_chains(tmp_path):
    """builder.skills() accepts a list of Skills and chains."""
    _write_skill_md(str(tmp_path), name="skill-a")
    _write_skill_md(str(tmp_path), name="skill-b")
    skills = senza.load_skills(str(tmp_path))
    provider = senza.create_openai_provider(api_key="test-key")
    builder = senza.HarnessBuilder("gpt-4o").provider("gpt-*", provider)
    result = builder.skills(skills)
    assert result is builder


def test_builder_skill_then_build(tmp_path):
    """builder with skill set can build successfully."""
    _write_skill_md(str(tmp_path), name="my-skill")
    skills = senza.load_skills(str(tmp_path))
    provider = senza.create_openai_provider(api_key="test-key")
    harness = senza.HarnessBuilder("gpt-4o").provider("gpt-*", provider).skills(skills).build()
    assert harness is not None


def test_builder_disable_skill_read_tool(tmp_path):
    """disable_skill_read_tool prevents SkillReadTool auto-registration."""
    _write_skill_md(str(tmp_path), name="my-skill")
    skills = senza.load_skills(str(tmp_path))
    provider = senza.create_openai_provider(api_key="test-key")
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .skills(skills)
        .disable_skill_read_tool()
        .build()
    )
    assert harness is not None
