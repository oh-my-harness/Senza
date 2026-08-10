import senza
import tempfile
import os


def test_knowledge_plugin_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "test.md"), "w") as f:
            f.write("# Test\nContent here.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="test-docs",
        )
        plugin = senza.create_knowledge_plugin(sources=[source])
        assert plugin is not None


def test_knowledge_plugin_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "doc.md"), "w") as f:
            f.write("# Doc\nContent.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="docs",
        )
        plugin = senza.create_knowledge_plugin(
            sources=[source],
            config={"max_search_results": 10, "max_read_bytes": 50000},
        )
        assert plugin is not None


def test_knowledge_plugin_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "doc.md"), "w") as f:
            f.write("# Doc\nContent.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="docs",
        )
        plugin = senza.create_knowledge_plugin(sources=[source])
        provider = senza.create_openai_provider(api_key="sk-test")
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("*", provider)
            .plugin(plugin)
            .build()
        )
        assert harness is not None
