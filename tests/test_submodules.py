"""Tests for the grouped submodule API (senza.providers, senza.hooks, etc.)."""

import senza

# ── Submodule existence ──────────────────────────────────────────────────────


def test_providers_submodule_exists():
    assert hasattr(senza, "providers")
    assert hasattr(senza.providers, "openai")
    assert hasattr(senza.providers, "anthropic")


def test_hooks_submodule_exists():
    assert hasattr(senza, "hooks")
    expected = {
        "before_turn",
        "after_turn",
        "before_run",
        "after_provider_response",
        "before_provider_request",
        "before_tool_call",
        "after_tool_call",
        "should_stop",
        "before_compact",
        "transform_context",
        "prepare_next_turn",
    }
    for name in expected:
        assert hasattr(senza.hooks, name), f"hooks.{name} missing"


def test_strategy_submodule_exists():
    assert hasattr(senza, "strategy")
    expected = {
        "safety_defaults",
        "loop_safety",
        "status_panel",
        "memory_defense",
        "injection_filter",
        "source_tag",
        "project_instruction",
        "audit",
        "notify",
        "tool_output_guard",
        "webhook_stream",
        "context_aware_compaction_prompt",
    }
    for name in expected:
        assert hasattr(senza.strategy, name), f"strategy.{name} missing"


def test_knowledge_submodule_exists():
    assert hasattr(senza, "knowledge")
    expected = {
        "local_source",
        "plugin",
        "memory_store",
        "memory_plugin",
        "secure_write_policy",
        "allow_all_gate",
        "in_memory_session_recall_index",
        "sqlite_session_recall_index",
        "in_memory_session_repo",
        "session_recall_knowledge_source",
        "history_recall_plugin",
    }
    for name in expected:
        assert hasattr(senza.knowledge, name), f"knowledge.{name} missing"


def test_infra_submodule_exists():
    assert hasattr(senza, "infra")
    assert hasattr(senza.infra, "jsonl_audit_sink")
    assert hasattr(senza.infra, "in_memory_trace_exporter")
    # Platform-specific: at least one sandbox factory should exist
    assert hasattr(senza.infra, "seatbelt_sandbox") or hasattr(senza.infra, "bwrap_sandbox")


def test_rules_submodule_exists():
    assert hasattr(senza, "rules")
    expected = {
        "chain",
        "contains",
        "regex_field",
        "number_range",
        "rate_limit",
        "approval_hook",
    }
    for name in expected:
        assert hasattr(senza.rules, name), f"rules.{name} missing"


# ── Identity checks: submodule delegates to same function ───────────────────


def test_providers_openai_identity():
    # The submodule attribute should be the same callable the Rust layer
    # registered — calling it produces a Provider.
    provider = senza.providers.openai(api_key="test-key")
    assert provider is not None
    assert type(provider).__name__ == "Provider"


def test_providers_anthropic_identity():
    provider = senza.providers.anthropic(api_key="test-key")
    assert provider is not None
    assert type(provider).__name__ == "Provider"


def test_hooks_before_turn_identity():
    hook = senza.hooks.before_turn(lambda ctx: None)
    assert isinstance(hook, senza.Hook)


def test_hooks_after_turn_identity():
    hook = senza.hooks.after_turn(lambda ctx: None)
    assert isinstance(hook, senza.Hook)


def test_hooks_should_stop_identity():
    hook = senza.hooks.should_stop(lambda ctx: True)
    assert isinstance(hook, senza.Hook)


def test_strategy_safety_defaults_identity():
    plugin = senza.strategy.safety_defaults()
    assert plugin is not None


def test_strategy_loop_safety_identity():
    plugin = senza.strategy.loop_safety()
    assert plugin is not None


def test_strategy_webhook_stream_identity():
    channel, stream = senza.strategy.webhook_stream(buffer=16)
    assert channel is not None
    assert stream is not None


def test_strategy_context_aware_compaction_prompt_identity():
    result = senza.strategy.context_aware_compaction_prompt()
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_knowledge_memory_store_identity():
    store = senza.knowledge.memory_store("test-source")
    assert store is not None


