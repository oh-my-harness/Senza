import senza


def test_notify_plugin_creates():
    plugin = senza.strategy.notify()
    assert plugin is not None


def test_notify_plugin_in_builder():
    provider = senza.providers.openai(api_key="sk-test")
    plugin = senza.strategy.notify()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
