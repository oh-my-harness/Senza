"""Smoke tests for Rules approval system exposure (G3)."""
import senza


def test_create_contains_predicate():
    """create_contains_predicate returns a Predicate."""
    p = senza.create_contains_predicate(["search", "read"])
    assert p is not None
    assert type(p).__name__ == "Predicate"


def test_create_regex_field_predicate():
    """create_regex_field_predicate returns a Predicate."""
    p = senza.create_regex_field_predicate("path", "^[a-z]+$")
    assert p is not None


def test_create_number_range_predicate():
    """create_number_range_predicate returns a Predicate."""
    p = senza.create_number_range_predicate("count", 0, 100)
    assert p is not None


def test_create_rate_limit_predicate():
    """create_rate_limit_predicate returns a Predicate."""
    p = senza.create_rate_limit_predicate(5, 60.0)
    assert p is not None


def test_rule_chain_builder_chains():
    """RuleChainBuilder chains rule() and fallback()."""
    p = senza.create_contains_predicate(["search"])
    chain = (
        senza.create_rule_chain()
        .rule("search", p, "allow")
        .fallback("deny")
        .build()
    )
    assert chain is not None
    assert type(chain).__name__ == "RuleChain"


def test_rule_chain_builder_wildcard():
    """RuleChainBuilder accepts '*' as tool_name."""
    p = senza.create_contains_predicate(["*"])
    chain = senza.create_rule_chain().rule("*", p, "allow").build()
    assert chain is not None


def test_create_rule_approval_hook():
    """create_rule_approval_hook returns a Hook."""
    p = senza.create_contains_predicate(["search"])
    chain = (
        senza.create_rule_chain()
        .rule("search", p, "allow")
        .fallback("deny")
        .build()
    )
    hook = senza.create_rule_approval_hook(chain)
    assert hook is not None
    assert type(hook).__name__ == "Hook"


def test_rule_approval_hook_on_harness():
    """Rule approval hook can be registered on a harness via builder.hooks()."""
    p = senza.create_contains_predicate(["search"])
    chain = (
        senza.create_rule_chain()
        .rule("search", p, "allow")
        .fallback("deny")
        .build()
    )
    hook = senza.create_rule_approval_hook(chain)
    provider = senza.create_openai_provider(api_key="test-key")
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("gpt-*", provider)
        .hooks([hook])
        .build()
    )
    assert harness is not None
