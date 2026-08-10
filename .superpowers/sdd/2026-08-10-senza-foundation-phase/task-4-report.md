# Task 4 Report: Expose compaction_prompt / compaction_query setters

## Status: DONE

## Summary

Exposed two new `HarnessBuilder` methods on the PyO3 `PyHarnessBuilder` class, allowing Python users to configure compaction prompt templates and query intents.

## API Correction Applied

The plan assumed `CompactionPromptSpec::from_text(prompt)` exists. It does not. The actual API is:

```rust
CompactionPromptSpec::new(system_prompt: impl Into<String>, user_template: impl Into<String>) -> Result<Self, TemplateError>
```

- `user_template` MUST contain `{conversation}` placeholder
- `user_template` supports: `{conversation}`, `{previous_summary}`, `{file_operations}`, `{query}`
- `system_prompt` is not parsed for placeholders

## Python API

```python
# Set (both args required):
builder.compaction_prompt(system_prompt="You are a summarizer.", user_template="Summarize: {conversation}")

# Clear:
builder.compaction_prompt(None)
# or:
builder.compaction_prompt()

# Query setter:
builder.compaction_query("What was discussed?")
builder.compaction_query(None)
```

Both methods return `self` for chaining. `compaction_prompt` raises `RuntimeError` if:
- Only one of `system_prompt`/`user_template` is provided
- `user_template` is missing `{conversation}` placeholder
- `user_template` contains unknown `{...}` placeholders

## Implementation Details

### `src/core/pybuilder.rs`

1. **Import**: Added `CompactionPromptSpec` to the `llm_harness_agent` import.

2. **`compaction_prompt` method**:
   - Signature: `(system_prompt: Option<&str>, user_template: Option<&str>) -> PyResult<PyRefMut<'a, Self>>`
   - `#[pyo3(signature = (system_prompt=None, user_template=None))]` for default None values
   - `(None, None)` → clears (passes `None` to Rust builder)
   - `(Some(sp), Some(ut))` → constructs `CompactionPromptSpec::new(sp, ut)`, converts `TemplateError` to `PyRuntimeError` via `.to_string()`
   - Mixed `(Some, None)` or `(None, Some)` → returns `PyRuntimeError`

3. **`compaction_query` method**:
   - Signature: `(query: Option<String>) -> PyRefMut<'a, Self>`
   - `#[pyo3(signature = (query=None))]` for default None
   - Passes `Option<String>` directly to `builder.compaction_query(query)`

### `senza-pkg/senza/__init__.pyi`

Added stub signatures matching the runtime API:
```python
def compaction_prompt(
    self, system_prompt: Optional[str] = ..., user_template: Optional[str] = ...,
) -> HarnessBuilder: ...
def compaction_query(self, query: Optional[str] = ...) -> HarnessBuilder: ...
```

### `tests/test_compaction_prompt.py`

8 tests covering:
- `test_compaction_prompt_chains` — chains and returns self
- `test_compaction_prompt_none_clears` — `compaction_prompt(None)` clears
- `test_compaction_prompt_missing_conversation_placeholder` — raises RuntimeError
- `test_compaction_prompt_unknown_placeholder` — raises RuntimeError
- `test_compaction_prompt_mixed_args_system_only` — only system_prompt raises RuntimeError
- `test_compaction_prompt_mixed_args_template_only` — only user_template raises RuntimeError
- `test_compaction_query_chains` — chains and returns self
- `test_compaction_query_none` — `compaction_query(None)` clears

## Verification

- `pytest tests/test_compaction_prompt.py -v`: **8 passed**
- `pytest tests/` (full suite): **264 passed, 31 skipped**
- `python scripts/check_stubs.py`: **OK — 170 signatures verified, no drift**

## Commits

- `008e4bb` — feat(pybuilder): expose compaction_prompt/compaction_query setters

## Files Modified

| File | Change |
|---|---|
| `src/core/pybuilder.rs` | +45 lines (import + 2 methods) |
| `senza-pkg/senza/__init__.pyi` | +4 lines (2 stub signatures) |
| `tests/test_compaction_prompt.py` | +92 lines (new test file, 8 tests) |

## Concerns

None. The implementation correctly handles the `CompactionPromptSpec::new` API (not the non-existent `from_text`), properly converts `TemplateError` to `PyRuntimeError`, and all stubs match runtime with zero deviations.

## Review Fix: Mixed-args Edge Case Tests

**Finding (Important):** The `compaction_prompt` method handles the mixed-args case `(Some, None)` or `(None, Some)` by returning `RuntimeError`, but no test exercised this path.

**Fix:** Added two tests:
- `test_compaction_prompt_mixed_args_system_only` — calls `builder.compaction_prompt(system_prompt="only system")` without `user_template`, verifies `RuntimeError`
- `test_compaction_prompt_mixed_args_template_only` — calls `builder.compaction_prompt(user_template="Summarize: {conversation}")` without `system_prompt`, verifies `RuntimeError`

**Verification:** `pytest tests/test_compaction_prompt.py -v` → **8 passed**
