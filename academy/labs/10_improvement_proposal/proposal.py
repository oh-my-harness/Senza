"""Pure-Python proposal pipeline for Academy lab 10.

This module deliberately has no installation or file-writing operation. It reads
fixtures, builds an in-memory candidate bundle, replays that exact bundle, and
stops at human approval. The checks are a teaching model for candidate
integrity and target scope; they are not an operating-system side-effect monitor.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Optional, Union


ROOT_CAUSE = "delete_without_where_admitted_by_before_tool_call"

# Candidate artifacts may only name these two review-only locations. This is an
# exact allowlist rather than a substring/prefix guess.
ALLOWED_CANDIDATE_TARGETS = frozenset(
    {
        "candidate/plugin/db_safety_delete_where.py",
        "candidate/skill/safe-sql-mutations/SKILL.md",
    }
)

# The two fixture paths are real Lab paths. The trust_roots entries model paths
# owned by an independent approval/release system. The helper never writes any
# of them; the catalog only constrains proposal targets.
PROTECTED_TARGETS = frozenset(
    {
        "fixtures/bad_cases.jsonl",
        "fixtures/retention_cases.jsonl",
        "trust_roots/approval_gate.json",
        "trust_roots/audit_log.jsonl",
        "trust_roots/stable_release_backup.json",
        "trust_roots/release_thresholds.json",
    }
)
PROTECTED_TARGET_ROOTS = ("fixtures", "trust_roots")

_DIGEST_FIELDS = (
    "proposal_id",
    "source_case_ids",
    "root_cause",
    "recommended_carriers",
    "artifacts",
    "diff_preview",
)


def load_jsonl(path: Union[str, Path]) -> list[dict[str, Any]]:
    """Load non-empty JSONL records without mutating the source file."""

    records: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            value = json.loads(line)
            if not isinstance(value, dict) or not value.get("case_id"):
                raise ValueError(f"{path}:{line_number}: case must be an object with case_id")
            records.append(value)
    if not records:
        raise ValueError(f"{path}: expected at least one case")
    return records


def _is_delete_without_where(sql: str) -> bool:
    return bool(re.match(r"^\s*DELETE\b", sql, flags=re.IGNORECASE)) and not bool(
        re.search(r"\bWHERE\b", sql, flags=re.IGNORECASE)
    )


def diagnose_bad_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Attribute a homogeneous failure cluster to its first incorrect step."""

    evidence_ids: list[str] = []
    for case in cases:
        sql = str(case.get("args", {}).get("sql", ""))
        matches = (
            case.get("tool_name") == "run_query"
            and case.get("observed_action") == "allow"
            and case.get("expected_action") == "deny"
            and _is_delete_without_where(sql)
            and case.get("first_error") == "before_tool_call admitted an unscoped DELETE"
        )
        if not matches:
            raise ValueError(f"bad case {case.get('case_id')!r} does not match the cluster")
        evidence_ids.append(str(case["case_id"]))

    return {
        "root_cause": ROOT_CAUSE,
        "first_incorrect_step": "before_tool_call",
        "pattern": "DELETE statement has no WHERE clause but received allow",
        "evidence_case_ids": evidence_ids,
        "evidence_count": len(evidence_ids),
    }


def _plugin_rule_config() -> dict[str, Any]:
    """Return the structured rule consumed by the replay evaluator."""

    return {
        "schema_version": 1,
        "tool_name": "run_query",
        "rules": [
            {
                "id": "deny-delete-without-where",
                "statement_prefix": "DELETE",
                "when": {"missing_keyword": "WHERE"},
                "decision": {
                    "action": "deny",
                    "reason": "delete_without_where",
                    "message": "Query denied: DELETE requires an explicit WHERE clause.",
                },
            },
            {
                "id": "limit-unbounded-select",
                "statement_prefix": "SELECT",
                "when": {"missing_limit": True},
                "decision": {"action": "modify", "append_limit": 100},
            },
        ],
        "fallback_action": "allow",
    }


def _skill_content() -> dict[str, Any]:
    return {
        "steps": [
            "Preview the mutation with a SELECT using the same predicate.",
            "Use an explicit WHERE clause for DELETE statements.",
        ],
        "security_boundary": "Guidance only; the Plugin candidate owns enforcement.",
    }


