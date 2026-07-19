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

## 运行

```bash
# 设置 API key
export OPENAI_API_KEY=sk-...

# 可选：覆盖默认模型（默认 gpt-4o）
# export SENZA_MODEL=gpt-4o-mini

# 从本目录运行
python agent/01_basic_prompt.py
python runtime/01_linear_workflow.py
```

## 导入

所有示例使用 `import senza as lh`。
