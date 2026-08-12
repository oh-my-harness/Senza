from .senza import *  # noqa: F401, F403

import asyncio as _asyncio
import threading as _threading
from typing import Any, AsyncGenerator

_TERMINAL_TYPES = frozenset(
    {"agent_end", "error", "settled", "aborted", "workflow_done", "workflow_failed"}
)

_STOP = object()


def _get_event_iterator(obj: Any, timeout_ms: int, max_consecutive_timeouts: int) -> Any:
    """Return the sync event iterator for *obj*, regardless of class."""
    if hasattr(obj, "events"):
        return obj.events(
            timeout_ms=timeout_ms, max_consecutive_timeouts=max_consecutive_timeouts
        )
    if hasattr(obj, "subscribe"):
        return obj.subscribe(
            timeout_ms=timeout_ms, max_consecutive_timeouts=max_consecutive_timeouts
        )
    raise TypeError(
        f"{type(obj).__name__} has no events() or subscribe() method"
    )


async def _next_event(it: Any) -> Any:
    """Call next(it) in a thread, converting StopIteration to a sentinel.

    ``asyncio.to_thread`` cannot propagate ``StopIteration`` because it
    interacts badly with the generator protocol, so we catch it in the
    worker thread and return ``_STOP`` instead.
    """

    def _step() -> Any:
        try:
            return next(it)
        except StopIteration:
            return _STOP

    result = await _asyncio.to_thread(_step)
    return result


async def stream_events(
    obj: Any,
    timeout_ms: int = 5000,
    max_consecutive_timeouts: int = 1,
) -> AsyncGenerator[dict, None]:
    """Async generator yielding events from an Agent, AgentHarness, or WorkflowEngine.

    Wraps the synchronous event iterator, releasing the GIL during each
    ``__next__`` call so the asyncio event loop stays responsive.

    Usage::

        async for event in senza.stream_events(agent, timeout_ms=5000):
            print(event["type"])
    """
    it = _get_event_iterator(obj, timeout_ms, max_consecutive_timeouts)
    while True:
        event = await _next_event(it)
        if event is _STOP:
            break
        yield event


async def stream_prompt(
    obj: Any,
    text: str,
    timeout_ms: int = 5000,
) -> AsyncGenerator[dict, None]:
    """Send a prompt and yield events as they arrive (Agent / AgentHarness).

    Starts ``obj.prompt(text)`` on a background thread, then yields events
    until a terminal event (``agent_end``, ``settled``, ``aborted``,
    ``error``) is received or the stream is exhausted.

    Usage::

        async for event in senza.stream_prompt(agent, "hello"):
            print(event)
    """
    it = _get_event_iterator(obj, timeout_ms, 1)

    done = _threading.Event()
    errors: list = []

    def _do_prompt() -> None:
        try:
            obj.prompt(text)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            done.set()

    t = _threading.Thread(target=_do_prompt, daemon=True)
    t.start()

    try:
        while True:
            event = await _next_event(it)
            if event is _STOP:
                break
            yield event
            if event.get("type") in _TERMINAL_TYPES:
                break
    finally:
        done.wait(timeout=60)
        t.join(timeout=60)
        if errors:
            raise errors[0]


async def stream_run(
    engine: Any,
    timeout_ms: int = 5000,
) -> AsyncGenerator[dict, None]:
    """Start ``engine.run()`` on a background thread and yield workflow events.

    Usage::

        async for event in senza.stream_run(engine):
            print(event["type"])
    """
    it = _get_event_iterator(engine, timeout_ms, 1)

    done = _threading.Event()
    errors: list = []

    def _do_run() -> None:
        try:
            engine.run()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            done.set()

    t = _threading.Thread(target=_do_run, daemon=True)
    t.start()

    try:
        while True:
            event = await _next_event(it)
            if event is _STOP:
                break
            yield event
            if event.get("type") in _TERMINAL_TYPES:
                break
    finally:
        done.wait(timeout=120)
        t.join(timeout=120)
        if errors:
            raise errors[0]


# ── extract_text helper ──────────────────────────────────────────────


def extract_text(events):
    """Extract concatenated text from a list of agent events.

    Filters for ``text_delta`` events and concatenates their ``text``
    field. Non-text events are skipped. Missing ``text`` fields are
    treated as empty strings.

    Args:
        events: List of event dicts (e.g. from ``harness.prompt_and_collect()``).

    Returns:
        Concatenated text string.
    """
    return "".join(
        event.get("text", "")
        for event in events
        if event.get("type") == "text_delta"
    )


# ── @senza.tool decorator ────────────────────────────────────────────

import inspect as _inspect
import typing as _typing

