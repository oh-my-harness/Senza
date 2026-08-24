"""CLI and subprocess runner for cataloged Senza scenarios."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .catalog import Catalog, CatalogError, Scenario, load_catalog, repository_root


_SECRET_NAME_RE = re.compile(r"(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE)
_SECRET_LITERAL_RE = re.compile(
    r"\b(?:sk|rk|ghp|gho|github_pat)[-_][A-Za-z0-9_-]{8,}"
)
_COURSE_MANIFEST = Path("academy/course_manifest.json")


def _emit_json(value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        print(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True))
        return
    buffer.write(payload.encode("utf-8"))
    buffer.flush()


def _redact_text(value: Any) -> str:
    """Normalize subprocess text and redact credential-shaped values."""

    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)

    for name, secret in os.environ.items():
        if _SECRET_NAME_RE.search(name) and len(secret) >= 4:
            text = text.replace(secret, "[REDACTED:{}]".format(name))
    return _SECRET_LITERAL_RE.sub("[REDACTED:CREDENTIAL]", text)


def _has_explicit_env(name: str) -> bool:
    """Check only this process's explicit environment; never load env files."""

    return bool(os.environ.get(name))


def _module_available(name: str) -> bool:
    """Check importability without importing the package or running its code."""

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def inspect_requirements(scenario: Scenario) -> Dict[str, Any]:
    """Return a secret-safe readiness report for one scenario.

    Provider values are never read beyond truthiness and are never returned.
    Services are declared for visibility but intentionally not contacted by
    ``doctor``; network probing would make diagnosis stateful and surprising.
    """

    requirements = scenario.requirements
    provider = requirements["provider"]
    provider_env = list(provider["any_of_env"])
    configured_provider_names = [name for name in provider_env if _has_explicit_env(name)]
    provider_ready = (not provider["required"]) or bool(configured_provider_names)

    required_env = list(requirements["env"])
    missing_env = [name for name in required_env if not _has_explicit_env(name)]
    commands = {
        name: shutil.which(name) is not None for name in requirements["commands"]
    }
    python_modules = {"senza": _module_available("senza")}
    platforms = list(requirements["platforms"])
    platform_ready = "any" in platforms or sys.platform in platforms
    ready = (
        provider_ready
        and not missing_env
        and all(commands.values())
        and all(python_modules.values())
        and platform_ready
    )
    return {
        "scenario_id": scenario.id,
        "ready": ready,
        "provider": {
            "required": provider["required"],
            "accepted_env_names": provider_env,
            "configured_env_names": configured_provider_names,
            "ready": provider_ready,
        },
        "env": {"required_names": required_env, "missing_names": missing_env},
        "commands": commands,
        "python_modules": python_modules,
        "services": {
            "declared": list(requirements["services"]),
            "probe": "not-performed",
        },
        "platform": {
            "current": sys.platform,
            "supported": platforms,
            "ready": platform_ready,
        },
    }


