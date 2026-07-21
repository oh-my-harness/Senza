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
