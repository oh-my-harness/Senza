import senza
import tempfile
import os


def test_memory_plugin_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "mem.md"), "w") as f:
            f.write("# Memory\nInitial content.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="memory-store",
        )
        store = senza.create_in_memory_store("memory-store")
        policy = senza.create_secure_write_policy()
        plugin = senza.create_memory_plugin(
            source=source,
            store=store,
            policy=policy,
        )
        assert plugin is not None


def test_memory_plugin_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "mem.md"), "w") as f:
            f.write("# Memory\nContent.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="mem",
        )
        store = senza.create_in_memory_store("mem")
        policy = senza.create_secure_write_policy()
        plugin = senza.create_memory_plugin(source=source, store=store, policy=policy)
        provider = senza.create_openai_provider(api_key="sk-test")
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("*", provider)
            .plugin(plugin)
            .build()
        )
        assert harness is not None


def test_memory_plugin_with_explicit_gate():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "mem.md"), "w") as f:
            f.write("# Memory\nContent.\n")
        source = senza.create_local_knowledge_source(
            path=tmpdir,
            source_id="mem-gate",
        )
        store = senza.create_in_memory_store("mem-gate")
        policy = senza.create_secure_write_policy()
        gate = senza.create_allow_all_gate()
        plugin = senza.create_memory_plugin(
            source=source,
            store=store,
            policy=policy,
            gate=gate,
        )
        assert plugin is not None
