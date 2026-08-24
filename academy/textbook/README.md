# 《从 Agent 理论到 Senza 实践》

这是一份面向 Runtime/Senza 使用者和维护者的中文教材。它借用《动手学 AI Agent》提出的
问题框架，但全部工程叙事、组件映射和实验对象都来自当前工作区中的
`llm-harness-runtime` 与 Senza。

教材的目标不是让读者背 API，而是建立三个层次的理解：

1. **理论层**：可靠 Agent 为什么需要 Core、Hook、Plugin、上下文治理和验证闭环；
2. **实现层**：这些职责在 Runtime 与 Senza 中分别落在哪里；
3. **证据层**：哪些能力已经由真实 API 和测试证明，哪些仍是教学或契约预览。

## 阅读路线

| 单元 | 章节 | 学习结果 |
| --- | --- | --- |
| 起步 | [序言：如何使用本教材](00-preface.md) | 建立四层架构、证据等级与运行方式 |
| 构建 Agent | [01 ReAct 与 Tool Calling](01-react-tool-calling.md) | 理解模型、Core、Tool、Environment 的闭环 |
| 构建 Agent | [02 14 个 Hook](02-hook-lifecycle.md) | 理解固定生命周期点与组合语义 |
| 构建 Agent | [03 Plugin 装配](03-plugin-composition.md) | 理解构建期能力包、作用域、依赖与冲突 |
| 管理上下文 | [04 Context Layers](04-context-layers.md) | 理解 Skill、状态栏、轨迹和压缩 |
| 构建应用 | [05 Coding Agent 与 Guardrails](05-coding-guardrails.md) | 形成观察、修改、测试、纠正闭环 |
| 构建应用 | [06 Workflow、恢复与 HITL](06-workflow-recovery-hitl.md) | 划分自主决策与确定性流程 |
| 管理知识 | [07 Knowledge、Memory 与 Recall](07-knowledge-memory-recall.md) | 区分查询证据、写侧状态和会话投影 |
| 扩展协作 | [08 受限多 Agent](08-basic-multi-agent.md) | 理解 Manager 拓扑、隔离和当前限制 |
| 提升可靠性 | [09 可靠性评测](09-reliability-eval.md) | 从单次演示走向重复运行和确定性验证 |
| 持续改进 | [10 从 Bad Case 到改进提案](10-improvement-proposal.md) | 建立证据、回归集、审批门禁的离线闭环 |
| 附录 | [术语表](appendix-glossary.md) | 快速核对关键概念和项目内含义 |

## 配套材料

- [十个可运行实验](../README.md)
- [学习版 PPT 与预览](../assets/README.md)
- [架构导读](../architecture.md)
- [能力边界](../capability-boundaries.md)

## 版本与授权说明

本教材按实施计划中固定的三个仓库快照编写。理论参考
[《动手学 AI Agent》](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/README.md)，不代表原书官方课程或官方改编版；
正文采用自己的解释与项目实例，不复制原书章节。代码与文档的使用应分别遵守对应仓库许可。
