import senza
import tempfile


def test_tool_output_guard_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_tool_output_guard_plugin(env)
        assert plugin is not None


def test_tool_output_guard_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_tool_output_guard_plugin(
            env, {"max_lines": 200, "max_bytes": 10000, "head_lines": 20, "tail_lines": 20}
        )
        assert plugin is not None


def test_tool_output_guard_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = senza.create_openai_provider(api_key="sk-test")
        env = senza.create_os_env(tmpdir)
        plugin = senza.create_tool_output_guard_plugin(env)
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("*", provider)
            .plugin(plugin)
            .env(env)
            .build()
        )
        assert harness is not None