_PY_TO_JSON_SCHEMA = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _build_schema_from_hints(func):
    """Build a JSON Schema dict from function type hints."""
    try:
        hints = _typing.get_type_hints(func)
    except Exception:
        hints = {}

    sig = _inspect.signature(func)
    properties = {}
    required = []

    for pname, param in sig.parameters.items():
        annotation = hints.get(pname, str)
        json_type = _PY_TO_JSON_SCHEMA.get(annotation, "string")
        prop = {"type": json_type}

        if param.default is _inspect.Parameter.empty:
            required.append(pname)
        else:
            prop["default"] = param.default

        properties[pname] = prop

    schema = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def _create_tool_from_function(func):
    """Create a Tool from a function with type hints."""
    name = func.__name__
    description = (func.__doc__ or func.__name__).strip()
    schema = _build_schema_from_hints(func)

    is_async = _inspect.iscoroutinefunction(func)
    sig = _inspect.signature(func)
    param_names = list(sig.parameters.keys())

    if is_async:
        async def wrapper(args, ctx):
            kwargs = {k: args.get(k) for k in param_names if k in args}
            return await func(**kwargs)
    else:
        def wrapper(args, ctx):
            kwargs = {k: args.get(k) for k in param_names if k in args}
            return func(**kwargs)

    return create_tool(name, description, schema, wrapper)


def tool(*args, **kwargs):
    """Create a Tool from a function or explicit parameters.

    As a decorator (no parens)::

        @senza.tool
        def search(query: str, limit: int = 10) -> str:
            \"\"\"Search the web.\"\"\"
            return f"Results for {query}"

    As a function call::

        tool = senza.tool(
            name="search",
            description="Search the web",
            parameters={"query": {"type": "string"}},
            callback=lambda args: f"Results for {args['query']}",
        )

    Type hints are used to auto-generate the JSON Schema when used as a
    decorator. The docstring becomes the tool description.
    """
    # Decorator form: @senza.tool (no parentheses)
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return _create_tool_from_function(args[0])

    # Function form: senza.tool(name=..., description=..., parameters=..., callback=...)
    name = kwargs.get("name")
    description = kwargs.get("description")
    parameters = kwargs.get("parameters")
    callback = kwargs.get("callback")

    if name is None or description is None or parameters is None or callback is None:
        raise TypeError(
            "senza.tool() requires name, description, parameters, and callback"
        )

    # Wrap callback to handle both (args) and (args, ctx) signatures
    cb_sig = _inspect.signature(callback)
    cb_nparams = len(cb_sig.parameters)
    if cb_nparams == 1:
        _orig = callback
        if _inspect.iscoroutinefunction(callback):
            async def _wrapped(args, ctx):
                return await _orig(args)
        else:
            def _wrapped(args, ctx):
                return _orig(args)
        callback = _wrapped

    return create_tool(name, description, parameters, callback)


# ── Async wrappers for blocking methods ──────────────────────────────


async def _workflow_run_async(self, timeout_ms: int = 300000):
    """Async version of run(). Does not block the event loop.

    Runs ``self.run()`` in a thread pool via ``asyncio.to_thread``.
    For event-streaming async usage, prefer ``senza.stream_run(engine)``.
    """
    return await _asyncio.to_thread(self.run)


async def _harness_prompt_async(self, text: str, timeout_ms: int = 30000):
    """Async version of prompt_and_collect(). Does not block the event loop.

    Runs ``self.prompt_and_collect(text, timeout_ms)`` in a thread pool
    via ``asyncio.to_thread``. For streaming async usage, prefer
    ``senza.stream_prompt(harness, text)``.
    """
    return await _asyncio.to_thread(self.prompt_and_collect, text, timeout_ms)


WorkflowEngine.run_async = _workflow_run_async
AgentHarness.prompt_async = _harness_prompt_async


# ── Debug helpers ────────────────────────────────────────────────────

import logging as _logging


def enable_debug():
    """Enable DEBUG-level logging for the senza logger.

    This sets the Python-side ``senza`` logger to DEBUG. The Rust-side
    tracing filter is controlled by the ``SENZA_LOG`` / ``RUST_LOG``
    environment variable; if you need Rust-side debug output, set
    ``SENZA_LOG=senza=debug`` before importing senza.
    """
    _logging.getLogger("senza").setLevel(_logging.DEBUG)


def disable_debug():
    """Restore INFO-level logging for the senza logger."""
    _logging.getLogger("senza").setLevel(_logging.INFO)


def _harness_inspect(self):
    """Return a snapshot of the harness state for debugging.

    Aggregates phase, message count, token usage, queued messages,
    and active tools into a single dict.
    """
    try:
        messages = self.get_messages()
        msg_count = len(messages) if messages else 0
    except Exception:
        msg_count = 0

    try:
        usage = self.usage()
    except Exception:
        usage = {}

    return {
        "message_count": msg_count,
        "usage": usage,
        "queued_messages": self.has_queued_messages() if hasattr(self, "has_queued_messages") else False,
    }


def _workflow_inspect(self):
    """Return a snapshot of the workflow engine state for debugging.

    Aggregates state, current step, step count, and total cost.
    """
    try:
        history = self.step_history()
        step_count = len(history) if history else 0
    except Exception:
        step_count = 0

    try:
        cost = self.total_cost()
    except Exception:
        cost = 0.0

    return {
        "state": self.state(),
        "current_step": self.current_step(),
        "step_count": step_count,
        "total_cost": cost,
    }


AgentHarness.inspect = _harness_inspect
WorkflowEngine.inspect = _workflow_inspect
