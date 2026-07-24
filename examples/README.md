# Senza 示例

## Agent 层（`agent/`）

使用 `HarnessBuilder` 和 `AgentHarness` 的单轮 LLM 对话模式。

| 文件 | 内容 |
|------|------|
| `01_basic_prompt.py` | 最小示例：发送提示 → 收集事件 → 提取文本 |
| `02_tool_calling.py` | 注册工具，LLM 发现并调用 |
| `03_streaming.py` | 通过 `events()` 逐 token 流式输出 |
| `04_dynamic_config.py` | `set_model`、`set_system_prompt`、`set_temperature`、`set_thinking_level`、`usage` |
| `05_multi_provider.py` | 通过 glob 模式将不同模型路由到不同 provider |
| `06_hooks.py` | 11 个生命周期 hook（观察 + `before_tool_call`/`should_stop` 决策） |
| `07_rules.py` | Rules 规则引擎：4 种 predicate + 审批 hook |
| `08_budget_pricing.py` | `pricing` 定价表 + `budget` 预算超限停止 |
| `09_skills.py` | `load_skills` 加载 SKILL.md + 自动注册 `skill_read` 工具 |
| `10_plugins.py` | `create_plugin` 打包 tools+hooks，agent 层 + workflow 层 `with_step_plugin` |
| `11_steering.py` | 多轮对话：`steer`/`follow_up`/`next_turn`/`continue_run` + 队列管理 + 上下文管理器 |
| `12_session_branch.py` | 会话树：`fork_branch`/`navigate_tree`/`list_branches`/`generate_branch_summary` |
| `13_anthropic_standalone.py` | Anthropic provider 独立示例 + `version`/`to_json`/`from_json` 工具函数 |
| `14_code_review.py` | 代码审查 agent：自定义工具读取代码 + 结构化输出 |
| `15_rag_qa.py` | RAG 问答 agent：知识库检索工具 + 工具增强问答 |
| `16_mcp_blender.py` | MCP 工具服务器：`McpServerConfig.stdio` + `mcp_server` + `McpManager` 生命周期（blender-mcp） |

## Runtime 层（`runtime/`）

使用 `WorkflowEngine` 的多步工作流模式。

| 文件 | 内容 |
|------|------|
| `01_linear_workflow.py` | 步骤 A → 步骤 B，judge 跳转，步骤历史 |
| `02_conditional_routing.py` | 自定义 judge 条件路由 |
| `03_executor_steps.py` | Python executor 步骤，与 LLM 步骤混合，共享上下文 |
| `04_crash_recovery.py` | `with_task_store` + `restore()` 崩溃恢复 |
| `05_pause_cancel.py` | 从另一线程调用 `pause()` / `cancel()`，状态监控 |
| `06_human_in_the_loop.py` | `create_event_channel` 外部事件注入 |
| `07_shell_executor.py` | Python callback executor + 命令白名单 |
| `08_http_executor.py` | `create_http_executor` + httpbin.org 测试 |
| `09_composite_judge.py` | `create_composite_judge` 按节点路由 + 声明式边 fallback |
| `10_hooks_retries.py` | `with_hooks` + `with_max_retries` + `restore_from_step` 按步恢复 |
| `11_data_analysis.py` | 数据分析流水线：LLM 步骤 + executor 步骤 + 共享上下文 |

## 运行

```bash
# 设置 API key
export OPENAI_API_KEY=sk-...

# 可选：覆盖默认模型（默认 gpt-4o）
# export SENZA_MODEL=gpt-4o-mini

# Anthropic 示例使用 Claude 模型：
# export ANTHROPIC_API_KEY=sk-ant-...
# export SENZA_MODEL=claude-sonnet-4-20250514

# 从本目录运行
python agent/01_basic_prompt.py
python runtime/01_linear_workflow.py

# MCP 示例（16_mcp_blender.py）额外需要：
#   - Blender 运行中，已安装 blender-mcp addon 并点 "Connect to Claude"
#   - uvx 在 PATH 上（pip install uv）
#   - OPENAI_MODEL 环境变量（或 SENZA_MODEL）
python agent/16_mcp_blender.py
```

## 导入

所有示例使用 `import senza`。
