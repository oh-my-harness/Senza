import tempfile

import senza


def test_project_instruction_plugin_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = senza.create_os_env(tmpdir)
        plugin = senza.strategy.project_instruction(env)
        assert plugin is not None


def test_project_instruction_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = senza.create_os_env(tmpdir)
        plugin = senza.strategy.project_instruction(
            env, {"file_names": ["CLAUDE.md", "AGENTS.md"], "max_depth": 3}
        )
        assert plugin is not None


def test_project_instruction_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = senza.providers.openai(api_key="sk-test")
        env = senza.create_os_env(tmpdir)
        plugin = senza.strategy.project_instruction(env)
        harness = (
            senza.HarnessBuilder("gpt-4o").provider("*", provider).plugin(plugin).env(env).build()
        )
        assert harness is not None
