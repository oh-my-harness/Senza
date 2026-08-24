import copy
import importlib.util
import sys
from pathlib import Path

from academy.common import load_trace


LAB_DIR = Path(__file__).resolve().parent


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, LAB_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PROPOSAL = _load_module("senza_academy_lab10_proposal", "proposal.py")
DEMO = _load_module("senza_academy_lab10_demo", "demo.py")


def _run_pipeline():
    return PROPOSAL.run_proposal_pipeline(
        LAB_DIR / "fixtures" / "bad_cases.jsonl",
        LAB_DIR / "fixtures" / "retention_cases.jsonl",
    )


def _proposal_and_cases():
    bad_cases = PROPOSAL.load_jsonl(LAB_DIR / "fixtures" / "bad_cases.jsonl")
    retention_cases = PROPOSAL.load_jsonl(
        LAB_DIR / "fixtures" / "retention_cases.jsonl"
    )
    diagnosis = PROPOSAL.diagnose_bad_cases(bad_cases)
    return PROPOSAL.build_proposal(diagnosis), bad_cases, retention_cases


def _rebind_candidate(proposal):
    proposal["diff_preview"] = PROPOSAL.render_candidate_diff(proposal["artifacts"])
    proposal["candidate_digest"] = PROPOSAL.compute_candidate_digest(proposal)


def _gate_results(validation):
    return {
        result["name"]: result
        for result in validation["protected_boundaries"]["results"]
    }


