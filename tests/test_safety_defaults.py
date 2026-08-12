import senza


def test_safety_defaults_plugin_creates():
    """create_safety_defaults_plugin() returns a valid Plugin."""
    plugin = senza.strategy.safety_defaults()
    assert plugin is not None


def test_safety_defaults_plugin_usable_in_builder():
    """SafetyDefaultsPlugin can be installed on a harness builder."""
    provider = senza.providers.openai(api_key="sk-test")
    env = senza.create_os_env(".")
    plugin = senza.strategy.safety_defaults()
    harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).plugin(plugin).env(env).build()
    assert harness is not None
    assert harness.phase() == "idle"
