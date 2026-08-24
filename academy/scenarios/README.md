# Senza Scenario Catalog

This directory is the additive migration layer that gives the existing
`live-tests/examples/` scripts stable semantic IDs and one runner. The legacy
files remain the executable source of truth in P1; the catalog does not copy or
import them.

```bash
python -m academy.scenarios list
python -m academy.scenarios describe agent.tool_calling
python -m academy.scenarios doctor agent.tool_calling
python -m academy.scenarios run agent.tool_calling --timeout 120
python -m academy.scenarios list --course academy
python -m academy.scenarios course 01 --mode recorded
python -m academy.scenarios course 04 --mode live --example skills
```

Use `--json` on any command for machine-readable output. A non-quarantined
provider scenario without an explicit `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
returns a structured `skipped` result and exit code 0. The runner never loads
`~/.omp_llm_env`; requirement reports expose variable names and readiness only,
never their values. JSON run output also redacts credential-shaped values.
Quarantined scenarios are refused first unless `--allow-quarantined` is present.

`run` starts the catalog's `legacy_path` with the current Python executable in
a subprocess whose working directory is the repository root. It deliberately
does not use `runpy`, so each existing script keeps normal script semantics.
If `--timeout` is omitted, the runner uses the scenario's catalog budget
(120 seconds by default; longer for compaction, spawn, HITL, budget, and replay).

`course` reads `academy/course_manifest.json`. Recorded mode runs the Lab's
deterministic demo without credential-shaped environment variables; live mode
resolves the selected Lab alias to the same catalog entry used by `run`.

The loader enforces more than the companion JSON Schema: IDs and aliases are
globally unique, paths cannot escape the repository, targets must exist, and
the catalog must cover every numbered script in `live-tests/examples/` exactly
once.