def render_candidate_diff(artifacts: list[dict[str, Any]]) -> str:
    """Render a deterministic review preview from the structured artifacts."""

    chunks: list[str] = []
    for artifact in artifacts:
        target = str(artifact["candidate_target"])
        if artifact.get("kind") == "plugin":
            payload = artifact["rule_config"]
        elif artifact.get("kind") == "skill":
            payload = artifact["content"]
        else:
            raise ValueError(f"unsupported artifact kind: {artifact.get('kind')!r}")
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        chunks.extend(
            [
                "--- /dev/null",
                f"+++ {target}",
                "@@ structured-candidate @@",
                f"+{rendered}",
            ]
        )
    return "\n".join(chunks) + "\n"


def compute_candidate_digest(proposal: dict[str, Any]) -> str:
    """Hash the review-relevant proposal fields using canonical JSON."""

    payload = {field: proposal.get(field) for field in _DIGEST_FIELDS}
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_proposal(diagnosis: dict[str, Any]) -> dict[str, Any]:
    """Create a deterministic, reviewable candidate without installing it."""

    artifacts = [
        {
            "kind": "plugin",
            "name": "db-safety-delete-where",
            "scope": "before_tool_call",
            "candidate_target": "candidate/plugin/db_safety_delete_where.py",
            "purpose": "deny DELETE without WHERE before executor admission",
            "rule_config": _plugin_rule_config(),
        },
        {
            "kind": "skill",
            "name": "safe-sql-mutations",
            "scope": "SQL mutation tasks",
            "candidate_target": "candidate/skill/safe-sql-mutations/SKILL.md",
            "purpose": "preview with SELECT, then use an explicit WHERE clause",
            "content": _skill_content(),
        },
    ]
    proposal = {
        "proposal_id": "db-safety-delete-where-v1",
        "status": "candidate",
        "source_case_ids": list(diagnosis["evidence_case_ids"]),
        "root_cause": diagnosis["root_cause"],
        "recommended_carriers": {
            "hard_boundary": "plugin",
            "operator_guidance": "skill",
        },
        "artifacts": artifacts,
        "diff_preview": render_candidate_diff(artifacts),
    }
    proposal["candidate_digest"] = compute_candidate_digest(proposal)
    return proposal


def _normalize_target(target: Any) -> str:
    if not isinstance(target, str) or not target:
        raise ValueError("candidate_target must be a non-empty string")
    portable = target.replace("\\", "/")
    raw_parts = portable.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError(f"candidate_target is not normalized: {target!r}")
    path = PurePosixPath(portable)
    if path.is_absolute() or ":" in raw_parts[0]:
        raise ValueError(f"candidate_target must be relative: {target!r}")
    return path.as_posix()


def _target_is_protected(target: str) -> bool:
    return target in PROTECTED_TARGETS or any(
        target == root or target.startswith(f"{root}/")
        for root in PROTECTED_TARGET_ROOTS
    )


def _plugin_artifact(proposal: dict[str, Any]) -> dict[str, Any]:
    artifacts = proposal.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("proposal artifacts must be a list")
    plugins = [item for item in artifacts if isinstance(item, dict) and item.get("kind") == "plugin"]
    if len(plugins) != 1:
        raise ValueError("proposal must contain exactly one plugin artifact")
    return plugins[0]


def _validate_rule_config(rule_config: Any) -> None:
    if not isinstance(rule_config, dict) or rule_config.get("schema_version") != 1:
        raise ValueError("plugin rule_config must use schema_version=1")
    if not isinstance(rule_config.get("tool_name"), str) or not rule_config["tool_name"]:
        raise ValueError("plugin rule_config requires tool_name")
    if rule_config.get("fallback_action") != "allow":
        raise ValueError("plugin fallback_action must be allow")
    rules = rule_config.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("plugin rule_config requires at least one rule")

    seen_ids: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("each plugin rule must be an object")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id or rule_id in seen_ids:
            raise ValueError("plugin rule ids must be non-empty and unique")
        seen_ids.add(rule_id)
        prefix = rule.get("statement_prefix")
        if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z]+", prefix):
            raise ValueError(f"invalid statement_prefix for {rule_id}")
        when = rule.get("when")
        if not isinstance(when, dict) or len(when) != 1:
            raise ValueError(f"rule {rule_id} must have one supported condition")
        if "missing_keyword" in when:
            keyword = when["missing_keyword"]
            if not isinstance(keyword, str) or not re.fullmatch(r"[A-Z]+", keyword):
                raise ValueError(f"invalid missing_keyword for {rule_id}")
        elif when.get("missing_limit") is not True:
            raise ValueError(f"unsupported condition for {rule_id}")

        decision = rule.get("decision")
        if not isinstance(decision, dict):
            raise ValueError(f"rule {rule_id} requires a decision")
        action = decision.get("action")
        if action == "deny":
            if not isinstance(decision.get("reason"), str) or not isinstance(
                decision.get("message"), str
            ):
                raise ValueError(f"deny rule {rule_id} requires reason and message")
        elif action == "modify":
            limit = decision.get("append_limit")
            if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10_000:
                raise ValueError(f"modify rule {rule_id} requires a bounded integer limit")
        else:
            raise ValueError(f"unsupported decision action for {rule_id}: {action!r}")


