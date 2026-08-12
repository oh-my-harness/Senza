import os
import tempfile

import senza


def test_memory_plugin_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "mem.md"), "w") as f:
            f.write("# Memory\nInitial content.\n")
        source = senza.knowledge.local_source(
            path=tmpdir,
            source_id="memory-store",
        )
        store = senza.knowledge.memory_store("memory-store")
        policy = senza.knowledge.secure_write_policy()
        plugin = senza.knowledge.memory_plugin(
            source=source,
            store=store,
            policy=policy,
        )
        assert plugin is not None


def test_memory_plugin_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "mem.md"), "w") as f:
            f.write("# Memory\nContent.\n")
        source = senza.knowledge.local_source(
            path=tmpdir,
            source_id="mem",
        )
        store = senza.knowledge.memory_store("mem")
        policy = senza.knowledge.secure_write_policy()
        plugin = senza.knowledge.memory_plugin(source=source, store=store, policy=policy)
        provider = senza.providers.openai(api_key="sk-test")
        harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).plugin(plugin).build()
        assert harness is not None


def test_memory_plugin_with_explicit_gate():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "mem.md"), "w") as f:
            f.write("# Memory\nContent.\n")
        source = senza.knowledge.local_source(
            path=tmpdir,
            source_id="mem-gate",
        )
        store = senza.knowledge.memory_store("mem-gate")
        policy = senza.knowledge.secure_write_policy()
        gate = senza.knowledge.allow_all_gate()
        plugin = senza.knowledge.memory_plugin(
            source=source,
            store=store,
            policy=policy,
            gate=gate,
        )
        assert plugin is not None