def _source_snapshot() -> dict[str, bytes]:
    return {
        str(path.relative_to(LAB_DIR)): path.read_bytes()
        for path in LAB_DIR.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def test_bad_cases_are_attributed_to_delete_without_where():
    bad_cases = PROPOSAL.load_jsonl(LAB_DIR / "fixtures" / "bad_cases.jsonl")
    diagnosis = PROPOSAL.diagnose_bad_cases(bad_cases)

    assert diagnosis["root_cause"] == PROPOSAL.ROOT_CAUSE
    assert diagnosis["first_incorrect_step"] == "before_tool_call"
    assert diagnosis["evidence_count"] == 3
    assert diagnosis["evidence_case_ids"] == [case["case_id"] for case in bad_cases]


def test_proposal_contains_plugin_and_skill_candidates_with_safe_roles():
    report = _run_pipeline()
    proposal = report["proposal"]
    artifacts = {artifact["kind"]: artifact for artifact in proposal["artifacts"]}

    assert artifacts["plugin"]["scope"] == "before_tool_call"
    assert "deny DELETE without WHERE" in artifacts["plugin"]["purpose"]
    assert artifacts["skill"]["name"] == "safe-sql-mutations"
    assert proposal["recommended_carriers"] == {
        "hard_boundary": "plugin",
        "operator_guidance": "skill",
    }
    plugin_rule = artifacts["plugin"]["rule_config"]
    assert plugin_rule["tool_name"] == "run_query"
    assert plugin_rule["rules"][0]["decision"]["action"] == "deny"
    assert artifacts["skill"]["content"]["security_boundary"].startswith(
        "Guidance only"
    )
    assert proposal["diff_preview"] == PROPOSAL.render_candidate_diff(
        proposal["artifacts"]
    )
    assert proposal["candidate_digest"] == PROPOSAL.compute_candidate_digest(proposal)
    assert len(proposal["candidate_digest"]) == 64


def test_boundary_retention_and_protected_sets_all_pass():
    report = _run_pipeline()
    validation = report["validation"]

    assert validation["all_passed"] is True
    assert validation["boundary"]["passed"] is True
    assert validation["retention"]["passed"] is True
    assert validation["protected_boundaries"]["passed"] is True
    assert all(result["passed"] for result in validation["boundary"]["results"])
    assert all(result["passed"] for result in validation["retention"]["results"])
    assert all(result["passed"] for result in validation["protected_boundaries"]["results"])
    gates = _gate_results(validation)
    assert gates["candidate-digest-matches"]["passed"] is True
    assert gates["diff-preview-matches-artifacts"]["passed"] is True
    assert gates["candidate-targets-allowlisted"]["passed"] is True
    assert gates["protected-targets-untouched"]["passed"] is True


def test_pipeline_stops_at_human_approval_and_keeps_lab_files_unchanged():
    before = _source_snapshot()
    report = _run_pipeline()
    after = _source_snapshot()

    assert report["status"] == "awaiting_human_approval"
    assert report["approval"] == {
        "required": True,
        "actor": "independent_human_reviewer",
        "state": "awaiting_human_approval",
    }
    assert report["application"] == {
        "performed": False,
        "scope": "This teaching helper has no apply/install/train operation.",
    }
    assert before == after


def test_replay_consumes_the_rule_config_bound_into_the_proposal():
    proposal, bad_cases, retention_cases = _proposal_and_cases()
    modified = copy.deepcopy(proposal)
    plugin = next(item for item in modified["artifacts"] if item["kind"] == "plugin")
    limit_rule = next(
        rule for rule in plugin["rule_config"]["rules"] if rule["decision"]["action"] == "modify"
    )
    limit_rule["decision"]["append_limit"] = 25
    _rebind_candidate(modified)

    validation = PROPOSAL.validate_proposal(modified, bad_cases, retention_cases)
    assert validation["protected_boundaries"]["passed"] is True
    assert validation["boundary"]["passed"] is True
    assert validation["retention"]["passed"] is False
    rewritten = next(
        item
        for item in validation["retention"]["results"]
        if item["case_id"] == "keep-unbounded-select-rewrite"
    )
    assert rewritten["effective_sql"] == "SELECT id FROM users LIMIT 25"


def test_artifact_or_diff_tampering_without_rebinding_fails_preflight():
    proposal, bad_cases, retention_cases = _proposal_and_cases()

    artifact_tampered = copy.deepcopy(proposal)
    plugin = next(
        item for item in artifact_tampered["artifacts"] if item["kind"] == "plugin"
    )
    plugin["rule_config"]["rules"][0]["decision"]["message"] = "tampered"

    diff_tampered = copy.deepcopy(proposal)
    diff_tampered["diff_preview"] += "+tampered\n"

    for candidate in (artifact_tampered, diff_tampered):
        validation = PROPOSAL.validate_proposal(candidate, bad_cases, retention_cases)
        gates = _gate_results(validation)
        assert gates["candidate-digest-matches"]["passed"] is False
        assert gates["diff-preview-matches-artifacts"]["passed"] is False
        assert validation["all_passed"] is False
        assert all(
            item["actual_action"] == "not_evaluated"
            for item in validation["boundary"]["results"]
        )


def test_protected_or_unlisted_target_fails_even_when_digest_is_rebound():
    proposal, bad_cases, retention_cases = _proposal_and_cases()
    modified = copy.deepcopy(proposal)
    plugin = next(item for item in modified["artifacts"] if item["kind"] == "plugin")
    plugin["candidate_target"] = "fixtures/retention_cases.jsonl"
    _rebind_candidate(modified)

    validation = PROPOSAL.validate_proposal(modified, bad_cases, retention_cases)
    gates = _gate_results(validation)
    assert gates["candidate-digest-matches"]["passed"] is True
    assert gates["candidate-targets-allowlisted"]["passed"] is False
    assert gates["protected-targets-untouched"]["passed"] is False
    assert validation["all_passed"] is False


def test_cli_defaults_to_recorded_and_maps_both_live_examples():
    args = DEMO.build_parser().parse_args([])

    assert args.mode == "recorded"
    assert DEMO.LIVE_EXAMPLES == {
        "plugins": "32_plugins.py",
        "audit": "12_tracing_audit.py",
    }


def test_recorded_output_reports_binding_target_and_proof_scope(capsys):
    report = DEMO.run_recorded()
    output = capsys.readouterr().out

    assert report["status"] == "awaiting_human_approval"
    assert "candidate digest bound:  true" in output
    assert "targets allowlisted:     true" in output
    assert "candidate applied:       false" in output
    assert "not arbitrary external side effects" in output


def test_trace_is_teaching_maturity_and_stops_at_approval():
    trace = load_trace(LAB_DIR / "expected_trace.json")

    assert trace["lab"] == "10"
    assert trace["maturity"] == "teaching"
    assert trace["events"][-1]["status"] == "paused"
    assert trace["events"][-1]["lifecycle"] == "awaiting_human_approval"
    assert trace["live_examples"] == ["32_plugins.py", "12_tracing_audit.py"]


def test_readme_states_product_training_and_safety_boundaries():
    readme = (LAB_DIR / "README.md").read_text(encoding="utf-8")

    assert "Senza Academy 的教学应用层" in readme
    assert "Runtime 当前没有" in readme
    assert "安全机制不能自我修改" in readme
    assert "awaiting_human_approval" in readme
    assert "不 install、不 publish、不改生产文件" in readme
    assert "SFT、RL" in readme
    assert "fixture 是合成的历史 bad case" in readme.lower()
    assert "candidate_digest" in readme
    assert "精确 allowlist" in readme
    assert "不能证明任意目录外副作用" in readme


def test_recorded_source_has_no_senza_or_install_imports():
    source = (LAB_DIR / "proposal.py").read_text(encoding="utf-8")
    demo_source = (LAB_DIR / "demo.py").read_text(encoding="utf-8")

    assert "import senza" not in source
    assert "import senza" not in demo_source
    assert "subprocess" not in source
    assert "pip install" not in source
    assert ".write_text(" not in source
    assert ".write_bytes(" not in source