def test_knowledge_secure_write_policy_identity():
    policy = senza.knowledge.secure_write_policy()
    assert policy is not None


def test_knowledge_allow_all_gate_identity():
    gate = senza.knowledge.allow_all_gate()
    assert gate is not None


def test_rules_chain_identity():
    chain = senza.rules.chain()
    assert chain is not None


def test_rules_contains_identity():
    p = senza.rules.contains(["search", "read"])
    assert type(p).__name__ == "Predicate"


def test_rules_regex_field_identity():
    p = senza.rules.regex_field("path", "^[a-z]+$")
    assert p is not None


def test_rules_number_range_identity():
    p = senza.rules.number_range("count", 0, 100)
    assert p is not None


def test_rules_rate_limit_identity():
    p = senza.rules.rate_limit(5, 60.0)
    assert p is not None


def test_rules_approval_hook_identity():
    p = senza.rules.contains(["search"])
    chain = senza.rules.chain().rule("search", p, "allow").fallback("deny").build()
    hook = senza.rules.approval_hook(chain)
    assert type(hook).__name__ == "Hook"


def test_infra_jsonl_audit_sink_identity():
    assert senza.infra.jsonl_audit_sink is senza.JsonlAuditSink


def test_infra_in_memory_trace_exporter_identity():
    assert senza.infra.in_memory_trace_exporter is senza.InMemoryTraceExporter


# ── High-frequency APIs still at top level ──────────────────────────────────


def test_high_freq_apis_still_top_level():
    for name in [
        "HarnessBuilder",
        "AgentHarness",
        "WorkflowEngine",
        "tool",
        "create_tool",
        "create_plugin",
        "create_judge",
        "stream_prompt",
        "stream_events",
        "stream_run",
        "extract_text",
        "enable_debug",
        "disable_debug",
        "SenzaError",
        "ProviderError",
    ]:
        assert hasattr(senza, name), f"{name} should remain at top level"


# ── Removed names NOT accessible at top level ───────────────────────────────


def test_removed_provider_names_not_top_level():
    for name in ["create_openai_provider", "create_anthropic_provider"]:
        assert not hasattr(senza, name), f"{name} should be removed from top level"


def test_removed_hook_names_not_top_level():
    for name in [
        "create_before_turn_hook",
        "create_after_turn_hook",
        "create_before_run_hook",
        "create_after_provider_response_hook",
        "create_before_provider_request_hook",
        "create_before_tool_call_hook",
        "create_after_tool_call_hook",
        "create_should_stop_hook",
        "create_before_compact_hook",
        "create_transform_context_hook",
        "create_prepare_next_turn_hook",
    ]:
        assert not hasattr(senza, name), f"{name} should be removed from top level"


def test_removed_strategy_names_not_top_level():
    for name in [
        "create_safety_defaults_plugin",
        "create_loop_safety_plugin",
        "create_status_panel_plugin",
        "create_memory_defense_plugin",
        "create_injection_filter_plugin",
        "create_source_tag_plugin",
        "create_project_instruction_plugin",
        "create_audit_plugin",
        "create_notify_plugin",
        "create_tool_output_guard_plugin",
        "create_webhook_stream",
        "create_context_aware_compaction_prompt",
    ]:
        assert not hasattr(senza, name), f"{name} should be removed from top level"


def test_removed_knowledge_names_not_top_level():
    for name in [
        "create_local_knowledge_source",
        "create_knowledge_plugin",
        "create_in_memory_store",
        "create_memory_plugin",
        "create_secure_write_policy",
        "create_allow_all_gate",
        "create_in_memory_session_recall_index",
        "create_sqlite_session_recall_index",
        "create_in_memory_session_repo",
        "create_session_recall_knowledge_source",
        "create_history_recall_plugin",
    ]:
        assert not hasattr(senza, name), f"{name} should be removed from top level"


def test_removed_rules_names_not_top_level():
    for name in [
        "create_rule_chain",
        "create_contains_predicate",
        "create_regex_field_predicate",
        "create_number_range_predicate",
        "create_rate_limit_predicate",
        "create_rule_approval_hook",
    ]:
        assert not hasattr(senza, name), f"{name} should be removed from top level"
