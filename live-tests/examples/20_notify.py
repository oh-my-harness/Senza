"""20 — Notify: LLM-callable user notifications (notify_user tool).

Mirrors runtime `20_notify.rs`. The NotifyPlugin registers a `notify_user` tool
the LLM can call (`senza.strategy.notify()`) to send the user a message WITHOUT
ending the run. The tool takes a `text` (required) and an optional `urgency`
(low | normal | high).

Feature gap: in the runtime, the actual delivery channel is injected **per run**
as a `NotificationChannel` via `RunRequest::with_extension(...)`. Senza's Python
surface exposes no way to inject a notification channel, so the tool always
reports `delivered=False` with reason `no_channel_configured`. This example
registers the plugin, lets the LLM call `notify_user`, and prints each
notification's text + delivery status captured from the tool result via an
`after_tool_call` hook — the closest analog to observing channel delivery.

Run:
  source ~/.omp_llm_env && python live-tests/examples/20_notify.py
"""

import senza
from _common import make_example_harness, run_prompt, text_of

# (text, delivered, reason) captured from notify_user tool results.
notifications: list[dict] = []


def after_tool_call(ctx):
    if ctx.get("tool_name") == "notify_user":
        result = ctx.get("result") or {}
        details = result.get("details") or {}
        content = result.get("content") or []
        content_text = "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
        notifications.append(
            {
                "text": details.get("text") or "(no text)",
                "delivered": details.get("delivered"),
                "reason": details.get("reason"),
                "tool_result": content_text,
            }
        )
    return "passthrough"


def run_one(prompt):
    """Run a prompt with the notify plugin + capture hook, then report."""
    notifications.clear()
    harness = make_example_harness(
        lambda b: b.plugin(senza.strategy.notify()).hooks(
            [senza.hooks.after_tool_call(after_tool_call)]
        )
    )
    print(f"Prompt: {prompt}\n")
    events = run_prompt(harness, prompt, timeout_ms=60_000)

    tools_called = sorted(
        {
            e.get("tool_name")
            for e in events
            if e["type"] in ("tool_call_start", "tool_execution_start")
        }
    )
    print(f"Tools called: {tools_called}")
    print(f"notify_user registered & invoked: {'notify_user' in tools_called}")
    print(f"Notifications observed: {len(notifications)}")
    for n in notifications:
        print(f"  - text={n['text']!r} delivered={n['delivered']} reason={n['reason']}")
    print(f"\nFinal text: {text_of(events).strip()[:160]}\n")
    return tools_called, notifications


def main() -> None:
    print("=== 20: Notify (notify_user) ===\n")

    # Part 1: single notification.
    print("--- Part 1: single notification ---\n")
    run_one("Use the notify_user tool to send a notification saying 'Task completed successfully'.")

    # Part 2: multiple notifications (mirrors runtime part 2).
    print("--- Part 2: multiple notifications ---\n")
    tools, notifs = run_one(
        "Send three separate notifications using the notify_user tool, each "
        "with a different urgency level (low, normal, high): 'Low battery "
        "warning', 'Build finished', 'Critical security alert'. Call the tool "
        "three times."
    )
    print(f"notify_user call count: {tools.count('notify_user')}")
    print(f"Notifications observed: {len(notifs)}")

    print(
        "\n[feature gap] The runtime delivers notifications through a per-run "
        "NotificationChannel injected via RunRequest::with_extension; Senza's "
        "Python surface exposes no such injection, so delivered=False "
        "(reason=no_channel_configured). The message text is still recorded "
        "in the notify_user tool result and observable here via the "
        "after_tool_call hook."
    )


if __name__ == "__main__":
    main()
