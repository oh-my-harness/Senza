"""Strict loader for the Senza scenario catalog.

Only Python's standard library is used so the catalog remains inspectable in a
fresh Python 3.9 checkout.  Validation is deliberately stricter than JSON
Schema alone: paths must stay inside the repository, aliases cannot shadow an
ID, every target must exist, and every numbered legacy example must be listed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = 1
CATALOG_PATH = Path(__file__).with_name("catalog.json")
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_ENV_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_TIERS = frozenset(("core", "advanced", "external", "quarantined"))
_MATURITIES = frozenset(("stable", "partial", "gap"))
_STATUSES = frozenset(("active", "needs-fix", "duplicate"))
_PLATFORMS = frozenset(("any", "darwin", "linux", "win32"))


class CatalogError(ValueError):
    """Raised when catalog content violates the repository contract."""


def repository_root() -> Path:
    """Return the repository root without consulting process cwd."""

    return Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class Scenario:
    """An immutable, validated scenario record."""

    id: str
    aliases: Tuple[str, ...]
    legacy_path: str
    title: str
    tier: str
    maturity: str
    status: str
    requirements: Mapping[str, Any]
    proves: Tuple[str, ...]
    does_not_prove: Tuple[str, ...]
    duplicate_of: Optional[str]
    timeout_seconds: int
    _raw: Mapping[str, Any]

    @property
    def raw(self) -> Mapping[str, Any]:
        """Return a read-only view of the original JSON object."""

        return self._raw

    @property
    def target(self) -> Path:
        """Revalidate and return the absolute legacy script path."""

        root = repository_root().resolve()
        target = (root / Path(self.legacy_path)).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise CatalogError(
                "{}: legacy target now escapes the repository".format(self.id)
            ) from exc
        if not target.is_file():
            raise CatalogError(
                "{}: legacy target is no longer a file".format(self.id)
            )
        return target

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable copy of this record."""

        return dict(self._raw)


class Catalog(Sequence[Scenario]):
    """Validated scenarios with stable ID and alias lookup."""

    def __init__(self, scenarios: Sequence[Scenario]) -> None:
        self._scenarios = tuple(scenarios)
        lookup: Dict[str, Scenario] = {}
        for scenario in self._scenarios:
            for selector in (scenario.id, scenario.legacy_path, *scenario.aliases):
                lookup[selector] = scenario
        self._lookup = MappingProxyType(lookup)

    def __len__(self) -> int:
        return len(self._scenarios)

    def __getitem__(self, index):  # type: ignore[no-untyped-def]
        return self._scenarios[index]

    def __iter__(self) -> Iterator[Scenario]:
        return iter(self._scenarios)

    def resolve(self, selector: str) -> Scenario:
        """Resolve a stable ID, alias, or exact legacy path."""

        try:
            return self._lookup[selector]
        except KeyError as exc:
            raise CatalogError("unknown scenario selector: {!r}".format(selector)) from exc


