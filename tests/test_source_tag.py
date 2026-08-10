import senza


def test_source_tag_plugin_creates():
    entries = [
        {"tool": "web_search", "label": "webpage"},
        {"tool": "read_url", "label": "webpage"},
    ]
    plugin = senza.create_source_tag_plugin(entries)
    assert plugin is not None


def test_source_tag_plugin_empty():
    plugin = senza.create_source_tag_plugin([])
    assert plugin is not None


def test_source_tag_in_builder():
    provider = senza.create_openai_provider(api_key="sk-test")
    plugin = senza.create_source_tag_plugin([{"tool": "search", "label": "web"}])
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
