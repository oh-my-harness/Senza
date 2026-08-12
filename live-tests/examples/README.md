# live-tests examples — 真实 LLM 可运行示例

`live-tests/examples/` 是 Senza 全部可运行示例的唯一归宿（仓库根 `examples/` 已废弃并入此处）。
镜像 `llm-harness-runtime/.../llm-harness-live-tests/examples/`，分两组：

- **01–23**：运行时同名镜像（`NN_<snake>.py`），与运行时示例一一对应。
- **30–46**：原仓库根 `examples/` 中无运行时对应、具独立文档价值的示例，迁入本目录。

## 运行

```bash
# 无 key —— 打印 SKIP 并退出 0（不崩溃）
python live-tests/examples/01_prompt_streaming.py

# 有 key —— 驱动真实 LLM（默认 OMP DeepSeek：http://api.hyper-op.com/v1 + DeepSeek-V4-Flash）
source ~/.omp_llm_env
python live-tests/examples/01_prompt_streaming.py
```

每个示例独立 `main()`：构造真实 provider → 搭 harness/engine → 驱动真实 LLM → 打印输出与
token 用量。无 key 时打印 SKIP 并 exit 0，对齐测试侧「无 key 跳过」语义。

## 清单

### 运行时镜像（01–23）

| 文件 | 主题 |
|---|---|
| `01_prompt_streaming.py` | Prompt & 流式输出 |
| `02_tool_calling.py` | 工具发现 + 并行调用 |
| `03_dynamic_config_multi_turn.py` | 运行期动态配置 + 多轮 |
| `04_session_branch.py` | session 持久化 + 分支 + 导航 |
| `05_compaction.py` | 手动/自动压缩、断路器、自定义 prompt |
| `06_skills_model_switch.py` | skills、模板、模型切换 |
| `07_hooks.py` | 生命周期 hooks |
| `08_workflow.py` | WorkflowEngine 多 step |
| `09_workflow_recovery.py` | TaskStore 持久化、暂停/恢复/取消 |
| `10_sandbox.py` | OsEnv 沙箱生命周期 |
| `11_spawn_sub_agent.py` | 子代理分发与收集 |
| `12_tracing_audit.py` | Span 导出 + JSONL 哈希链审计 |
| `13_budget_pricing.py` | 成本账本 + 定价 |
| `14_rules_approval.py` | 规则链 + 审批 |
| `15_safety_injection.py` | 安全默认 + 注入过滤 |
| `16_status_panel.py` | 状态面板插件 |
| `17_source_instruction.py` | 来源标记 + 项目指令 |
| `18_loop_safety.py` | 循环安全四守卫 |
| `19_memory_defense.py` | 内存防御 + 工具输出守卫 |
| `20_notify.py` | 用户通知插件 |
| `21_context_aware_compact.py` | 上下文感知压缩 |
| `22_fs_tools.py` | bash/read/write/edit/grep/glob |
| `23_infra_integration.py` | 事件流 + knowledge + memory + recall |

### 仓库根迁入（30–46）

| 文件 | 主题 | 原出处 |
|---|---|---|
| `30_basic_prompt.py` | 最简对话 | examples/agent/01_basic_prompt.py |
| `31_multi_provider.py` | 多 provider | examples/agent/05_multi_provider.py |
| `32_plugins.py` | 插件机制 | examples/agent/10_plugins.py |
| `33_steering.py` | 行为导向 | examples/agent/11_steering.py |
| `34_anthropic_standalone.py` | Anthropic 独立 | examples/agent/13_anthropic_standalone.py |
| `35_code_review.py` | 代码审查模板 | examples/agent/14_code_review.py |
| `36_rag_qa.py` | RAG 问答模板 | examples/agent/15_rag_qa.py |
| `37_mcp_blender.py` | MCP Blender | examples/agent/16_mcp_blender.py |
| `38_conditional_routing.py` | 工作流条件路由 | examples/runtime/02_conditional_routing.py |
| `39_executor_steps.py` | 执行器步骤 | examples/runtime/03_executor_steps.py |
| `40_pause_cancel.py` | 暂停/取消 | examples/runtime/05_pause_cancel.py |
| `41_human_in_the_loop.py` | 人工介入 | examples/runtime/06_human_in_the_loop.py |
| `42_shell_executor.py` | Shell 执行器 | examples/runtime/07_shell_executor.py |
| `43_http_executor.py` | HTTP 执行器 | examples/runtime/08_http_executor.py |
| `44_composite_judge.py` | CompositeJudge | examples/runtime/09_composite_judge.py |
| `45_hooks_retries.py` | hooks + 重试 | examples/runtime/10_hooks_retries.py |
| `46_data_analysis.py` | 数据分析流水线 | examples/runtime/11_data_analysis.py |

## 约定

- 所有示例统一从 `_common.py` 导入（`make_example_harness` / `require_provider` / 超时常量 /
  `run_prompt` / `text_of`），由它完成 sys.path 引导与 provider 发现。
- 与各层测试的关系：这些是「可运行的文档」，弱断言 + 人类可观察；**行为断言**在上一层
  `live-tests/test_{agent,loop,tools,runtime,strategy}_layer.py`。
