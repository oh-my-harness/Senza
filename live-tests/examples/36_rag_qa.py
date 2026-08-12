"""36 — RAG QA: answer questions from a local document knowledge base.

Mirrors repo-root `examples/agent/15_rag_qa.py` (adapted to the real
`senza.knowledge` plugin instead of a simulated tool). Demonstrates:
  - Building a local knowledge source via senza.knowledge.local_source
  - Registering its knowledge_search / knowledge_read tools via
    senza.knowledge.plugin(sources=[...])
  - Tool-augmented QA: the model retrieves relevant chunks and answers

Run:
  source ~/.omp_llm_env && python live-tests/examples/36_rag_qa.py
"""

import os
import tempfile

import senza
from _common import make_example_harness, require_provider, run_prompt, text_of

KNOWLEDGE_DOCS = {
    "senza.md": (
        "# Senza\n\n"
        "Senza 是一个生产级 Agent 运行时，基于 Rust 内核 + Python SDK。"
        "支持崩溃恢复和预算管控。"
    ),
    "workflow.md": (
        "# WorkflowEngine\n\nWorkflowEngine 用于多步工作流编排，支持条件路由、暂停取消和崩溃恢复。"
    ),
    "agent.md": (
        "# AgentHarness\n\nAgentHarness 用于单轮 LLM 对话和工具调用，支持流式输出和动态配置。"
    ),
}


def main() -> None:
    print("=== 36: RAG QA ===\n")
    require_provider()

    kb_dir = tempfile.mkdtemp(prefix="senza-rag-")
    for name, body in KNOWLEDGE_DOCS.items():
        with open(os.path.join(kb_dir, name), "w") as f:
            f.write(body)

    source = senza.knowledge.local_source(path=kb_dir, source_id="senza-docs")
    knowledge = senza.knowledge.plugin(sources=[source])

    harness = make_example_harness(
        lambda b: (
            b.system_prompt(
                "You are a QA assistant. Use the knowledge_search tool to find "
                "relevant information before answering. Cite the source in your "
                "answer. If no relevant information is found, say you don't know."
            )
            .plugin(knowledge)
            .max_tokens(512)
        )
    )

    questions = [
        "Senza 是什么？",
        "WorkflowEngine 能做什么？",
        "怎么实现单轮对话？",
    ]

    for question in questions:
        print("=" * 60)
        print(f"Q: {question}")
        events = run_prompt(harness, question, timeout_ms=60_000)
        tools_used = {e.get("tool_name") for e in events if e["type"] == "tool_call_start"}
        print(f"Tools used: {sorted(tools_used)}")
        print(f"A: {text_of(events)}\n")

    usage = harness.usage()
    print(f"Total tokens: {usage['total_input_tokens']} in / {usage['total_output_tokens']} out")


if __name__ == "__main__":
    main()
