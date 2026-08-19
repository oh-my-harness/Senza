# 附录：Runtime/Senza 源码地图

教材中的架构名词最终都应能落到代码。下面的地图不是完整 API 索引，而是帮助读者沿着一次 Agent
运行，从 Python 装配面追到 Runtime 权威实现。

## 主循环与生命周期

| 问题 | Runtime 权威入口 | Senza 装配入口 | 配套实验 |
| --- | --- | --- | --- |
| Harness 如何驱动一次 run？ | [`harness/core.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-agent/src/harness/core.rs)、[`loop_fn.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-loop/src/loop_fn.rs) | [`pybuilder.rs`](../../../src/core/pybuilder.rs)、[`pyharness.rs`](../../../src/core/pyharness.rs) | [Lab 01](../../../academy/labs/01_react_tool_calling/README.md) |
| 12 个 Hook 存在哪里？ | [`harness/state.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-agent/src/harness/state.rs) | [`pyhooks.rs`](../../../src/core/pyhooks.rs) | [Lab 02](../../../academy/labs/02_hook_xray/README.md) |
| 多个 Hook 怎样组合？ | [`composite.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-loop/src/composite.rs) | Python callback 适配仍由 [`pyhooks.rs`](../../../src/core/pyhooks.rs) 完成 | [Lab 02](../../../academy/labs/02_hook_xray/README.md) |
| Plugin 贡献怎样进入 Harness？ | [`plugin.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-agent/src/plugin.rs)、[`builder.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime/src/builder.rs) | [`create_plugin`](../../../src/lib.rs)、[`HarnessBuilder`](../../../src/core/pybuilder.rs) | [Lab 03](../../../academy/labs/03_plugin_db_safety/README.md) |

## 上下文与应用控制

| 问题 | Runtime/Senza 入口 | 配套实验 |
| --- | --- | --- |
| Skill 如何进入 Python 装配面？ | [`pyskills.rs`](../../../src/runtime/pyskills.rs)、[`pybuilder.rs`](../../../src/core/pybuilder.rs) | [Lab 04](../../../academy/labs/04_context_layers/README.md) |
| 状态栏和压缩在哪里配置？ | [`pystatuspanel.rs`](../../../src/strategy/pystatuspanel.rs)、[`pyharness.rs`](../../../src/core/pyharness.rs) | [Lab 04](../../../academy/labs/04_context_layers/README.md) |
| 文件工具和规则怎样组合？ | [`src/lib.rs`](../../../src/lib.rs)、[`pysafety.rs`](../../../src/strategy/pysafety.rs)、[`pyloopsafety.rs`](../../../src/strategy/pyloopsafety.rs) | [Lab 05](../../../academy/labs/05_coding_guardrails/README.md) |
| Workflow、TaskStore、恢复和 HITL 在哪里？ | [`pyworkflow.rs`](../../../src/runtime/pyworkflow.rs) | [Lab 06](../../../academy/labs/06_workflow_recovery_hitl/README.md) |

## 知识、状态与协作

| 问题 | Runtime 权威入口 | Senza 装配入口 | 配套实验 |
| --- | --- | --- | --- |
| KnowledgeSource 的 `search/read` 契约是什么？ | [`source.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime-knowledge/src/source.rs) | [`pylocalsource.rs`](../../../src/knowledge/pylocalsource.rs) | [Lab 07](../../../academy/labs/07_knowledge_memory_recall/README.md) |
| 本地搜索为什么是 BM25？ | [`index.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime-knowledge-local/src/index.rs) | 同上 | [Lab 07](../../../academy/labs/07_knowledge_memory_recall/README.md) |
| Memory 写侧经过哪些门？ | [`service.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime-memory/src/service.rs)、[`store.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime-memory/src/store.rs) | [`pymemory.rs`](../../../src/knowledge/pymemory.rs) | [Lab 07](../../../academy/labs/07_knowledge_memory_recall/README.md) |
| Session Recall 投影怎样构造？ | [`projector.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime-session-recall/src/projector.rs) | [`pysessionrecall.rs`](../../../src/knowledge/pysessionrecall.rs) | [Lab 07](../../../academy/labs/07_knowledge_memory_recall/README.md) |
| Spawn 管理和消息协议在哪里？ | [`spawn/tools.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime/src/spawn/tools.rs)、[`message_bus.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime/src/spawn/message_bus.rs) | [`pyspawn.rs`](../../../src/runtime/pyspawn.rs) | [Lab 08](../../../academy/labs/08_basic_multi_agent/README.md) |

## 证据、评测与改进

| 问题 | 项目入口 | 配套实验 |
| --- | --- | --- |
| JSONL Audit 如何记录并校验行为？ | [`pyaudit.rs`](../../../src/infra/pyaudit.rs) | [Lab 09](../../../academy/labs/09_reliability_eval/README.md) |
| 教学 eval runner 如何计算结果？ | [`evaluation.py`](../../../academy/labs/09_reliability_eval/evaluation.py) | [Lab 09](../../../academy/labs/09_reliability_eval/README.md) |
| Bad case 如何变成待审批候选？ | [`proposal.py`](../../../academy/labs/10_improvement_proposal/proposal.py) | [Lab 10](../../../academy/labs/10_improvement_proposal/README.md) |

## 推荐的源码阅读顺序

不要从 Python 顶层导出列表一次性向下遍历。先运行一条最小 recorded 或 live 轨迹，带着一个问题
进入代码：先看 Senza builder 如何接收配置，再看 Runtime builder 怎样安装 Plugin，随后看 Core
在哪个时机调用 composite Hook，最后回到具体 Tool 或后端。这样读到的每个接口都能放回执行
因果链中，不会把“可构造对象”误认为“已经完成端到端装配”。
