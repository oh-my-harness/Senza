"""02 — Data Analysis Pipeline: analyze data, transform, generate report.

Demonstrates:
  - WorkflowEngine with LLM steps + executor steps
  - Shared context variables between steps
  - Judge routing with structured output

Prerequisites:
  - Set OPENAI_API_KEY env var

Run:
  python examples/templates/02_data_analysis.py
"""
import json
import os
import sys

import senza as lh

SAMPLE_DATA = [
    {"product": "Widget A", "q1": 1200, "q2": 1500, "q3": 1100},
    {"product": "Widget B", "q1": 800, "q2": 950, "q3": 1200},
    {"product": "Widget C", "q1": 300, "q2": 400, "q3": 600},
]


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-demo-key")
    provider = lh.create_openai_provider(api_key=api_key)

    workflow = {
        "entry_step": "analyze",
        "steps": [
            {
                "id": "analyze",
                "name": "数据分析",
                "prompt": "分析以下销售数据，找出趋势和异常。返回 JSON：{\"summary\": \"一句话总结\", \"anomaly\": \"异常描述或null\"}",
                "allowed_tools": [],
            },
            {
                "id": "report",
                "name": "生成报告",
                "prompt": "根据分析结果写一份简短的业务报告（3-5句话）。",
                "allowed_tools": [],
            },
        ],
        "edges": [
            {"from": "analyze", "to": "report"},
        ],
    }

    def judge(ctx):
        if ctx["step_id"] == "analyze":
            structured = ctx.get("structured")
            if structured and "summary" in structured:
                return "to:report"
            return "retry"
        return "abort:done"

    def transform_executor(ctx):
        """Executor: 在分析结果上附加额外统计信息。"""
        prev_output = ctx.get("prev_output", "")
        total = sum(item["q1"] + item["q2"] + item["q3"] for item in SAMPLE_DATA)
        return {
            "output": f"{prev_output}\n\n[executor] 总销售额: {total}",
            "structured": {"total_sales": total},
        }

    engine = (
        lh.WorkflowEngine(workflow, provider, os.environ.get("SENZA_MODEL", "gpt-4o"), lh.create_judge(judge))
        .with_executor("transform", lh.create_executor(transform_executor))
        .with_max_tokens(512)
    )

    engine.set_context_variable("raw_data", json.dumps(SAMPLE_DATA, ensure_ascii=False))

    print("Running data analysis pipeline...\n")
    engine.run()

    print(f"Final state: {engine.state()}\n")
    for record in engine.step_history():
        r = record.get("result")
        if r:
            print(f"--- {record['step_id']} ---")
            print(r["output"][:300])
            print()


if __name__ == "__main__":
    main()
