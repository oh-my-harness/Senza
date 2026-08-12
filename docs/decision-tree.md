# Senza 决策树

## 要做什么？

### 单轮对话 / 工具调用
→ `HarnessBuilder` + `AgentHarness`

### 多步流程 / 条件分支
→ `WorkflowEngine`

### 需要安全防护？

| 场景 | API |
|------|-----|
| bash 黑名单 + 路径穿越防护 | `senza.strategy.safety_defaults()` |
| 死循环 / 重复 / 连续失败断路器 | `senza.strategy.loop_safety()` |
| 注入检测 | `senza.strategy.injection_filter()` |
| 内存防御 | `senza.strategy.memory_defense()` |
| 工具输出审计 | `senza.strategy.audit()` |
| 通知 | `senza.strategy.notify()` |

### 需要知识 / 记忆？

| 场景 | API |
|------|-----|
| 本地文档 RAG | `senza.knowledge.local_source()` + `senza.knowledge.plugin()` |
| 长期记忆 | `senza.knowledge.memory_store()` + `senza.knowledge.memory_plugin()` |
| 会话历史召回 | `senza.knowledge.sqlite_session_recall_index()` + `senza.knowledge.history_recall_plugin()` |

### 需要预算管控？

→ `builder.budget(limit)` + `builder.pricing(senza.providers.pricing_provider(...))`

### 需要审计 / 沙箱？

| 场景 | API |
|------|-----|
| JSONL 审计日志 | `senza.infra.jsonl_audit_sink()` |
| Trace 导出 | `senza.infra.in_memory_trace_exporter()` |
| 命令沙箱 (macOS) | `senza.infra.seatbelt_sandbox()` |
| 命令沙箱 (Linux) | `senza.infra.bwrap_sandbox()` |

### 需要工具审批规则？

→ `senza.rules.chain()` + predicates + `senza.rules.approval_hook()`

### 需要 Hooks？

→ `senza.hooks.*` (11 种 lifecycle hooks)

### 需要 Provider？

| 场景 | API |
|------|-----|
| OpenAI / DeepSeek / 通义千问 | `senza.providers.openai()` |
| Anthropic | `senza.providers.anthropic()` |

## Agent vs Workflow 快速判断

一个 prompt + 几个工具 → **Agent**
多个 prompt 串联、条件分支、需要持久化 → **Workflow**
