"""01 — Local RAG: KnowledgePlugin with LocalDocumentSource.

Demonstrates:
  - create_local_knowledge_source: index local files for retrieval
  - create_knowledge_plugin: expose indexed docs as a search tool to the LLM

The knowledge plugin gives the harness a `knowledge_search` tool. When the
LLM asks a question, it searches the local document source and injects
relevant snippets into context — a lightweight RAG pipeline.
"""

import os
import tempfile

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.create_openai_provider(api_key=api_key)
    env = senza.create_os_env(".")

    # Create a temp doc directory to index
    doc_dir = tempfile.mkdtemp(prefix="senza_docs_")
    with open(os.path.join(doc_dir, "guide.md"), "w") as f:
        f.write("# Senza Guide\n\nSenza is an oh-my-harness runtime SDK.\n")

    source = senza.create_local_knowledge_source(
        path=doc_dir,
        source_id="local-docs",
        name="Project Docs",
        description="Local markdown documentation",
        domains=["engineering"],
        max_document_bytes=1048576,
    )

    plugin = senza.create_knowledge_plugin(sources=[source])

    harness = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .plugin(plugin)
        .env(env)
        .build()
    )

    print(f"KnowledgePlugin indexing: {doc_dir}")
    print(f"  source_id: local-docs")
    print(f"Harness phase: {harness.phase()}")


if __name__ == "__main__":
    main()