def _expect_string(record: Mapping[str, Any], field: str, owner: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CatalogError("{}: {} must be a non-empty string".format(owner, field))
    return value


def _expect_string_list(
    record: Mapping[str, Any], field: str, owner: str, *, allow_empty: bool = True
) -> Tuple[str, ...]:
    value = record.get(field)
    if not isinstance(value, list) or (not allow_empty and not value):
        raise CatalogError("{}: {} must be a{} string list".format(
            owner, field, " non-empty" if not allow_empty else ""
        ))
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise CatalogError("{}: {} contains a non-string or empty item".format(owner, field))
    if len(value) != len(set(value)):
        raise CatalogError("{}: {} contains duplicates".format(owner, field))
    return tuple(value)


def _validate_path(root: Path, legacy_path: str, owner: str) -> Path:
    relative = Path(legacy_path)
    if relative.is_absolute():
        raise CatalogError("{}: legacy_path must be repository-relative".format(owner))
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise CatalogError("{}: legacy_path escapes the repository".format(owner)) from exc
    if not target.is_file():
        raise CatalogError("{}: target does not exist: {}".format(owner, legacy_path))
    if target.suffix != ".py":
        raise CatalogError("{}: target must be a Python file".format(owner))
    return target


def _validate_requirements(
    requirements: Any, owner: str
) -> Mapping[str, Any]:
    if not isinstance(requirements, dict):
        raise CatalogError("{}: requirements must be an object".format(owner))
    expected = {"provider", "env", "commands", "services", "platforms"}
    if set(requirements) != expected:
        raise CatalogError(
            "{}: requirements keys must be exactly {}".format(owner, sorted(expected))
        )

    provider = requirements["provider"]
    if not isinstance(provider, dict) or set(provider) != {"required", "any_of_env"}:
        raise CatalogError(
            "{}: requirements.provider needs required and any_of_env".format(owner)
        )
    if not isinstance(provider["required"], bool):
        raise CatalogError("{}: provider.required must be boolean".format(owner))
    provider_env = provider["any_of_env"]
    if not isinstance(provider_env, list) or any(
        not isinstance(name, str) or not _ENV_RE.fullmatch(name) for name in provider_env
    ):
        raise CatalogError("{}: provider.any_of_env has an invalid env name".format(owner))
    if provider["required"] and not provider_env:
        raise CatalogError("{}: a required provider needs any_of_env".format(owner))

    env = _expect_string_list(requirements, "env", owner)
    if any(not _ENV_RE.fullmatch(name) for name in env):
        raise CatalogError("{}: requirements.env has an invalid name".format(owner))
    _expect_string_list(requirements, "commands", owner)
    _expect_string_list(requirements, "services", owner)
    platforms = _expect_string_list(requirements, "platforms", owner, allow_empty=False)
    if any(name not in _PLATFORMS for name in platforms):
        raise CatalogError("{}: requirements.platforms has an invalid value".format(owner))
    if "any" in platforms and len(platforms) != 1:
        raise CatalogError("{}: platform 'any' cannot be combined".format(owner))
    return MappingProxyType(requirements)


def _validate_scenario(
    value: Any, index: int, root: Path
) -> Scenario:
    owner = "scenarios[{}]".format(index)
    if not isinstance(value, dict):
        raise CatalogError("{} must be an object".format(owner))
    required = {
        "id",
        "aliases",
        "legacy_path",
        "title",
        "tier",
        "maturity",
        "status",
        "requirements",
        "proves",
        "does_not_prove",
    }
    optional = {"duplicate_of", "timeout_seconds"}
    missing = required - set(value)
    extra = set(value) - required - optional
    if missing or extra:
        raise CatalogError(
            "{}: fields mismatch (missing={}, extra={})".format(
                owner, sorted(missing), sorted(extra)
            )
        )

    scenario_id = _expect_string(value, "id", owner)
    if not _ID_RE.fullmatch(scenario_id):
        raise CatalogError("{}: invalid semantic id {!r}".format(owner, scenario_id))
    aliases = _expect_string_list(value, "aliases", owner, allow_empty=False)
    legacy_path = _expect_string(value, "legacy_path", owner)
    if "\\" in legacy_path:
        raise CatalogError("{}: legacy_path must use POSIX separators".format(owner))
    _validate_path(root, legacy_path, owner)
    title = _expect_string(value, "title", owner)
    tier = _expect_string(value, "tier", owner)
    maturity = _expect_string(value, "maturity", owner)
    status = _expect_string(value, "status", owner)
    if tier not in _TIERS:
        raise CatalogError("{}: invalid tier {!r}".format(owner, tier))
    if maturity not in _MATURITIES:
        raise CatalogError("{}: invalid maturity {!r}".format(owner, maturity))
    if status not in _STATUSES:
        raise CatalogError("{}: invalid status {!r}".format(owner, status))
    requirements = _validate_requirements(value["requirements"], owner)
    proves = _expect_string_list(value, "proves", owner, allow_empty=False)
    does_not_prove = _expect_string_list(value, "does_not_prove", owner, allow_empty=False)
    duplicate_of = value.get("duplicate_of")
    if duplicate_of is not None and (
        not isinstance(duplicate_of, str) or not _ID_RE.fullmatch(duplicate_of)
    ):
        raise CatalogError("{}: duplicate_of must be a semantic id".format(owner))
    if status == "duplicate" and duplicate_of is None:
        raise CatalogError("{}: duplicate status needs duplicate_of".format(owner))
    if status != "duplicate" and duplicate_of is not None:
        raise CatalogError("{}: only duplicate entries may have duplicate_of".format(owner))

    timeout_seconds = value.get("timeout_seconds", 120)
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, int)
        or timeout_seconds <= 0
    ):
        raise CatalogError("{}: timeout_seconds must be a positive integer".format(owner))

    raw = MappingProxyType(dict(value))
    return Scenario(
        id=scenario_id,
        aliases=aliases,
        legacy_path=legacy_path,
        title=title,
        tier=tier,
        maturity=maturity,
        status=status,
        requirements=requirements,
        proves=proves,
        does_not_prove=does_not_prove,
        duplicate_of=duplicate_of,
        timeout_seconds=timeout_seconds,
        _raw=raw,
    )


