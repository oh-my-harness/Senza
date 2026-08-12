import senza


def test_memory_defense_default():
    plugin = senza.strategy.memory_defense()
    assert plugin is not None


def test_memory_defense_builder():
    builder = senza.MemoryDefensePluginBuilder()
    builder = builder.extra_file("CLAUDE.md")
    plugin = builder.build()
    assert plugin is not None


def test_memory_defense_builder_extra_files():
    builder = senza.MemoryDefensePluginBuilder()
    builder = builder.extra_files(["CLAUDE.md", "AGENTS.md"])
    plugin = builder.build()
    assert plugin is not None


def test_memory_defense_in_builder():
    provider = senza.providers.openai(api_key="sk-test")
    plugin = senza.strategy.memory_defense()
    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .build()
    )
    assert harness is not None
