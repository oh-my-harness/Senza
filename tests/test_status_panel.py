import senza


def test_status_panel_plugin_creates():
    plugin = senza.strategy.status_panel()
    assert plugin is not None


def test_status_panel_in_builder():
    provider = senza.providers.openai(api_key="sk-test")
    plugin = senza.strategy.status_panel()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
