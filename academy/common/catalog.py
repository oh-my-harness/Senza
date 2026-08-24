"""Resolve Academy live lessons through the repository scenario catalog."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


ACADEMY_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ACADEMY_ROOT.parent
COURSE_MANIFEST_PATH = ACADEMY_ROOT / "course_manifest.json"
SCENARIO_CATALOG_PATH = ACADEMY_ROOT / "scenarios" / "catalog.json"


@dataclass(frozen=True)
class CourseLiveExample:
    """One course alias bound to a stable catalog scenario."""

    alias: str
    scenario_id: str
    role: str
    legacy_path: str

    @property
    def filename(self) -> str:
        """Return the historical filename exposed by Academy demo modules."""

        return PurePosixPath(self.legacy_path).name


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required catalog file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return payload


def _course_labs() -> list[dict[str, Any]]:
    payload = _load_json(COURSE_MANIFEST_PATH)
    labs = payload.get("labs")
    if not isinstance(labs, list):
        raise ValueError(f"{COURSE_MANIFEST_PATH}: 'labs' must be a list")
    return labs


def _catalog_scenarios() -> dict[str, dict[str, Any]]:
    payload = _load_json(SCENARIO_CATALOG_PATH)
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError(f"{SCENARIO_CATALOG_PATH}: 'scenarios' must be a list")

    by_id: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise ValueError(f"{SCENARIO_CATALOG_PATH}: every scenario must be an object")
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ValueError(f"{SCENARIO_CATALOG_PATH}: scenario id must be non-empty")
        if scenario_id in by_id:
            raise ValueError(f"{SCENARIO_CATALOG_PATH}: duplicate scenario id {scenario_id!r}")
        by_id[scenario_id] = scenario
    return by_id


def _normalize_lab_id(lab_id: str) -> str:
    value = str(lab_id).strip()
    return value.zfill(2) if value.isdigit() else value


def course_live_examples(lab_id: str) -> tuple[CourseLiveExample, ...]:
    """Resolve a Lab's manifest references against the canonical catalog."""

    normalized_id = _normalize_lab_id(lab_id)
    lab = next(
        (candidate for candidate in _course_labs() if candidate.get("id") == normalized_id),
        None,
    )
    if lab is None:
        raise KeyError(f"unknown Academy lab: {lab_id!r}")

    refs = lab.get("scenario_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError(
            f"{COURSE_MANIFEST_PATH}: lab {normalized_id} needs scenario_refs"
        )

    scenarios = _catalog_scenarios()
    resolved: list[CourseLiveExample] = []
    aliases: set[str] = set()
    for ref in refs:
        if not isinstance(ref, dict):
            raise ValueError(
                f"{COURSE_MANIFEST_PATH}: lab {normalized_id} scenario ref must be an object"
            )
        alias = ref.get("alias")
        scenario_id = ref.get("scenario_id")
        role = ref.get("role")
        if not all(
            isinstance(value, str) and value
            for value in (alias, scenario_id, role)
        ):
            raise ValueError(
                f"{COURSE_MANIFEST_PATH}: lab {normalized_id} scenario ref needs "
                "alias, scenario_id, and role"
            )
        if alias in aliases:
            raise ValueError(
                f"{COURSE_MANIFEST_PATH}: lab {normalized_id} duplicates alias {alias!r}"
            )
        aliases.add(alias)

        scenario = scenarios.get(scenario_id)
        if scenario is None:
            raise KeyError(
                f"{COURSE_MANIFEST_PATH}: lab {normalized_id} references unknown "
                f"scenario {scenario_id!r}"
            )
        legacy_path = scenario.get("legacy_path")
        if not isinstance(legacy_path, str) or not legacy_path:
            raise ValueError(
                f"{SCENARIO_CATALOG_PATH}: scenario {scenario_id!r} needs legacy_path"
            )
        resolved.append(
            CourseLiveExample(
                alias=alias,
                scenario_id=scenario_id,
                role=role,
                legacy_path=legacy_path,
            )
        )
    return tuple(resolved)


def live_examples_for_lab(lab_id: str) -> dict[str, str]:
    """Return the legacy ``alias -> filename`` view used by existing Lab CLIs."""

    return {example.alias: example.filename for example in course_live_examples(lab_id)}


def _run_scenario(scenario_id: str) -> None:
    try:
        subprocess.run(
            [sys.executable, "-m", "academy.scenarios", "run", scenario_id],
            cwd=REPOSITORY_ROOT,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from None


def run_course_live(lab_id: str, alias: str = "default") -> None:
    """Run one Academy live alias through the unified scenario runner.

    Omitting ``alias`` selects the manifest's single primary reference. Labs
    whose historical CLI already used ``default`` continue to resolve that
    literal alias.
    """

    examples = {example.alias: example for example in course_live_examples(lab_id)}
    if alias == "default" and alias not in examples:
        primary = [example for example in examples.values() if example.role == "primary"]
        if len(primary) == 1:
            _run_scenario(primary[0].scenario_id)
            return
    try:
        selected = examples[alias]
    except KeyError as error:
        raise KeyError(
            f"lab {_normalize_lab_id(lab_id)} has no live alias {alias!r}; "
            f"choose one of {sorted(examples)}"
        ) from error
    _run_scenario(selected.scenario_id)


def run_legacy_live_example(filename: str) -> None:
    """Resolve an old plain filename and delegate it to the unified runner."""

    if Path(filename).name != filename or not filename.endswith(".py"):
        raise ValueError("live example must be a plain .py filename")

    matches: list[str] = []
    for scenario_id, scenario in _catalog_scenarios().items():
        legacy_path = scenario.get("legacy_path")
        if isinstance(legacy_path, str) and PurePosixPath(legacy_path).name == filename:
            matches.append(scenario_id)

    if not matches:
        raise FileNotFoundError(
            f"canonical live example not found in scenario catalog: {filename}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"legacy live example {filename!r} is ambiguous: {sorted(matches)}"
        )
    _run_scenario(matches[0])
