"""Tests for hook context converters and hook creation."""

import senza

# ── Module surface tests ────────────────────────────────────────────────────


def test_module_has_before_turn_in_hooks_submodule():
    """The hooks submodule exposes before_turn (previously create_before_turn_hook)."""
    assert hasattr(senza.hooks, "before_turn")


def test_module_has_hook_class():
    """The module exposes a Hook class."""
    assert hasattr(senza, "Hook")


# ── create_before_turn_hook tests ───────────────────────────────────────────


def test_create_before_turn_hook():
    """create_before_turn_hook returns a non-None Hook object."""

    def my_hook(ctx):
        pass

    hook = senza.hooks.before_turn(my_hook)
    assert hook is not None


def test_create_before_turn_hook_with_lambda():
    """create_before_turn_hook accepts a lambda callback."""
    hook = senza.hooks.before_turn(lambda ctx: None)
    assert hook is not None


def test_create_before_turn_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.before_turn(lambda ctx: None)
    assert isinstance(hook, senza.Hook)


def test_multiple_before_turn_hooks_independent():
    """Multiple hook instances are independent."""
    h1 = senza.hooks.before_turn(lambda ctx: None)
    h2 = senza.hooks.before_turn(lambda ctx: None)
    assert h1 is not h2


def test_before_turn_hook_accepts_async_callback():
    """create_before_turn_hook accepts an async def callback."""

    async def my_async_hook(ctx):
        pass

    hook = senza.hooks.before_turn(my_async_hook)
    assert hook is not None


# ── Hook callback invocation tests (via Rust integration) ───────────────────
# The following tests verify that the Python callback is actually invoked when
# the BeforeTurnHook trait method is called. Full end-to-end invocation is
# tested in the Rust integration test (tests/hooks_integration.rs) because it
# requires tokio + Python::attach.


# ── create_after_turn_hook tests ─────────────────────────────────────────────


def test_create_after_turn_hook():
    """create_after_turn_hook returns a non-None Hook object."""

    def my_hook(ctx):
        pass

    hook = senza.hooks.after_turn(my_hook)
    assert hook is not None


def test_create_after_turn_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.after_turn(lambda ctx: None)
    assert isinstance(hook, senza.Hook)


def test_create_after_turn_hook_accepts_async_callback():
    """create_after_turn_hook accepts an async def callback."""

    async def my_async_hook(ctx):
        pass

    hook = senza.hooks.after_turn(my_async_hook)
    assert hook is not None


# ── create_before_run_hook tests ─────────────────────────────────────────────


def test_create_before_run_hook():
    """create_before_run_hook returns a non-None Hook object."""

    def my_hook(ctx):
        pass

    hook = senza.hooks.before_run(my_hook)
    assert hook is not None


def test_create_before_run_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.before_run(lambda ctx: None)
    assert isinstance(hook, senza.Hook)


def test_create_before_run_hook_accepts_async_callback():
    """create_before_run_hook accepts an async def callback."""

    async def my_async_hook(ctx):
        pass

    hook = senza.hooks.before_run(my_async_hook)
    assert hook is not None


# ── create_after_provider_response_hook tests ────────────────────────────────


def test_create_after_provider_response_hook():
    """create_after_provider_response_hook returns a non-None Hook object."""

    def my_hook(info):
        pass

    hook = senza.hooks.after_provider_response(my_hook)
    assert hook is not None


def test_create_after_provider_response_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.after_provider_response(lambda info: None)
    assert isinstance(hook, senza.Hook)


def test_create_after_provider_response_hook_accepts_async_callback():
    """create_after_provider_response_hook accepts an async def callback."""

    async def my_async_hook(info):
        pass

    hook = senza.hooks.after_provider_response(my_async_hook)
    assert hook is not None


# ── create_before_provider_request_hook tests ────────────────────────────────


def test_create_before_provider_request_hook():
    """create_before_provider_request_hook returns a non-None Hook object."""

    def my_hook(opts):
        pass

    hook = senza.hooks.before_provider_request(my_hook)
    assert hook is not None


def test_create_before_provider_request_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.before_provider_request(lambda opts: None)
    assert isinstance(hook, senza.Hook)


def test_create_before_provider_request_hook_accepts_async_callback():
    """create_before_provider_request_hook accepts an async def callback."""

    async def my_async_hook(opts):
        pass

    hook = senza.hooks.before_provider_request(my_async_hook)
    assert hook is not None


# ── create_should_stop_hook tests ───────────────────────────────────────────


def test_create_should_stop_hook():
    """create_should_stop_hook returns a non-None Hook object."""

    def my_hook(ctx):
        return True

    hook = senza.hooks.should_stop(my_hook)
    assert hook is not None


def test_create_should_stop_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.should_stop(lambda ctx: True)
    assert isinstance(hook, senza.Hook)


def test_create_should_stop_hook_accepts_async_callback():
    """create_should_stop_hook accepts an async def callback."""

    async def my_async_hook(ctx):
        return True

    hook = senza.hooks.should_stop(my_async_hook)
    assert hook is not None


# ── create_before_tool_call_hook tests ──────────────────────────────────────


def test_create_before_tool_call_hook():
    """create_before_tool_call_hook returns a non-None Hook object."""

    def my_hook(ctx):
        return "allow"

    hook = senza.hooks.before_tool_call(my_hook)
    assert hook is not None


