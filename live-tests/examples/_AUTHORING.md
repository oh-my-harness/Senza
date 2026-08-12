# Senza live-tests examples — subagent authoring conventions

You are writing Python example files for `Senza/live-tests/examples/`. Repo root: `/Users/hhl/Documents/projs/oh-my-harness/Senza`.

## Hard rules
- Write ONLY the one file assigned. Do NOT create/delete any other file. Do NOT run `git`, lint, formatters, or any project-wide build/test (the main agent runs those).
- Do NOT invent API. Verify every signature against `senza-pkg/senza/__init__.pyi` (and `senza-pkg/senza/__init__.py`) and, when a number is given, the reference file. If an API from the runtime example does NOT exist in Senza's Python surface, write the example as a concise feature-gap note + nearest available analog (see `11_spawn_subagent.py`, `10_sandbox.py` for the pattern already used).
- Import from `_common` (already provides sys.path bootstrap + re-exports): `from _common import live_model, make_example_harness, require_provider, run_prompt, text_of, with_timeout`. Do NOT import `base` directly in the example body.
- No key = behave gracefully: call `require_provider()` (prints SKIP + exit 0) at the start of `main()`.
- Structure: module docstring (mirror "NN — Title", "Mirrors runtime `NN_x.rs`" or "原仓库根 examples/..."), then `main()`, guarded by `if __name__ == "__main__": main()`.
- Real LLM prompts against DeepSeek-V4-Flash; weak assertions (print output + small verification); each turn via `run_prompt(harness, text, timeout_ms=60_000)` unless longer.
- Docstring follows the exact style of `01_prompt_streaming.py`.

## Reference templates to read first
- `live-tests/examples/_common.py` (helpers + re-exports)
- `live-tests/examples/01_prompt_streaming.py` (streaming, canonical structure)
- `live-tests/examples/07_hooks.py` (tool + hooks; shows `create_tool`, `.tool()`, `.hooks()`)
- `live-tests/examples/10_sandbox.py` and `11_spawn_subagent.py` (feature-gap pattern)
- Senza API reference: `docs/api-reference.md`; stubs: `senza-pkg/senza/__init__.pyi`

## Key Senza API facts (verified)
- Provider/model: default OMP DeepSeek via `_common`. `require_provider()` gates key.
- Harness: `make_example_harness(customize)` where customize is `lambda b: b...`; builder methods include `.system_prompt(s)`, `.max_tokens(n)`, `.temperature(f)`, `.tool(t)`, `.tools([...])`, `.hooks([...])`, `.skills([...])`, `.plugin(p)`, `.env(e)`, `.set_model` (runtime method), `.model_info(ctx, max)`, `.auto_compact(bool)` etc.
- Event dict types: agent_start/end, turn_start/end, tool_call_start/end, text_delta, settled/aborted/error. `senza.extract_text(events)`, `senza.stream_prompt(obj, text, timeout_ms)`.
- Tools: `senza.create_tool(name, description, parameters_schema=json-str, callback=(args,ctx)->{"content":[...],"terminate":bool})`. Return for tool callbacks: dict with "content" list of {"type":"text","text":...}.
- Hooks: `senza.hooks.before_turn(cb)` etc. `before_tool_call` cb must return `"allow"`; `after_tool_call` cb must return `"passthrough"`.
- WorkflowEngine: `senza.WorkflowEngine(wf_dict, provider, model, judge)`, `.with_task_store(dir)`, `.with_tool(t)`, `.with_executor(name, ex)`, `.run()`, `.state()`, `.step_history()`, `.task_id()`, static `.restore(dir, task_id, provider, model, judge)`. `senza.create_judge(cb)` where cb(ctx)->"to:X" or "done"; `senza.create_executor(cb)`, `senza.create_shell_executor([cmds])`, `senza.create_http_executor([hosts])`, `senza.create_composite_judge()` + `.on(step, cb)`.
- Strategy plugins (factories, verify in pyi `senza.strategy.*`): safety_defaults(), loop_safety(), status_panel(), memory_defense(), injection_filter(), source_tag([..]), project_instruction(), audit(sink_path=, trace_id=, task_id=), notify(...), tool_output_guard(env), webhook_stream(buffer). Plugins attach via `.plugin(p)`.
- Knowledge: `senza.knowledge.local_source(path, source_id)`, `.plugin(sources=[...])`.
- Infra: `senza.infra.seatbelt_sandbox()`, `senza.create_os_env(working_dir=".")`, `senza.infra.jsonl_audit_sink`, `senza.JsonlAuditSink.validate(path)`, `senza.infra.in_memory_trace_exporter`.
- File numbering: exact filename given in the assignment. Write file at `live-tests/examples/<NAME>`.

Return in your final message: the filename(s) written + any feature-gap you documented + one line on what the example demonstrates.
