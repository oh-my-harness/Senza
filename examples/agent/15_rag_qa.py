"""03 — RAG QA Agent: answer questions based on a knowledge base.

Demonstrates:
  - HarnessBuilder with a RAG system prompt
  - Custom tool for knowledge base retrieval (simulated)
  - Tool-augmented QA pattern

Prerequisites:
  - Set OPENAI_API_KEY env var

Run:
  python examples/templates/03_rag_qa.py
"""
import json
import os
import sys

import senza

KNOWLEDGE_BASE = {
    "senza": "Senza 是一个生产级 Agent 运行时，基于 Rust 内核 + Python SDK。支持崩溃恢复和预算管控。",
    "workflow": "WorkflowEngine 用于多步工作流编排，支持条件路由、暂停取消和崩溃恢复。",
    "agent": "AgentHarness 用于单轮 LLM 对话和工具调用，支持流式输出和动态配置。",
}


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    provider = senza.create_openai_provider(api_key=api_key, base_url=base_url)

    def search_kb(args, ctx):
        """Tool: search the knowledge base by keyword."""
        query = args.get("query", "").lower()
        results = []
        for key, value in KNOWLEDGE_BASE.items():
            if key in query or query in key:
                results.append(f"[{key}] {value}")
        if not results:
            # 模糊匹配：返回所有内容
            for key, value in KNOWLEDGE_BASE.items():
                results.append(f"[{key}] {value}")
        return {
            "content": [{"type": "text", "text": "\n".join(results)}],
            "terminate": False,
        }

    search_tool = senza.create_tool(
        name="search_kb",
        description="Search the knowledge base for relevant information. Pass a keyword or topic.",
        parameters_schema=json.dumps({
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or topic"},
            },
            "required": ["query"],
        }),
        callback=search_kb,
    )

    harness = (
        senza.HarnessBuilder(os.environ.get("SENZA_MODEL", "gpt-4o"))
        .provider("*", provider)
        .system_prompt(
            "You are a QA assistant. Always use the search_kb tool to find relevant "
            "information before answering. Cite the source key in your answer. "
            "If no relevant information is found, say you don't know."
        )
        .tool(search_tool)
        .max_tokens(512)
        .build()
    )

    questions = [
        "Senza 是什么？",
        "WorkflowEngine 能做什么？",
        "怎么实现单轮对话？",
    ]

    for question in questions:
        print(f"\n{'='*60}")
        print(f"Q: {question}")
        print(f"{'='*60}")

        events = harness.prompt_and_collect(question, timeout_ms=30000)

        text = ""
        for event in events:
            t = event["type"]
            if t == "text_delta":
                text += event.get("text", "")
            elif t == "tool_call_start":
                print(f"  [tool called: {event.get('tool_name', '?')}]")
            elif t == "error":
                print(f"\n[error] {event.get('message', event)}", file=sys.stderr)
                break

        print(f"\nA: {text}")

    cost = harness.usage()
    print(f"\nTotal tokens: {cost['total_input_tokens']} in / {cost['total_output_tokens']} out")


if __name__ == "__main__":
    main()
