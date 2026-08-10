import senza


def test_notify_plugin_creates():
    plugin = senza.create_notify_plugin()
    assert plugin is not None


def test_notify_plugin_in_builder():
    provider = senza.create_openai_provider(api_key="sk-test")
    plugin = senza.create_notify_plugin()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
