import senza


def test_injection_filter_default():
    plugin = senza.strategy.injection_filter()
    assert plugin is not None


def test_injection_filter_custom_patterns():
    plugin = senza.strategy.injection_filter(["ignore.*instructions", "system:.*"])
    assert plugin is not None


def test_injection_filter_in_builder():
    provider = senza.providers.openai(api_key="sk-test")
    plugin = senza.strategy.injection_filter()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