def _skip_reasons(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    reasons: List[Dict[str, Any]] = []
    if not report["provider"]["ready"]:
        reasons.append(
            {
                "code": "missing-provider",
                "accepted_env_names": report["provider"]["accepted_env_names"],
            }
        )
    if report["env"]["missing_names"]:
        reasons.append(
            {"code": "missing-env", "names": report["env"]["missing_names"]}
        )
    missing_commands = [
        name for name, available in report["commands"].items() if not available
    ]
    if missing_commands:
        reasons.append({"code": "missing-command", "names": missing_commands})
    missing_modules = [
        name for name, available in report["python_modules"].items() if not available
    ]
    if missing_modules:
        reasons.append({"code": "missing-python-module", "names": missing_modules})
    if not report["platform"]["ready"]:
        reasons.append(
            {
                "code": "unsupported-platform",
                "current": report["platform"]["current"],
                "supported": report["platform"]["supported"],
            }
        )
    return reasons


def run_scenario(
    scenario: Scenario,
    *,
    timeout: Optional[float] = None,
    allow_quarantined: bool = False,
    json_output: bool = False,
) -> int:
    """Run a scenario as a child Python process from the repository root."""

    effective_timeout = float(scenario.timeout_seconds if timeout is None else timeout)
    if not math.isfinite(effective_timeout) or effective_timeout <= 0:
        raise ValueError("timeout must be a finite number greater than zero")
    if scenario.tier == "quarantined" and not allow_quarantined:
        _emit_json(
            {
                "status": "refused",
                "scenario_id": scenario.id,
                "reason": {
                    "code": "quarantined",
                    "message": "pass --allow-quarantined to run this needs-fix scenario",
                },
            }
        )
        return 2

    report = inspect_requirements(scenario)
    reasons = _skip_reasons(report)
    if reasons:
        _emit_json(
            {
                "status": "skipped",
                "scenario_id": scenario.id,
                "reasons": reasons,
            }
        )
        return 0

    root = repository_root()
    command = [sys.executable, str(scenario.target)]
    child_env = os.environ.copy()
    child_env["PYTHONUTF8"] = "1"
    try:
        completed = subprocess.run(
            command,
            cwd=str(root),
            env=child_env,
            timeout=effective_timeout,
            check=False,
            capture_output=json_output,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        result: Dict[str, Any] = {
            "status": "timeout",
            "scenario_id": scenario.id,
            "timeout_seconds": effective_timeout,
        }
        if json_output:
            result["stdout"] = _redact_text(exc.stdout)
            result["stderr"] = _redact_text(exc.stderr)
        _emit_json(result)
        return 124
    except OSError as exc:
        _emit_json(
            {
                "status": "error",
                "scenario_id": scenario.id,
                "reason": {"code": "process-start-failed", "message": str(exc)},
            }
        )
        return 1


    status = "passed" if completed.returncode == 0 else "failed"
    if json_output:
        _emit_json(
            {
                "status": status,
                "scenario_id": scenario.id,
                "exit_code": completed.returncode,
                "stdout": _redact_text(completed.stdout),
                "stderr": _redact_text(completed.stderr),
            }
        )
    return completed.returncode


def _load_course_manifest() -> Dict[str, Any]:
    path = repository_root() / _COURSE_MANIFEST
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogError("cannot load Academy course manifest: {}".format(exc)) from exc
    labs = payload.get("labs") if isinstance(payload, dict) else None
    if not isinstance(labs, list):
        raise CatalogError("Academy course manifest must contain a labs list")
    return payload


def _resolve_course_lab(selector: str) -> Dict[str, Any]:
    normalized = selector.zfill(2) if selector.isdigit() else selector
    for lab in _load_course_manifest()["labs"]:
        if not isinstance(lab, dict):
            continue
        if normalized in (lab.get("id"), lab.get("directory")):
            return lab
    raise CatalogError("unknown Academy course selector: {!r}".format(selector))


def _course_scenario_ids() -> set[str]:
    ids: set[str] = set()
    for lab in _load_course_manifest()["labs"]:
        for ref in lab.get("scenario_refs", ()):
            scenario_id = ref.get("scenario_id") if isinstance(ref, dict) else None
            if isinstance(scenario_id, str):
                ids.add(scenario_id)
    return ids


def _run_recorded_lab(lab: Dict[str, Any], *, timeout: float, json_output: bool) -> int:
    root = repository_root()
    directory = lab.get("directory")
    if not isinstance(directory, str) or not directory:
        raise CatalogError("Academy lab needs a directory")
    demo = (root / "academy" / "labs" / directory / "demo.py").resolve()
    try:
        demo.relative_to(root.resolve())
    except ValueError as exc:
        raise CatalogError("Academy demo escapes the repository") from exc
    if not demo.is_file():
        raise CatalogError("Academy demo does not exist: {}".format(demo))

    recorded_env = {
        name: value
        for name, value in os.environ.items()
        if not _SECRET_NAME_RE.search(name)
    }
    recorded_env["PYTHONUTF8"] = "1"
    try:
        completed = subprocess.run(
            [sys.executable, str(demo), "--mode", "recorded"],
            cwd=str(root),
            env=recorded_env,
            timeout=timeout,
            check=False,
            capture_output=json_output,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        _emit_json(
            {
                "status": "timeout",
                "course": lab.get("id"),
                "mode": "recorded",
                "timeout_seconds": timeout,
                "stdout": _redact_text(exc.stdout) if json_output else "",
                "stderr": _redact_text(exc.stderr) if json_output else "",
            }
        )
        return 124

    if json_output:
        _emit_json(
            {
                "status": "passed" if completed.returncode == 0 else "failed",
                "course": lab.get("id"),
                "mode": "recorded",
                "exit_code": completed.returncode,
                "stdout": _redact_text(completed.stdout),
                "stderr": _redact_text(completed.stderr),
            }
        )
    return completed.returncode


def _course_command(args: argparse.Namespace, catalog: Catalog) -> int:
    lab = _resolve_course_lab(args.selector)
    if args.mode == "recorded":
        if args.example is not None:
            raise CatalogError("--example is only valid with --mode live")
        recorded_timeout = 120.0 if args.timeout is None else args.timeout
        if not math.isfinite(recorded_timeout) or recorded_timeout <= 0:
            raise ValueError("timeout must be a finite number greater than zero")
        return _run_recorded_lab(
            lab, timeout=recorded_timeout, json_output=args.json
        )

    refs = lab.get("scenario_refs")
    if not isinstance(refs, list) or not refs:
        raise CatalogError("Academy lab {} has no scenario_refs".format(lab.get("id")))
    selected = None
    if args.example is not None:
        selected = next(
            (ref for ref in refs if isinstance(ref, dict) and ref.get("alias") == args.example),
            None,
        )
        if selected is None:
            aliases = sorted(
                ref.get("alias") for ref in refs if isinstance(ref, dict) and ref.get("alias")
            )
            raise CatalogError(
                "Academy lab {} has no live example {!r}; choose one of {}".format(
                    lab.get("id"), args.example, aliases
                )
            )
    else:
        primary = [
            ref for ref in refs if isinstance(ref, dict) and ref.get("role") == "primary"
        ]
        if len(primary) != 1:
            raise CatalogError(
                "Academy lab {} must have exactly one primary scenario".format(lab.get("id"))
            )
        selected = primary[0]

    scenario_id = selected.get("scenario_id")
    if not isinstance(scenario_id, str):
        raise CatalogError("Academy scenario reference needs scenario_id")
    return run_scenario(
        catalog.resolve(scenario_id),
        timeout=args.timeout,
        allow_quarantined=args.allow_quarantined,
        json_output=args.json,
    )


def _select(
    catalog: Catalog, tiers: Sequence[str], maturities: Sequence[str]
) -> Iterable[Scenario]:
    for scenario in catalog:
        if tiers and scenario.tier not in tiers:
            continue
        if maturities and scenario.maturity not in maturities:
            continue
        yield scenario


def _list_command(args: argparse.Namespace, catalog: Catalog) -> int:
    scenarios = list(_select(catalog, args.tier, args.maturity))
    if args.course == "academy":
        course_ids = _course_scenario_ids()
        scenarios = [scenario for scenario in scenarios if scenario.id in course_ids]
    if args.json:
        _emit_json([scenario.to_dict() for scenario in scenarios])
        return 0
    print("{:<36} {:<12} {:<8} {:<10} {}".format(
        "ID", "TIER", "MATURITY", "STATUS", "LEGACY PATH"
    ))
    for scenario in scenarios:
        print("{:<36} {:<12} {:<8} {:<10} {}".format(
            scenario.id,
            scenario.tier,
            scenario.maturity,
            scenario.status,
            scenario.legacy_path,
        ))
    print("\n{} scenario(s)".format(len(scenarios)))
    return 0


def _describe_command(args: argparse.Namespace, catalog: Catalog) -> int:
    scenario = catalog.resolve(args.selector)
    if args.json:
        _emit_json(scenario.to_dict())
        return 0
    print("{} — {}".format(scenario.id, scenario.title))
    print("tier={} maturity={} status={}".format(
        scenario.tier, scenario.maturity, scenario.status
    ))
    print("legacy_path={}".format(scenario.legacy_path))
    print("aliases={}".format(", ".join(scenario.aliases)))
    if scenario.duplicate_of:
        print("duplicate_of={}".format(scenario.duplicate_of))
    print("proves:")
    for claim in scenario.proves:
        print("  - {}".format(claim))
    print("does_not_prove:")
    for claim in scenario.does_not_prove:
        print("  - {}".format(claim))
    return 0


def _doctor_command(args: argparse.Namespace, catalog: Catalog) -> int:
    scenarios = [catalog.resolve(args.selector)] if args.selector else list(catalog)
    reports = [inspect_requirements(scenario) for scenario in scenarios]
    if args.json:
        _emit_json(
            {
                "status": "ready"
                if all(report["ready"] for report in reports)
                else "not-ready",
                "reports": reports,
            }
        )
    else:
        for report in reports:
            label = "READY" if report["ready"] else "NOT READY"
            print("{:<10} {}".format(label, report["scenario_id"]))
            for reason in _skip_reasons(report):
                print("  - {}".format(json.dumps(reason, ensure_ascii=False, sort_keys=True)))
            services = report["services"]["declared"]
            if services:
                print("  - services declared, not probed: {}".format(", ".join(services)))
    return 0 if all(report["ready"] for report in reports) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m academy.scenarios",
        description="Inspect and run Senza's unified scenario catalog.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list catalog scenarios")
    list_parser.add_argument(
        "--tier",
        action="append",
        choices=("core", "advanced", "external", "quarantined"),
        default=[],
    )
    list_parser.add_argument(
        "--maturity",
        action="append",
        choices=("stable", "partial", "gap"),
        default=[],
    )
    list_parser.add_argument("--course", choices=("academy",))
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(handler=_list_command)

    describe_parser = subparsers.add_parser("describe", help="describe one scenario")
    describe_parser.add_argument("selector")
    describe_parser.add_argument("--json", action="store_true")
    describe_parser.set_defaults(handler=_describe_command)

    run_parser = subparsers.add_parser("run", help="run one legacy implementation")
    run_parser.add_argument("selector")
    run_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="override the catalog timeout budget",
    )
    run_parser.add_argument("--allow-quarantined", action="store_true")
    run_parser.add_argument("--json", action="store_true")
    run_parser.set_defaults(handler=None)

    doctor_parser = subparsers.add_parser("doctor", help="check explicit prerequisites")
    doctor_parser.add_argument("selector", nargs="?")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(handler=_doctor_command)

    course_parser = subparsers.add_parser(
        "course", help="run one Academy lesson through the same scenario entry point"
    )
    course_parser.add_argument("selector", help="Lab number or directory name")
    course_parser.add_argument("--mode", choices=("recorded", "live"), default="recorded")
    course_parser.add_argument("--example", help="live alias from course_manifest.json")
    course_parser.add_argument("--timeout", type=float, default=None, metavar="SECONDS")
    course_parser.add_argument("--allow-quarantined", action="store_true")
    course_parser.add_argument("--json", action="store_true")
    course_parser.set_defaults(handler=_course_command)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog()
        if args.command == "run":
            scenario = catalog.resolve(args.selector)
            return run_scenario(
                scenario,
                timeout=args.timeout,
                allow_quarantined=args.allow_quarantined,
                json_output=args.json,
            )
        if args.command == "course":
            return _course_command(args, catalog)
        return args.handler(args, catalog)
    except (CatalogError, ValueError) as exc:
        _emit_json({"status": "error", "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
