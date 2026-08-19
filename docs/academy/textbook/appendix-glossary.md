# 附录：术语表

| 术语 | 本教材中的含义 |
| --- | --- |
| Agent | 能在上下文中选择行动、观察结果并持续推进任务的系统；不是单独的模型调用 |
| Agent Core | Runtime 中维护 run/turn/model/tool 循环、状态和收敛规则的稳定控制内核 |
| Harness | 模型之外负责上下文、工具接口、约束、验证和纠正的工程系统 |
| Run | 用户一次 `prompt()` 所触发的完整执行，内部可以包含多个 turn |
| Turn | 一次 Provider 决策及其后续工具处理所构成的循环单元 |
| Tool | 模型可选择的结构化行动接口；callback 连接 Harness 与真实 Environment |
| Observation | 工具执行或环境查询产生、重新进入轨迹的结果 |
| Hook | Agent Core 预定义生命周期边界上的扩展协议；Runtime 当前定义 12 种 |
| Plugin | 在构建期向 Harness 或 Workflow step 贡献能力的复用单元 |
| Builder | 收集 Provider、Tool、Hook、Plugin 和策略配置并构造 Harness 的对象 |
| Environment | Agent 边界外的文件、进程、网页、数据库和其他真实状态 |
| Context | 当前模型调用可见的信息集合，不等同于一段字符串 Prompt |
| Skill | 按需披露的任务知识或操作说明，用于控制稳定上下文的大小 |
| StatusPanel | 显式呈现当前状态的上下文组件，避免模型从长轨迹中反推关键状态 |
| Compaction | 将旧轨迹压缩为较短表示，同时尽量保留任务意图、状态和证据 |
| KnowledgeSource | 面向检索的只读 `search/read` 协议 |
| MemoryStore | 长期状态的写侧 `upsert/delete` 后端；写入不等于已经可检索 |
| Session Recall | 从权威会话仓库构建可重建检索投影，再按权限召回历史内容的机制 |
| Workflow | 显式定义节点、路由、恢复点和审批边界的确定性执行图 |
| HITL | Human in the Loop；把人的批准、补充或否决作为显式外部事件 |
| Spawn | 主 Agent 创建并管理隔离子 Agent 的运行时能力 |
| Audit | 面向追责和复核的结构化行为记录，不自动等同于评测 |
| Pass@k | 多次尝试中至少一次成功的能力上限指标 |
| Pass^k | 连续多次都成功的可靠性指标 |
| Recorded | 无 Provider 的审阅轨迹，用来稳定讲解因果关系和做离线断言 |
| Live | 使用当前 Senza API、真实 Provider 或真实后端执行的验证模式 |