def _validate_uniqueness(scenarios: Sequence[Scenario]) -> None:
    selectors: Dict[str, str] = {}
    ids = {scenario.id for scenario in scenarios}
    for scenario in scenarios:
        for selector in (scenario.id, scenario.legacy_path, *scenario.aliases):
            previous = selectors.get(selector)
            if previous is not None:
                raise CatalogError(
                    "selector {!r} is shared by {} and {}".format(
                        selector, previous, scenario.id
                    )
                )
            selectors[selector] = scenario.id
        if scenario.duplicate_of is not None:
            if scenario.duplicate_of == scenario.id:
                raise CatalogError("{} duplicates itself".format(scenario.id))
            if scenario.duplicate_of not in ids:
                raise CatalogError(
                    "{} duplicates missing scenario {}".format(
                        scenario.id, scenario.duplicate_of
                    )
                )


def _validate_legacy_coverage(root: Path, scenarios: Sequence[Scenario]) -> None:
    directory = root / "live-tests" / "examples"
    discovered = {
        path.relative_to(root).as_posix()
        for path in directory.glob("[0-9][0-9]_*.py")
        if path.is_file()
    }
    registered = {scenario.legacy_path for scenario in scenarios}
    if discovered != registered:
        raise CatalogError(
            "catalog/legacy coverage mismatch (missing={}, stale={})".format(
                sorted(discovered - registered), sorted(registered - discovered)
            )
        )


def load_catalog(path: Path = CATALOG_PATH) -> Catalog:
    """Load and fully validate ``catalog.json``.

    Supplying a path is intended for tests and tooling.  Legacy targets are
    still constrained to this package's repository root.
    """

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogError("cannot load catalog {}: {}".format(path, exc)) from exc
    if not isinstance(document, dict) or set(document) != {"schema_version", "scenarios"}:
        raise CatalogError("catalog must contain exactly schema_version and scenarios")
    if document["schema_version"] != SCHEMA_VERSION:
        raise CatalogError(
            "unsupported schema_version {!r}; expected {}".format(
                document["schema_version"], SCHEMA_VERSION
            )
        )
    values = document["scenarios"]
    if not isinstance(values, list):
        raise CatalogError("scenarios must be a list")
    root = repository_root().resolve()
    scenarios = [_validate_scenario(value, index, root) for index, value in enumerate(values)]
    _validate_uniqueness(scenarios)
    _validate_legacy_coverage(root, scenarios)
    return Catalog(scenarios)