def _validate_artifact_schema(proposal: dict[str, Any]) -> None:
    artifacts = proposal.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise ValueError("proposal must contain one plugin and one skill artifact")
    kinds = [item.get("kind") for item in artifacts if isinstance(item, dict)]
    if sorted(kinds) != ["plugin", "skill"]:
        raise ValueError("proposal artifact kinds must be plugin and skill")
    plugin = _plugin_artifact(proposal)
    _validate_rule_config(plugin.get("rule_config"))
    skill = next(item for item in artifacts if item.get("kind") == "skill")
    content = skill.get("content")
    if not isinstance(content, dict) or not isinstance(content.get("steps"), list):
        raise ValueError("skill artifact requires structured content steps")
    if not isinstance(content.get("security_boundary"), str):
        raise ValueError("skill artifact requires a security_boundary")


def proposal_boundary_checks(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    """Check the in-memory bundle's integrity and declared target scope.

    These checks do not observe arbitrary filesystem, package-manager, process,
    network, or training side effects. They only gate the proposal object passed
    to this function.
    """

    expected_digest = proposal.get("candidate_digest")
    actual_digest = compute_candidate_digest(proposal)

    schema_error: Optional[str] = None
    try:
        _validate_artifact_schema(proposal)
    except (KeyError, TypeError, ValueError) as error:
        schema_error = str(error)

    diff_error: Optional[str] = None
    try:
        rendered_diff = render_candidate_diff(proposal["artifacts"])
        diff_matches = proposal.get("diff_preview") == rendered_diff
    except (KeyError, TypeError, ValueError) as error:
        diff_matches = False
        diff_error = str(error)

    targets: list[str] = []
    target_error: Optional[str] = None
    try:
        targets = [
            _normalize_target(artifact["candidate_target"])
            for artifact in proposal["artifacts"]
        ]
    except (KeyError, TypeError, ValueError) as error:
        target_error = str(error)

    targets_well_formed = target_error is None
    targets_unique = targets_well_formed and len(targets) == len(set(targets))
    targets_allowlisted = targets_well_formed and set(targets) == ALLOWED_CANDIDATE_TARGETS
    protected_untouched = targets_well_formed and not any(
        _target_is_protected(target) for target in targets
    )

    return [
        {
            "name": "candidate-digest-matches",
            "passed": isinstance(expected_digest, str) and expected_digest == actual_digest,
            "details": {"expected": expected_digest, "actual": actual_digest},
        },
        {
            "name": "artifact-schema-valid",
            "passed": schema_error is None,
            "details": {"error": schema_error},
        },
        {
            "name": "diff-preview-matches-artifacts",
            "passed": diff_matches,
            "details": {"error": diff_error},
        },
        {
            "name": "candidate-targets-well-formed",
            "passed": targets_well_formed,
            "details": {"targets": targets, "error": target_error},
        },
        {
            "name": "candidate-targets-unique",
            "passed": targets_unique,
            "details": {"targets": targets},
        },
        {
            "name": "candidate-targets-allowlisted",
            "passed": targets_allowlisted,
            "details": {
                "targets": targets,
                "allowlist": sorted(ALLOWED_CANDIDATE_TARGETS),
            },
        },
        {
            "name": "protected-targets-untouched",
            "passed": protected_untouched,
            "details": {
                "targets": targets,
                "protected_targets": sorted(PROTECTED_TARGETS),
            },
        },
    ]


def _condition_matches(when: dict[str, Any], sql: str) -> bool:
    if "missing_keyword" in when:
        keyword = str(when["missing_keyword"])
        return re.search(rf"\b{re.escape(keyword)}\b", sql, flags=re.IGNORECASE) is None
    if when.get("missing_limit") is True:
        return re.search(r"\bLIMIT\s+\d+\b", sql, flags=re.IGNORECASE) is None
    raise ValueError(f"unsupported rule condition: {when!r}")


def candidate_guard(
    rule_config: dict[str, Any], tool_name: str, args: dict[str, Any]
) -> Union[str, dict[str, Any]]:
    """Execute the structured Plugin rule from the candidate proposal."""

    _validate_rule_config(rule_config)
    if tool_name != rule_config["tool_name"]:
        return str(rule_config["fallback_action"])

    sql = str(args.get("sql", "")).strip()
    for rule in rule_config["rules"]:
        prefix = str(rule["statement_prefix"])
        if not re.match(rf"^{re.escape(prefix)}\b", sql, flags=re.IGNORECASE):
            continue
        if not _condition_matches(rule["when"], sql):
            continue
        decision = rule["decision"]
        if decision["action"] == "deny":
            return {
                "action": "deny",
                "result": {
                    "content": [{"type": "text", "text": decision["message"]}],
                    "details": {"reason": decision["reason"], "sql": sql},
                },
            }
        if decision["action"] == "modify":
            modified_args = dict(args)
            modified_args["sql"] = (
                f"{sql.rstrip().rstrip(';')} LIMIT {decision['append_limit']}"
            )
            return {"action": "modify", "args": modified_args}

    return str(rule_config["fallback_action"])


def _decision_action(decision: Union[str, dict[str, Any]]) -> str:
    return decision if isinstance(decision, str) else str(decision["action"])


def evaluate_case(case: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Replay one boundary/retention case against the proposal's rule_config."""

    plugin = _plugin_artifact(proposal)
    rule_config = plugin["rule_config"]
    args = dict(case.get("args", {}))
    decision = candidate_guard(rule_config, str(case.get("tool_name", "")), args)
    action = _decision_action(decision)

    effective_args: Optional[dict[str, Any]]
    if action == "allow":
        effective_args = args
    elif action == "modify":
        effective_args = dict(decision["args"])
    else:
        effective_args = None

    effective_sql = None if effective_args is None else effective_args.get("sql")
    action_passed = action == case.get("expected_action")
    sql_passed = (
        "expected_effective_sql" not in case
        or effective_sql == case.get("expected_effective_sql")
    )
    return {
        "case_id": case["case_id"],
        "expected_action": case.get("expected_action"),
        "actual_action": action,
        "effective_sql": effective_sql,
        "passed": action_passed and sql_passed,
    }


def evaluate_cases(
    cases: list[dict[str, Any]], proposal: dict[str, Any]
) -> list[dict[str, Any]]:
    return [evaluate_case(case, proposal) for case in cases]


def _not_evaluated(cases: list[dict[str, Any]], reason: str) -> list[dict[str, Any]]:
    return [
        {
            "case_id": case["case_id"],
            "expected_action": case.get("expected_action"),
            "actual_action": "not_evaluated",
            "effective_sql": None,
            "passed": False,
            "reason": reason,
        }
        for case in cases
    ]


def validate_proposal(
    proposal: dict[str, Any],
    boundary_cases: list[dict[str, Any]],
    retention_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run candidate preflight, then replay the exact preflighted proposal."""

    preflight_results = proposal_boundary_checks(proposal)
    preflight_passed = all(result["passed"] for result in preflight_results)
    if preflight_passed:
        boundary_results = evaluate_cases(boundary_cases, proposal)
        retention_results = evaluate_cases(retention_cases, proposal)
    else:
        reason = "candidate preflight failed; replay refused"
        boundary_results = _not_evaluated(boundary_cases, reason)
        retention_results = _not_evaluated(retention_cases, reason)

    boundary_passed = preflight_passed and all(
        result["passed"] for result in boundary_results
    )
    retention_passed = preflight_passed and all(
        result["passed"] for result in retention_results
    )
    all_passed = preflight_passed and boundary_passed and retention_passed
    return {
        "boundary": {"passed": boundary_passed, "results": boundary_results},
        "retention": {"passed": retention_passed, "results": retention_results},
        "protected_boundaries": {
            "passed": preflight_passed,
            "results": preflight_results,
        },
        "all_passed": all_passed,
    }


def run_proposal_pipeline(
    bad_cases_path: Union[str, Path], retention_cases_path: Union[str, Path]
) -> dict[str, Any]:
    """Run diagnosis, candidate-bound replay and offline gates; never apply."""

    bad_cases = load_jsonl(bad_cases_path)
    retention_cases = load_jsonl(retention_cases_path)
    diagnosis = diagnose_bad_cases(bad_cases)
    proposal = build_proposal(diagnosis)
    validation = validate_proposal(proposal, bad_cases, retention_cases)

    status = (
        "awaiting_human_approval"
        if validation["all_passed"]
        else "rejected_by_offline_gate"
    )
    proposal["status"] = status
    return {
        "status": status,
        "diagnosis": diagnosis,
        "proposal": proposal,
        "validation": validation,
        "approval": {
            "required": True,
            "actor": "independent_human_reviewer",
            "state": status,
        },
        "application": {
            "performed": False,
            "scope": "This teaching helper has no apply/install/train operation.",
        },
    }
