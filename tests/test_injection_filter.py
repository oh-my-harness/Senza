import senza


def test_injection_filter_default():
    plugin = senza.create_injection_filter_plugin()
    assert plugin is not None


def test_injection_filter_custom_patterns():
    plugin = senza.create_injection_filter_plugin(["ignore.*instructions", "system:.*"])
    assert plugin is not None


def test_injection_filter_in_builder():
    provider = senza.create_openai_provider(api_key="sk-test")
    plugin = senza.create_injection_filter_plugin()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
