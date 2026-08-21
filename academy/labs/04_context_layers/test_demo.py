import importlib.util
import sys
from pathlib import Path

from academy.common import load_trace


LAB_DIR = Path(__file__).resolve().parent


def _load_demo():
    name = "senza_academy_lab04_demo"
    spec = importlib.util.spec_from_file_location(name, LAB_DIR / "demo.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


DEMO = _load_demo()


def test_recorded_snapshots_cover_all_layers_and_keep_prefix_stable():
    snapshots = DEMO.context_snapshots()

    assert tuple(snapshots[0]["layers"]) == DEMO.LAYER_ORDER
    assert len(snapshots) == 4
    assert all(
        snapshot["layers"]["stable_prefix"] == DEMO.STABLE_PREFIX
        for snapshot in snapshots
    )
    assert len(snapshots[1]["layers"]["skill"]) > len(snapshots[0]["layers"]["skill"])
    assert snapshots[2]["layers"]["status"]
    assert len(snapshots[2]["layers"]["trajectory"]) > len(
        snapshots[1]["layers"]["trajectory"]
    )


def test_compaction_reduces_trajectory_and_keeps_structured_context():
    before, after = DEMO.context_snapshots()[-2:]
    summary = "\n".join(after["layers"]["compaction"])

    assert len(after["layers"]["trajectory"]) < len(before["layers"]["trajectory"])
    for section in ("## Goal", "## Progress", "## Key Decisions", "## Next Steps", "## Critical Context"):
        assert section in summary
    assert after["layers"]["stable_prefix"] == before["layers"]["stable_prefix"]


def test_context_diff_prints_every_layer_including_unchanged_prefix():
    diffs = DEMO.context_diffs()

    assert len(diffs) == 3
    for rendered in diffs:
        for layer in DEMO.LAYER_ORDER:
            assert layer in rendered
        assert "= stable_prefix" in rendered
    assert "+ status" in diffs[1]
    assert "+ compaction" in diffs[2]


def test_cli_defaults_to_recorded_and_maps_each_live_example():
    args = DEMO.build_parser().parse_args([])

    assert args.mode == "recorded"
    assert DEMO.LIVE_EXAMPLES == {
        "skills": "06_skills_model_switch.py",
        "status": "16_status_panel.py",
        "compaction": "21_context_aware_compact.py",
    }


def test_trace_and_readme_keep_manual_compaction_boundary_accurate():
    trace = load_trace(LAB_DIR / "expected_trace.json")
    readme = (LAB_DIR / "README.md").read_text(encoding="utf-8")

    assert trace["lab"] == "04"
    assert trace["maturity"] == "stable"
    assert trace["live_examples"] == list(DEMO.LIVE_EXAMPLES.values())
    assert "`harness.compact()`" in readme
    assert "它不是 Runtime-only 能力" in readme
    assert "教学模型" in readme
    assert "chapter2.md" in readme
