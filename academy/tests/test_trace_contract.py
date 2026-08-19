import json
from pathlib import Path

from academy.common import load_trace


ACADEMY_ROOT = Path(__file__).resolve().parents[1]


def _trace_paths() -> list[Path]:
    return sorted((ACADEMY_ROOT / "labs").glob("*/expected_trace.json"))


def test_every_recorded_trace_obeys_the_common_contract():
    paths = _trace_paths()
    assert paths, "Academy must contain at least one recorded trace"
    for path in paths:
        trace = load_trace(path)
        assert trace["lab"] == path.parent.name.split("_", 1)[0]


def test_every_live_example_link_resolves_to_the_canonical_directory():
    repository_root = ACADEMY_ROOT.parent
    examples_dir = repository_root / "live-tests" / "examples"
    for path in _trace_paths():
        for filename in load_trace(path)["live_examples"]:
            assert (examples_dir / filename).is_file(), f"{path}: missing live example {filename}"


def test_course_manifest_matches_all_ten_labs_and_required_artifacts():
    manifest = json.loads((ACADEMY_ROOT / "course_manifest.json").read_text(encoding="utf-8"))
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
    manifest = json.loads((ACADEMY_ROOT / "course_manifest.json").read_text(encoding="utf-8"))
    wave_one = [lab for lab in manifest["labs"] if lab["release_wave"] == 1]
    assert [lab["id"] for lab in wave_one] == ["01", "02", "03", "04", "05", "06"]
    assert all(lab["maturity"] == "stable" for lab in wave_one)
