"""Lab 03: execute a provider-free DB guard or delegate to the live Plugin demo."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Optional, Union


LAB_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = LAB_DIR.parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from academy.common import load_trace, render_trace, run_live_example  # noqa: E402


RECORDED_SCENARIOS = (
    {
        "name": "bounded-select",
        "tool_name": "run_query",
        "args": {"sql": "SELECT id, email FROM users LIMIT 5"},
    },
    {
        "name": "unbounded-select",
        "tool_name": "run_query",
        "args": {"sql": "SELECT id, email FROM users"},
    },
    {
        "name": "destructive-statement",
        "tool_name": "run_query",
        "args": {"sql": "DROP TABLE users"},
    },
)


def db_guard(tool_name: str, args: dict[str, Any]) -> Union[str, dict[str, Any]]:
    """Return the current before_tool_call allow/modify/deny decision shapes."""

    if tool_name != "run_query":
        return "allow"

    sql = str(args.get("sql", "")).strip()
    if not re.match(r"^SELECT\b", sql, flags=re.IGNORECASE):
        return {
            "action": "deny",
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "Query denied by db-safety: only SELECT is permitted.",
                    }
                ],
                "details": {"reason": "non_read_only_sql", "sql": sql},
            },
        }

    if not re.search(r"\bLIMIT\s+\d+\b", sql, flags=re.IGNORECASE):
        modified_args = dict(args)
        modified_args["sql"] = f"{sql.rstrip().rstrip(';')} LIMIT 100"
        return {"action": "modify", "args": modified_args}

    return "allow"


def decision_action(decision: Union[str, dict[str, Any]]) -> str:
    """Normalize a hook decision to its action name for display and tests."""

    return decision if isinstance(decision, str) else str(decision["action"])


def execute_recorded_scenarios() -> tuple[list[dict[str, Any]], list[str]]:
    """Call the real pure-Python guard and simulate executor admission."""

    records: list[dict[str, Any]] = []
    executed_queries: list[str] = []

    for scenario in RECORDED_SCENARIOS:
        requested_args = dict(scenario["args"])
        decision = db_guard(str(scenario["tool_name"]), requested_args)
        action = decision_action(decision)

        effective_sql: Optional[str] = None
        if action == "allow":
            effective_sql = str(requested_args["sql"])
        elif action == "modify":
            effective_sql = str(decision["args"]["sql"])

        if effective_sql is not None:
            executed_queries.append(effective_sql)

        records.append(
            {
                "name": scenario["name"],
                "requested_sql": requested_args["sql"],
                "action": action,
                "effective_sql": effective_sql,
                "executed": effective_sql is not None,
            }
        )

    return records, executed_queries


def run_recorded() -> None:
    records, executed_queries = execute_recorded_scenarios()
    actions = [record["action"] for record in records]
    if actions != ["allow", "modify", "deny"]:
        raise RuntimeError(f"recorded guard drifted: {actions!r}")

    print("Recorded DB guard execution (pure Python)\n")
    for record in records:
        effective = record["effective_sql"] or "<blocked before executor>"
        print(
            f"[{record['action']:<6}] {record['name']}: "
            f"{record['requested_sql']} -> {effective}"
        )
    print(f"\nExecutor received {len(executed_queries)} queries: {executed_queries}\n")

    trace = load_trace(LAB_DIR / "expected_trace.json")
    print(render_trace(trace))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("recorded", "live"),
        default="recorded",
        help="recorded is provider-free; live delegates to 32_plugins.py",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    if args.mode == "live":
        run_live_example("32_plugins.py")
        return
    run_recorded()


if __name__ == "__main__":
    main()
