"""Smoke tests for PricingProvider exposure (G2)."""
import senza as lh


def _make_provider():
    return lh.create_openai_provider(api_key="test-key")


def test_create_pricing_provider():
    """create_pricing_provider accepts a dict table."""
    pricing = lh.create_pricing_provider({
        "gpt-4o": {
            "input_per_mtok": 2.5,
            "output_per_mtok": 10.0,
            "cache_read_per_mtok": 1.25,
            "cache_write_per_mtok": 2.5,
        },
    })
    assert pricing is not None
    assert type(pricing).__name__ == "PricingProvider"


def test_create_pricing_provider_callback():
    """create_pricing_provider_callback accepts a callable."""
    def get_price(model, provider):
        if model == "gpt-4o":
            return {
                "input_per_mtok": 2.5,
                "output_per_mtok": 10.0,
                "cache_read_per_mtok": 1.25,
                "cache_write_per_mtok": 2.5,
            }
        return None

    pricing = lh.create_pricing_provider_callback(get_price)
    assert pricing is not None


def test_create_pricing_provider_callback_returns_none():
    """callback returning None should not crash."""
    pricing = lh.create_pricing_provider_callback(lambda m, p: None)
    assert pricing is not None


def test_builder_pricing_chains():
    """builder.pricing() chains and returns self."""
    pricing = lh.create_pricing_provider({"gpt-4o": {"input_per_mtok": 2.5, "output_per_mtok": 10.0}})
    builder = lh.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.pricing(pricing)
    assert result is builder


def test_builder_pricing_then_build():
    """builder with pricing set can build successfully."""
    pricing = lh.create_pricing_provider({"gpt-4o": {"input_per_mtok": 2.5, "output_per_mtok": 10.0}})
    harness = (
        lh.HarnessBuilder("gpt-4o")
        .provider("gpt-*", _make_provider())
        .pricing(pricing)
        .build()
    )
    assert harness is not None
    usage = harness.usage()
    assert "total_cost" in usage
