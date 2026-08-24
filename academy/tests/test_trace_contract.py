import json
from pathlib import Path, PurePosixPath

from academy.common import load_trace


ACADEMY_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ACADEMY_ROOT.parent
COURSE_MANIFEST_PATH = ACADEMY_ROOT / "course_manifest.json"
SCENARIO_CATALOG_PATH = REPOSITORY_ROOT / "academy" / "scenarios" / "catalog.json"


def _trace_paths() -> list[Path]:
    return sorted((ACADEMY_ROOT / "labs").glob("*/expected_trace.json"))


def _load_manifest() -> dict:
    return json.loads(COURSE_MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_scenario_catalog() -> dict:
    return json.loads(SCENARIO_CATALOG_PATH.read_text(encoding="utf-8"))


def test_every_recorded_trace_obeys_the_common_contract():
    paths = _trace_paths()
    assert paths, "Academy must contain at least one recorded trace"
    for path in paths:
        trace = load_trace(path)
        assert trace["lab"] == path.parent.name.split("_", 1)[0]


def test_every_live_example_link_resolves_to_the_canonical_directory():
    examples_dir = REPOSITORY_ROOT / "live-tests" / "examples"
    for path in _trace_paths():
        for filename in load_trace(path)["live_examples"]:
            assert (examples_dir / filename).is_file(), f"{path}: missing live example {filename}"


def test_course_manifest_matches_all_ten_labs_and_required_artifacts():
    manifest = _load_manifest()
    labs = manifest["labs"]
    assert [lab["id"] for lab in labs] == [f"{number:02d}" for number in range(1, 11)]

    expected_directories = {lab["directory"] for lab in labs}
    actual_directories = {
        path.name
        for path in (ACADEMY_ROOT / "labs").iterdir()
        if path.is_dir() and path.name[:2].isdigit()
    }
    assert actual_directories == expected_directories

    for lab in labs:
        lab_dir = ACADEMY_ROOT / "labs" / lab["directory"]
        for filename in ("README.md", "demo.py", "expected_trace.json", "test_demo.py"):
            assert (lab_dir / filename).is_file(), f"{lab_dir}: missing {filename}"
        trace = load_trace(lab_dir / "expected_trace.json")
        assert trace["lab"] == lab["id"]
        assert trace["maturity"] == lab["maturity"]


def test_first_release_wave_contains_the_six_stable_labs():
    manifest = _load_manifest()
    wave_one = [lab for lab in manifest["labs"] if lab["release_wave"] == 1]
    assert [lab["id"] for lab in wave_one] == ["01", "02", "03", "04", "05", "06"]
    assert all(lab["maturity"] == "stable" for lab in wave_one)


def test_course_scenario_refs_resolve_to_catalog_and_existing_targets():
    manifest = _load_manifest()
    scenarios = {
        scenario["id"]: scenario for scenario in _load_scenario_catalog()["scenarios"]
    }

    for lab in manifest["labs"]:
        refs = lab["scenario_refs"]
        aliases = [ref["alias"] for ref in refs]
        assert len(aliases) == len(set(aliases)), f"lab {lab['id']}: duplicate alias"
        assert all(ref["role"] in {"primary", "supporting"} for ref in refs)
        assert sum(ref["role"] == "primary" for ref in refs) == 1
        for ref in refs:
            scenario_id = ref["scenario_id"]
            assert scenario_id in scenarios, (
                f"lab {lab['id']}: missing catalog scenario {scenario_id}"
            )
            target = REPOSITORY_ROOT / scenarios[scenario_id]["legacy_path"]
            assert target.is_file(), f"lab {lab['id']}: missing scenario target {target}"


def test_course_trace_live_examples_exactly_follow_manifest_catalog_order():
    manifest = _load_manifest()
    scenarios = {
        scenario["id"]: scenario for scenario in _load_scenario_catalog()["scenarios"]
    }

    for lab in manifest["labs"]:
        trace_path = ACADEMY_ROOT / "labs" / lab["directory"] / "expected_trace.json"
        expected_legacy_paths = [
            scenarios[ref["scenario_id"]]["legacy_path"]
            for ref in lab["scenario_refs"]
        ]
        trace_legacy_paths = [
            str(PurePosixPath("live-tests/examples") / filename)
            for filename in load_trace(trace_path)["live_examples"]
        ]
        assert trace_legacy_paths == expected_legacy_paths


def test_course_manifest_has_twenty_edges_and_eighteen_unique_scenarios():
    refs = [
        ref
        for lab in _load_manifest()["labs"]
        for ref in lab["scenario_refs"]
    ]
    assert len(refs) == 20
    assert len({ref["scenario_id"] for ref in refs}) == 18
