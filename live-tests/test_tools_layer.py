"""Tools layer live tests: fs tools, grep/glob, knowledge RAG + memory, session recall."""

import os
import tempfile

import senza
from base import assert_settled, assert_tool_called, make_harness, provider_or_skip, run_prompt


def test_fs_tools_read_write():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "note.txt"), "w") as f:
            f.write("the magic number is 42")
        h = make_harness(
            provider_or_skip(),
            lambda b: b.plugin(senza.create_fs_tools_plugin()).env(senza.create_os_env(d)),
        )
        ev = run_prompt(h, "Use the read tool to read note.txt and report the number.")
        assert_settled(ev)
        assert_tool_called(ev, "read")


def test_grep_glob():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "a.py"), "w") as f:
            f.write("def main(): pass\n")
        h = make_harness(
            provider_or_skip(),
            lambda b: b.plugin(senza.create_fs_tools_plugin()).env(senza.create_os_env(d)),
        )
        ev = run_prompt(h, "Use glob to list the *.py files in the working directory.")
        assert_settled(ev)
        assert_tool_called(ev, "glob")


def test_knowledge_memory():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "guide.md"), "w") as f:
            f.write("Senza is an agent runtime. The deployment command is `senza deploy`.")
        source = senza.knowledge.local_source(path=d, source_id="guide")
        plugin = senza.knowledge.plugin(sources=[source])
        h = make_harness(provider_or_skip(), lambda b: b.plugin(plugin))
        ev = run_prompt(h, "Search the knowledge source for the deployment command.")
        assert_settled(ev)


def test_session_recall():
    repo = senza.knowledge.in_memory_session_repo()
    index = senza.knowledge.sqlite_session_recall_index(
        path=os.path.join(tempfile.mkdtemp(), "recall.db")
    )
    source = senza.knowledge.session_recall_knowledge_source(repo=repo, index=index)
    plugin = senza.knowledge.history_recall_plugin(source=source)
    h = make_harness(provider_or_skip(), lambda b: b.plugin(plugin))
    ev = run_prompt(h, "Say hello.")
    assert_settled(ev)


def test_tools_constructs_offline():
    """No key needed; validates fs-tools + knowledge construction."""
    stub = senza.providers.openai(api_key="sk-test")
    src = senza.knowledge.local_source(path=".", source_id="x")
    plugin = senza.knowledge.plugin(sources=[src])
    env_h = make_harness(
        stub, lambda b: b.plugin(senza.create_fs_tools_plugin()).env(senza.create_os_env("."))
    )
    k_h = make_harness(stub, lambda b: b.plugin(plugin))
    assert env_h is not None and k_h is not None and env_h.phase() == "idle"
