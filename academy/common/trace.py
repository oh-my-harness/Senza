"""Recorded-trace contract for stable, provider-free Academy demonstrations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

MATURITY_LEVELS = {"stable", "teaching", "preview"}
EVENT_KINDS = {
    "agent",
    "context",
    "eval",
    "hook",
    "knowledge",
    "memory",
    "model",
    "proposal",
    "tool",
    "user",
    "workflow",
}
EVENT_STATUSES = {
    "accepted",
    "denied",
    "failed",
    "info",
    "modified",
    "ok",
    "passed",
    "paused",
    "preview",
}


def load_trace(path: Union[str, Path]) -> dict[str, Any]:
    """Load and validate one Academy trace JSON document."""

    trace_path = Path(path)
    with trace_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_trace(payload, source=trace_path)
    return payload


def validate_trace(
    payload: dict[str, Any], source: Union[str, Path] = "<memory>"
) -> None:
    """Raise ``ValueError`` when a recorded trace violates the course contract."""

    label = str(source)
    required_text = ("lab", "title", "maturity", "theory", "runtime_mapping")
    for field in required_text:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label}: {field!r} must be a non-empty string")

    maturity = payload["maturity"]
    if maturity not in MATURITY_LEVELS:
        raise ValueError(
            f"{label}: maturity must be one of {sorted(MATURITY_LEVELS)}, got {maturity!r}"
        )

    for field in ("claims", "boundaries", "live_examples"):
        values = payload.get(field)
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            raise ValueError(f"{label}: {field!r} must be a list of non-empty strings")

    if not payload["claims"]:
        raise ValueError(f"{label}: at least one verifiable claim is required")
    if not payload["boundaries"]:
        raise ValueError(f"{label}: at least one capability boundary is required")

    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError(f"{label}: events must be a non-empty list")

    expected_sequence = list(range(1, len(events) + 1))
    actual_sequence = [event.get("seq") for event in events if isinstance(event, dict)]
    if actual_sequence != expected_sequence:
        raise ValueError(
            f"{label}: event seq values must be consecutive from 1; got {actual_sequence!r}"
        )

    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            raise ValueError(f"{label}: event {index} must be an object")
        for field in ("kind", "actor", "summary", "status"):
            value = event.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label}: event {index} field {field!r} is required")
        if event["kind"] not in EVENT_KINDS:
            raise ValueError(
                f"{label}: event {index} kind must be one of {sorted(EVENT_KINDS)}"
            )
        if event["status"] not in EVENT_STATUSES:
            raise ValueError(
                f"{label}: event {index} status must be one of {sorted(EVENT_STATUSES)}"
            )


def render_trace(payload: dict[str, Any]) -> str:
    """Render a validated trace as a compact classroom timeline."""

    validate_trace(payload)
    lines = [
        f"{payload['lab']} — {payload['title']}",
        f"Maturity: {payload['maturity']}",
        f"Theory: {payload['theory']}",
        f"Runtime mapping: {payload['runtime_mapping']}",
        "",
        "Timeline",
    ]
    for event in payload["events"]:
        lifecycle = event.get("lifecycle")
        lifecycle_suffix = f" | {lifecycle}" if lifecycle else ""
        lines.append(
            f"[{event['seq']:02d}] {event['kind'].upper():9} "
            f"{event['actor']} — {event['summary']} "
            f"[{event['status']}]{lifecycle_suffix}"
        )

    lines.extend(["", "Claims proved by this lab"])
    lines.extend(f"- {claim}" for claim in payload["claims"])
    lines.extend(["", "Capability boundaries"])
    lines.extend(f"- {boundary}" for boundary in payload["boundaries"])
    if payload["live_examples"]:
        lines.extend(["", "Canonical live examples"])
        lines.extend(f"- {example}" for example in payload["live_examples"])
    return "\n".join(lines)
