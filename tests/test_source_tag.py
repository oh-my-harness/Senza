import senza


def test_source_tag_plugin_creates():
    entries = [
        {"tool": "web_search", "label": "webpage"},
        {"tool": "read_url", "label": "webpage"},
    ]
    plugin = senza.strategy.source_tag(entries)
    assert plugin is not None


def test_source_tag_plugin_empty():
    plugin = senza.strategy.source_tag([])
    assert plugin is not None


def test_source_tag_in_builder():
    provider = senza.providers.openai(api_key="sk-test")
    plugin = senza.strategy.source_tag([{"tool": "search", "label": "web"}])
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
