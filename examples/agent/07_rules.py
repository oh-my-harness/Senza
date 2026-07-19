"""07 — Rules Engine: declarative tool-call approval with predicates.

Demonstrates the rule-based approval system. A ``RuleChain`` of
``(tool_name, predicate, decision)`` rules is turned into a
``BeforeToolCallHook`` via ``create_rule_approval_hook``. Every tool call
is checked against the chain **before** execution; the first matching
rule wins, and ``fallback`` decides what happens when nothing matches.

Predicates (all covered below):
  create_contains_predicate(allowed)         tool_name in allowed list
  create_regex_field_predicate(arg_path, p)  args[arg_path] matches regex
  create_number_range_predicate(arg_path,..) args[arg_path] within [min, max]
  create_rate_limit_predicate(max, window)   at most `max` calls per window

Rule chain used here (first match wins):

  1. delete_file  + regex  ^/tmp/                 -> allow   (only /tmp paths)
  2. transfer_money + number_range amount [0,1000] -> allow  (cap transfers)
  3. get_weather  + rate_limit 5 / 60s            -> allow   (throttle)
  4. *  + contains [get_weather,transfer_money,   -> deny    (whitelisted but
        delete_file]                                          condition failed)
  5. fallback                                     -> deny    (unknown tools)

Effect: a safe tool call is allowed; anything violating a rule is denied
**before** the tool runs, so the dangerous callback never fires.

Prerequisites:
  - Set OPENAI_API_KEY env var

Run:
  python 07_rules.py
"""
import json
import os
import sys

import senza as lh


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = lh.create_openai_provider(api_key=api_key, base_url=base_url)

    # ── Tools: one safe, two potentially dangerous ──────────────────────────
    def get_weather(args, ctx):
        city = args.get("city", "unknown")
        return {
            "content": [{"type": "text", "text": f"The weather in {city} is sunny, 22C."}],
            "terminate": False,
        }

    def transfer_money(args, ctx):
        amount = args.get("amount", 0)
        to = args.get("recipient", "?")
        return {
            "content": [{"type": "text", "text": f"Transferred {amount} to {to}."}],
            "terminate": False,
        }

    def delete_file(args, ctx):
        path = args.get("path", "?")
        return {
            "content": [{"type": "text", "text": f"Deleted {path}."}],
            "terminate": False,
        }

    tools = [
        lh.create_tool(
            name="get_weather",
            description="Get current weather for a city",
            parameters_schema=json.dumps({
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            }),
            callback=get_weather,
        ),
        lh.create_tool(
            name="transfer_money",
            description="Transfer money to a recipient",
            parameters_schema=json.dumps({
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "recipient": {"type": "string"},
                },
                "required": ["amount", "recipient"],
            }),
            callback=transfer_money,
        ),
        lh.create_tool(
            name="delete_file",
            description="Delete a file at the given path",
            parameters_schema=json.dumps({
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            }),
            callback=delete_file,
        ),
    ]

    # ── Build the rule chain (first match wins) ─────────────────────────────
    chain = (
        lh.create_rule_chain()
        # 1. delete_file: only allow paths under /tmp/
        .rule("delete_file", lh.create_regex_field_predicate("path", r"^/tmp/"), "allow")
        # 2. transfer_money: only allow amounts in [0, 1000]
        .rule("transfer_money", lh.create_number_range_predicate("amount", 0, 1000), "allow")
        # 3. get_weather: allow but throttle to 5 calls / 60s
        .rule("get_weather", lh.create_rate_limit_predicate(5, 60), "allow")
        # 4. whitelisted tool whose condition failed above -> explicit deny
        .rule("*", lh.create_contains_predicate(["get_weather", "transfer_money", "delete_file"]), "deny")
        # 5. anything not whitelisted -> deny
        .fallback("deny")
        .build()
    )

    approval_hook = lh.create_rule_approval_hook(chain)

    harness = (
        lh.HarnessBuilder(os.environ.get("SENZA_MODEL", "gpt-4o"))
        .provider("gpt-*", provider)
        .system_prompt(
            "You are an assistant with three tools. When asked, call the "
            "relevant tools. If a tool is denied, report that to the user."
        )
        .hooks([approval_hook])
    )
    for t in tools:
        harness = harness.tool(t)
    harness = harness.max_tokens(512).build()

    print("Prompting: the model will try a rule-violating transfer and delete...\n")
    events = harness.prompt_and_collect(
        "Transfer 5000 to Alice, delete /etc/passwd, and tell me the "
        "weather in Paris.",
        timeout_ms=30000,
    )

    text = ""
    tool_calls = []
    for event in events:
        t = event["type"]
        if t == "text_delta":
            text += event.get("text", "")
        elif t == "tool_call_start":
            tool_calls.append(event.get("tool_name", "?"))
        elif t == "error":
            print(f"\n[error] {event.get('message', event)}", file=sys.stderr)
            sys.exit(1)

    print(f"Tool calls attempted: {tool_calls}")
    print("Rules deny the >1000 transfer and the non-/tmp delete before they run.")
    print(f"\nResponse:\n{text}")


if __name__ == "__main__":
    main()