def test_create_before_tool_call_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.before_tool_call(lambda ctx: "allow")
    assert isinstance(hook, senza.Hook)


def test_create_before_tool_call_hook_accepts_async_callback():
    """create_before_tool_call_hook accepts an async def callback."""

    async def my_async_hook(ctx):
        return "allow"

    hook = senza.hooks.before_tool_call(my_async_hook)
    assert hook is not None


def test_create_before_tool_call_hook_accepts_dict_return():
    """create_before_tool_call_hook accepts a dict with action=modify."""

    def my_hook(ctx):
        return {"action": "modify", "args": {"path": "/modified"}}

    hook = senza.hooks.before_tool_call(my_hook)
    assert hook is not None


# ── create_after_tool_call_hook tests ───────────────────────────────────────


def test_create_after_tool_call_hook():
    """create_after_tool_call_hook returns a non-None Hook object."""

    def my_hook(ctx):
        return "passthrough"

    hook = senza.hooks.after_tool_call(my_hook)
    assert hook is not None


def test_create_after_tool_call_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.after_tool_call(lambda ctx: "passthrough")
    assert isinstance(hook, senza.Hook)


def test_create_after_tool_call_hook_accepts_async_callback():
    """create_after_tool_call_hook accepts an async def callback."""

    async def my_async_hook(ctx):
        return "passthrough"

    hook = senza.hooks.after_tool_call(my_async_hook)
    assert hook is not None


# ── create_before_compact_hook tests ────────────────────────────────────────


def test_create_before_compact_hook():
    """create_before_compact_hook returns a non-None Hook object."""

    def my_hook(ctx):
        return "proceed"

    hook = senza.hooks.before_compact(my_hook)
    assert hook is not None


def test_create_before_compact_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.before_compact(lambda ctx: "proceed")
    assert isinstance(hook, senza.Hook)


def test_create_before_compact_hook_accepts_async_callback():
    """create_before_compact_hook accepts an async def callback."""

    async def my_async_hook(ctx):
        return "proceed"

    hook = senza.hooks.before_compact(my_async_hook)
    assert hook is not None


def test_create_before_compact_hook_accepts_compact_decision():
    """create_before_compact_hook accepts a callback returning 'compact'."""

    def my_hook(ctx):
        return "compact"

    hook = senza.hooks.before_compact(my_hook)
    assert isinstance(hook, senza.Hook)


def test_create_before_compact_hook_accepts_override_decision():
    """create_before_compact_hook accepts a callback returning an override dict with first_kept_entry."""

    def my_hook(ctx):
        entry_ids = ctx["entry_ids"]
        return {
            "action": "override",
            "summary": {
                "role": "compaction_summary",
                "summary": "custom summary",
                "timestamp": "2025-01-01T00:00:00Z",
            },
            "first_kept_entry": entry_ids[-1] if entry_ids else "",
        }

    hook = senza.hooks.before_compact(my_hook)
    assert isinstance(hook, senza.Hook)


# ── create_transform_context_hook tests ──────────────────────────────────────


def test_create_transform_context_hook():
    """create_transform_context_hook returns a non-None Hook object."""

    def my_hook(ctx):
        return ctx

    hook = senza.hooks.transform_context(my_hook)
    assert hook is not None


def test_create_transform_context_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.transform_context(lambda ctx: ctx)
    assert isinstance(hook, senza.Hook)


def test_create_transform_context_hook_accepts_async_callback():
    """create_transform_context_hook accepts an async def callback."""

    async def my_async_hook(ctx):
        return ctx

    hook = senza.hooks.transform_context(my_async_hook)
    assert hook is not None


# ── create_prepare_next_turn_hook tests ──────────────────────────────────────


def test_create_prepare_next_turn_hook():
    """create_prepare_next_turn_hook returns a non-None Hook object."""

    def my_hook(ctx):
        return {}

    hook = senza.hooks.prepare_next_turn(my_hook)
    assert hook is not None


def test_create_prepare_next_turn_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.prepare_next_turn(lambda ctx: {})
    assert isinstance(hook, senza.Hook)


def test_create_prepare_next_turn_hook_accepts_async_callback():
    """create_prepare_next_turn_hook accepts an async def callback."""

    async def my_async_hook(ctx):
        return {}

    hook = senza.hooks.prepare_next_turn(my_async_hook)
    assert hook is not None


# ── create_after_run_hook tests ──────────────────────────────────────────────


def test_create_after_run_hook():
    """after_run returns a non-None Hook object."""

    def my_hook():
        pass

    hook = senza.hooks.after_run(my_hook)
    assert hook is not None


def test_create_after_run_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.after_run(lambda: None)
    assert isinstance(hook, senza.Hook)


def test_create_after_run_hook_accepts_async_callback():
    """after_run accepts an async def callback."""

    async def my_async_hook():
        pass

    hook = senza.hooks.after_run(my_async_hook)
    assert hook is not None


# ── create_on_abort_hook tests ───────────────────────────────────────────────


def test_create_on_abort_hook():
    """on_abort returns a non-None Hook object."""

    def my_hook():
        pass

    hook = senza.hooks.on_abort(my_hook)
    assert hook is not None


def test_create_on_abort_hook_returns_hook_instance():
    """The returned object is an instance of the Hook class."""
    hook = senza.hooks.on_abort(lambda: None)
    assert isinstance(hook, senza.Hook)
