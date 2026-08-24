import inspect

import pytest

from academy.common import live_examples_for_lab, run_course_live, run_live_example
from academy.common import catalog as catalog_bridge


def test_live_examples_keep_the_existing_alias_and_filename_view():
    assert live_examples_for_lab("04") == {
        "skills": "06_skills_model_switch.py",
        "status": "16_status_panel.py",
        "compaction": "21_context_aware_compact.py",
    }
    assert live_examples_for_lab("6") == {
        "workflow": "08_workflow.py",
        "executor": "39_executor_steps.py",
        "hitl": "41_human_in_the_loop.py",
        "recovery": "45_hooks_retries.py",
    }


def test_run_course_live_uses_stable_id_and_unified_runner(monkeypatch):
    calls = []

    def fake_run(command, *, cwd, check):
        calls.append((command, cwd, check))

    monkeypatch.setattr(catalog_bridge.subprocess, "run", fake_run)
    run_course_live("10", "audit")

    command, cwd, check = calls.pop()
    assert command == [
        catalog_bridge.sys.executable,
        "-m",
        "academy.scenarios",
        "run",
        "observability.audit",
    ]
    assert cwd == catalog_bridge.REPOSITORY_ROOT
    assert check is True


def test_run_course_live_defaults_to_the_manifest_primary_role(monkeypatch):
    delegated = []
    monkeypatch.setattr(catalog_bridge, "_run_scenario", delegated.append)

    run_course_live("06")
    assert delegated == ["workflow.retry_replay"]


def test_legacy_filename_helper_keeps_signature_but_delegates_by_catalog(monkeypatch):
    delegated = []
    monkeypatch.setattr(catalog_bridge, "_run_scenario", delegated.append)

    assert list(inspect.signature(run_live_example).parameters) == ["filename"]
    run_live_example("32_plugins.py")
    assert delegated == ["plugin.composition"]


@pytest.mark.parametrize(
    "filename",
    ("../02_tool_calling.py", "live-tests/examples/02_tool_calling.py", "README.md"),
)
def test_legacy_filename_helper_rejects_non_plain_python_names(filename):
    with pytest.raises(ValueError, match="plain .py filename"):
        run_live_example(filename)


def test_every_course_legacy_target_is_repository_local():
    for lab_id in (f"{number:02d}" for number in range(1, 11)):
        for filename in live_examples_for_lab(lab_id).values():
            target = catalog_bridge.REPOSITORY_ROOT / "live-tests" / "examples" / filename
            assert target.is_file()
            assert target.resolve().is_relative_to(
                catalog_bridge.REPOSITORY_ROOT.resolve()
            )
