import senza


def test_loop_safety_default_enabled():
    """create_loop_safety_plugin() with no args enables all guards with defaults."""
    plugin = senza.strategy.loop_safety()
    assert plugin is not None


def test_loop_safety_disabled():
    """create_loop_safety_plugin(None) creates a disabled (no-op) plugin."""
    plugin = senza.strategy.loop_safety(None)
    assert plugin is not None


def test_loop_safety_in_builder():
    """LoopSafetyPlugin can be installed on a harness builder."""
    provider = senza.providers.openai(api_key="sk-test")
    plugin = senza.strategy.loop_safety()
    harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).plugin(plugin).build()
    assert harness is not None
