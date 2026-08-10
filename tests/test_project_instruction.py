import senza
import tempfile


def test_project_instruction_plugin_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_project_instruction_plugin(env)
        assert plugin is not None


def test_project_instruction_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_project_instruction_plugin(
            env, {"file_names": ["CLAUDE.md", "AGENTS.md"], "max_depth": 3}
        )
        assert plugin is not None


def test_project_instruction_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = senza.create_openai_provider(api_key="sk-test")
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_project_instruction_plugin(env)
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("*", provider)
            .plugin(plugin)
            .env(env)
            .build()
        )
        assert harness is not None
