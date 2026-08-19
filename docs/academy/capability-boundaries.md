# Academy 能力边界

课程把能力分成三个成熟度等级：

- **stable**：当前 API 与测试可以直接证明，允许作为框架能力演示；
- **teaching**：Academy 提供教学应用层或 recorded runner，不能说成 Runtime 内建平台；
- **preview**：底层契约已存在，但 Python 端到端链路或生产后端尚不完整。

| 能力 | 等级 | 可安全表述 | 不应表述为 |
| --- | --- | --- | --- |
| Agent Core / Tool Calling | stable | Runtime 维护模型—工具闭环 | 模型自己可靠地执行环境动作 |
| 12 Hooks | stable | 固定生命周期扩展边界 | 任意源码位置插桩 |
| Plugin | stable | 构建期能力贡献与组合 | built harness 的热插拔系统 |
| Workflow / restore_from_step / HITL | stable | 步骤边界的编排、恢复、审批 | 可抢占任意进行中的 Provider 请求 |
| Local Knowledge | stable | 本地文本/Markdown BM25 RAG | 向量/混合检索与 reranker |
| Memory | preview | 写策略、gate、write/forget 和进程内 demo store | 生产持久化且写后自动可检索的长期记忆 |
| Session Recall | preview | repo/index/source/plugin 的装配契约 | Python 已有完整 projector 与索引填充链路 |
| Spawn | teaching | 纯推理子任务的上下文隔离和消息生命周期 | 带专业工具/profile 的 Coding/Research 团队 |
| SafetyDefaults / OS env | stable with limits | 黑名单、词法路径检查与工作目录解析 | symlink/junction 隔离、完整 shell 语义验证或强 OS 沙箱 |
| Audit / usage / budget | stable | 可靠性评测的数据输入 | 通用 eval 或 LLM-as-Judge 平台 |
| Academy eval runner | teaching | JSONL cases、重复运行、确定性 verifier | Runtime 内建产品能力 |
| Improvement proposal | teaching | 离线候选、保留集、人工批准 | 在线自动改写并发布自身 |
| SFT / RL | external | Runtime 可输出轨迹供训练系统消费 | Runtime/Senza 已提供后训练系统 |

升级某项成熟度前，必须先加入能够证明新声明的端到端测试，再同步课程、README、API
文档与 PPT。只增加接口名或装配对象不足以把 preview 升为 stable。
