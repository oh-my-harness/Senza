import os
import tempfile

import senza


def test_knowledge_plugin_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "test.md"), "w") as f:
            f.write("# Test\nContent here.\n")
        source = senza.knowledge.local_source(
            path=tmpdir,
            source_id="test-docs",
        )
        plugin = senza.knowledge.plugin(sources=[source])
        assert plugin is not None


def test_knowledge_plugin_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "doc.md"), "w") as f:
            f.write("# Doc\nContent.\n")
        source = senza.knowledge.local_source(
            path=tmpdir,
            source_id="docs",
        )
        plugin = senza.knowledge.plugin(
            sources=[source],
            config={"max_search_results": 10, "max_read_bytes": 50000},
        )
        assert plugin is not None


def test_knowledge_plugin_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "doc.md"), "w") as f:
            f.write("# Doc\nContent.\n")
        source = senza.knowledge.local_source(
            path=tmpdir,
            source_id="docs",
        )
        plugin = senza.knowledge.plugin(sources=[source])
        provider = senza.providers.openai(api_key="sk-test")
        harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).plugin(plugin).build()
        assert harness is not None
