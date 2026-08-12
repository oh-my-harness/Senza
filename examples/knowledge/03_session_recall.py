"""03 — Session Recall: HistoryRecallPlugin.

Demonstrates:
  - SessionRecallIndex: indexes past conversation turns for semantic recall
  - SessionRepo: stores session entries (in-memory or SQLite-backed)
  - HistoryRecallPlugin: gives the LLM a `recall_history` tool

Session recall lets the harness search previous turns ("what did the user
decide about X?") without re-reading the full transcript. The plugin builds
an index over the session repo and exposes a retrieval tool to the LLM.
"""

import os
import tempfile

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    # SQLite-backed index for persistence; in-memory repo for entries
    index_path = os.path.join(tempfile.gettempdir(), "senza_recall.db")
    index = senza.knowledge.sqlite_session_recall_index(path=index_path)
    repo = senza.knowledge.in_memory_session_repo()

    recall_source = senza.knowledge.session_recall_knowledge_source(repo=repo, index=index)
    plugin = senza.knowledge.history_recall_plugin(source=recall_source)

    harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).plugin(plugin).env(env).build()

    print("HistoryRecallPlugin installed.")
    print(f"  index: SQLite ({index_path})")
    print("  repo:  in-memory")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
