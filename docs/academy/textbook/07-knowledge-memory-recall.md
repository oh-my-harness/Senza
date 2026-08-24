# 第 7 章：Knowledge、Memory 与 Session Recall

> 本章成熟度：Local Knowledge 为 `stable`；Academy 的离线 BM25 实现为
> `teaching`；Memory 与 Session Recall 的当前 Python 端到端路径为 `preview`。

## 本章回答的问题

Agent 最终都把信息放进模型上下文，那么“查知识”“记住用户偏好”和“找回过去会话”是不是
同一件事？不是。它们共享检索、引用和上下文注入等技术，但管理的是不同来源、不同生命周期、
不同写权限的数据。

本章回答四个具体问题：

1. Knowledge、MemoryStore 和 Session Recall 分别保存什么；
2. 为什么 `memory_write` 成功不等于内容已经可以被 `knowledge_search` 找到；
3. 为什么 Recall index 只是 SessionRepo 的可重建投影，而不是会话权威数据；
4. 当前 Senza Python 哪些路径可以真实运行，哪些只能作为契约预览。

## 学习目标与先修知识

学完本章，你应当能够：

- 根据数据的所有者、生命周期和读写方向选择 Knowledge、Memory 或 Recall；
- 解释 local Knowledge 的 BM25 排序，而不把它说成向量或混合检索；
- 画出 Memory 的 policy、mutation gate、store 与 read source 的职责边界；
- 识别“对象装配成功”和“索引已有数据、可端到端召回”之间的证据差异；
- 为持久 Memory 或 Session Recall 补齐后端、投影和测试，而不是只增加一个 Plugin 名称。

建议先阅读第 4 章的上下文分层，并了解 Tool 与 Plugin 的基本概念。理论背景可参考本地
[《动手学 AI Agent》第 3 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter3.md)。

## 理论直觉：三个系统，三个问题

书中区分面向所有用户的共享知识、面向某个用户的长期记忆，以及一段会话内按时间追加的轨迹。
换成工程语言，最重要的不是它们最后是否出现在 Prompt，而是它们在进入 Prompt 之前由谁负责、
能否修改、何时过期，以及如何核对来源。

| 能力 | 它回答的问题 | 典型权威数据 | 主要方向 |
| --- | --- | --- | --- |
| Knowledge | 当前请求需要查哪份外部证据？ | 文档库、规则库、代码说明 | 搜索与读取 |
| MemoryStore | Agent 获准写入或忘记什么长期状态？ | 用户偏好、经审查的事实、应用状态 | 写入与删除 |
| Session Recall | 哪些过去会话与当前请求相关？ | SessionRepo 中的会话轨迹 | 投影、搜索、精确回读 |

### Knowledge 是取证，不是“模型突然记起”

RAG 的最小循环是“查询 → 排序 → 读取 → 注入上下文 → 生成”。Senza 的 local Knowledge
先索引本地 Markdown/text，再用 BM25 根据词频、文档频率和文档长度做稀疏排序。BM25 擅长
标识符、专有名词和明确关键词，不需要 embedding 服务；它也会受同义词、语义改写和分词方式
限制。因此当前能力应准确称为 **BM25 本地检索**，不能写成向量检索、混合检索或 reranker。

### Memory 是受控写侧，不天然等于读侧

Memory 的困难不只是“把字符串存下来”，而是决定谁可以写、写什么、保留多久、如何去重、怎样
删除，以及后续从哪里读。Runtime 因此刻意把 `MemoryStore` 定义为写侧接口；它不继承
`KnowledgeSource`。写侧可以返回一个指向读侧的引用，但真正可检索还需要读后端同步、建索引并
由 KnowledgeSource 暴露。

这条分离很有价值：生产系统可以用事务数据库承接写入，用搜索索引承担读取，两者采用立即一致
或最终一致策略。不过，它也意味着不能从“收到写入回执”推导出“下一次搜索一定命中”。

### Session Recall 是会话权威的可丢弃投影

历史会话原文属于 SessionRepo。Recall index 只保存便于搜索的投影，可以重建、替换或删除；
命中后仍应重新打开当前 Session 权威数据做精确读取。这样，索引过期不会变成新的事实来源，
会话的删除、权限和最新修订仍由 SessionRepo 决定。

## Runtime/Senza 架构映射

```text
Knowledge
本地 Markdown/text ── BM25 index ── KnowledgeSource
                                      ├─ knowledge_search
                                      └─ knowledge_read

Memory
memory_write/forget ── policy ── mutation gate ── MemoryStore
                                                   │
                           需要应用另行同步/索引 ────┘
                                                   ▼
                                             read source

Session Recall（目标装配）
SessionRepo ── ObservedSessionRepo/Projector ── RecallIndex
     ▲                                            │ search
     └────────── exact read ── Recall Source ─────┘
                                  │
                         transform_context Hook
```

对应到当前实现：

| 层次 | Runtime/Senza 组件 | 当前证据 |
| --- | --- | --- |
| Knowledge 读侧 | `LocalDocumentSource`、`Bm25DocumentSearchIndex`、`KnowledgePlugin` | `stable`，真实 live RAG 可运行 |
| Memory 写侧 | `MemoryWritePolicy`、`MemoryMutationGate`、`MemoryStore`、`MemoryPlugin` | `preview`，契约存在，Senza store 仅为 demo |
| Recall 权威与投影 | `SessionRepo`、`SessionRecallProjector`、`SessionRecallIndex` | Runtime 契约存在 |
| Recall 注入 | `SessionRecallKnowledgeSource`、`HistoryRecallPlugin` | Python 可构造部分对象，但完整填充链路未公开 |

Plugin 在这里仍是构建期能力包。Knowledge Plugin 注册两个读工具；Memory Plugin 注册写入与
忘记工具；History Recall Plugin 在 `transform_context` Hook 注入受预算约束的历史片段。Store、
索引、文件系统和 SessionRepo 则是外部状态后端，不会因为 Plugin 被安装就自动出现数据。

## 一条完整执行故事

假设 Developer Agent 收到三个连续请求。

### 第一幕：从框架文档取证

用户问：“Senza 的 local Knowledge 用什么检索？”Agent 调用 `knowledge_search`。本地 source
用 BM25 对已索引文档排序，返回文档引用和分数；Agent 再调用 `knowledge_read` 读取命中内容，
最后回答“当前是 BM25”，并保留文档引用。这里发生的是外部知识取证，原始文档仍在 Agent
上下文之外。

### 第二幕：写入一条偏好

用户说：“以后回答先给结论，请记住。”模型可以发起 `memory_write`。服务先让 write policy
规范化内容、TTL 和幂等信息，再经过 mutation gate，最后调用 store。当前 Senza 内置 store 把
数据放进进程内的 `Mutex<Vec>` 并返回引用。

这时必须停下来核对证据：

- 当前进程中的 vector 有了记录；
- 没有文件或数据库持久化，进程退出后记录消失；
- 这次写入没有同步到配对的 local Knowledge source；
- 所以下一次 `knowledge_search` 不会因此自动命中“先给结论”。

若产品需要真正长期记忆，应用必须提供持久 store、可读 source、同步/索引策略以及写后读测试。

### 第三幕：新会话想找回旧讨论

理想链路是：旧 Session 的变更被 `ObservedSessionRepo` 观察，Projector 把可召回分支写入 index；
新 Run 带着受信任的访问上下文和 recall request，History Recall Plugin 搜索 index，再从
SessionRepo 精确回读，把历史作为“不可信数据”有界注入本轮上下文。

Runtime 已定义这条链路，但当前 Senza Python surface 只暴露 repo、index、source 和 plugin 的
部分构造函数，没有完整公开 projector/index population 装配，也没有一条已证明的 Python E2E
填充路径。因此本幕只能停在 `preview`：能构造空 index 不等于能找回旧会话。

## 源码导读

建议按“真实可运行 → 写侧边界 → Recall 缺口”的顺序阅读：

1. [Runtime BM25 index](https://github.com/oh-my-harness/llm-harness-runtime/blob/03aed0ce550aa0c95cb26d9667f6440bc3dd3349/crates/llm-harness-knowledge-local/src/index.rs)：
   看 `Bm25DocumentSearchIndex::build` 如何计算文档频率，`search` 如何做长度归一化与排序。
2. [Senza local source](../../../src/knowledge/pylocalsource.rs) 与
   [Knowledge Plugin binding](../../../src/knowledge/pyknowledge.rs)：前者创建本地文档 source，
   后者把 source 注册进 registry 并贡献 `knowledge_search`/`knowledge_read`。
3. [Runtime MemoryStore](https://github.com/oh-my-harness/llm-harness-runtime/blob/03aed0ce550aa0c95cb26d9667f6440bc3dd3349/crates/llm-harness-memory/src/store.rs)：
   注意它只定义 descriptor、`upsert` 和 `delete`，并明确不继承 KnowledgeSource。
4. [Senza Memory binding](../../../src/knowledge/pymemory.rs)：查看 `InMemoryStore` 的
   `Mutex<Vec>`、`AllowAllGate` 缺省值，以及 store/source ID 只做契约匹配而没有同步代码。
5. [Runtime Session Recall 入口](https://github.com/oh-my-harness/llm-harness-runtime/blob/03aed0ce550aa0c95cb26d9667f6440bc3dd3349/crates/llm-harness-session-recall/src/lib.rs)、
   [Projector](https://github.com/oh-my-harness/llm-harness-runtime/blob/03aed0ce550aa0c95cb26d9667f6440bc3dd3349/crates/llm-harness-session-recall/src/projector.rs) 和
   [History Recall Plugin](https://github.com/oh-my-harness/llm-harness-runtime/blob/03aed0ce550aa0c95cb26d9667f6440bc3dd3349/crates/llm-harness-session-recall/src/plugin.rs)：
   入口文档列出完整装配条件；Projector 建投影；Plugin 在 `transform_context` 读取并注入。
6. [Senza Recall binding](../../../src/knowledge/pysessionrecall.rs)：对照上一步，找出当前公开构造函数
   中缺少的 projector、observer 和 index population 路径。

一个实用的源码阅读问题是：“如果我只执行这个构造函数，数据从哪里来？”若答案只是“创建了
一个空对象”，就不能把它当成召回成功的证据。

## 配套实验

实验入口是 [Lab 07 README](../../../academy/labs/07_knowledge_memory_recall/README.md)。在 Senza
仓库根目录运行：

```powershell
# 默认：现场索引三篇 fixture，运行无依赖的教学 BM25
python academy/labs/07_knowledge_memory_recall/demo.py
python academy/labs/07_knowledge_memory_recall/demo.py --top-k 2

# 验证真实 Senza local_source + Provider + Knowledge tools
python academy/labs/07_knowledge_memory_recall/demo.py --mode live --live-example rag

# 查看三类基础设施的装配；不把它当成 Memory/Recall E2E
python academy/labs/07_knowledge_memory_recall/demo.py --mode live --live-example infra

python -m pytest academy/labs/07_knowledge_memory_recall/test_demo.py -q
```

默认模式会用 [教学 BM25 实现](../../../academy/labs/07_knowledge_memory_recall/retrieval.py)
对三篇受控文档排序。请记录两个查询的第一名、分数和文档 ID，再完成两个小实验：

1. 把查询中的 `BM25` 换成一个 fixture 未出现的同义表达，观察稀疏检索的边界；
2. 阅读 expected trace，分别标出哪些事件是 `knowledge`、哪些只是 `memory` preview。

recorded 结果证明算法和课程证据排序可复现，不证明 Python binding、Provider 或真实工具回调已
执行；真实 RAG 由 `36_rag_qa.py` 负责证明。

## 常见误解与能力边界

### “BM25 demo 跑通，所以 Senza 的一切记忆都可检索”

错误。Academy 的 BM25 是 `teaching` 实现；真实 local Knowledge 的 BM25 路径是 `stable`；
Memory 和 Session Recall 仍是另外两条数据链路。

### “MemoryStore 就是 Knowledge 数据库”

错误。Runtime 明确把 MemoryStore 设计成写侧。当前 Senza 内置 store 非持久化，且写入不会自动
进入 local Knowledge source。`read_source_id` 一致只证明引用契约相容，不证明数据已复制。

### “缺省 gate 表示 Runtime 默认安全批准”

错误。Runtime 的可信 mutation boundary 要求显式实现 gate；Senza Python wrapper 在未提供 gate
时选择了 `AllowAllGate`，这是方便演示的宽松默认，不是审批或安全保证。

### “创建 SQLite recall index 就有跨会话记忆”

错误。持久 index 仍需要 projector 填充和更新，还需要 Run 的访问扩展。当前 Python 没有完整公开
projector/index population 链路，因此 Recall 只能标记为 `preview`。

### “历史片段进入 Context 后就可信”

错误。Recall Plugin 把历史标成不可信数据，并受命中数、字节数、token 与超时预算约束。来源、
权限和当前请求优先级仍需保留。

完整成熟度口径见 [Academy 能力边界](../capability-boundaries.md)。

## 小结

Knowledge 管“读哪份外部证据”，MemoryStore 管“获准写入或删除什么状态”，Session Recall 管
“怎样从会话权威数据建立可重建投影并找回相关历史”。三者可以共享 registry、引用和上下文注入
机制，却不能共享未经证明的能力结论。当前最稳妥的说法是：local Knowledge/BM25 可运行；
Memory 有写侧契约和进程内 demo；Session Recall 有底层契约，但 Python 投影填充链路未完整公开。

## 复习题

1. 为什么 MemoryStore 不继承 KnowledgeSource？这种分离给生产架构带来什么好处和额外工作？
2. `memory_write` 返回 `Visible` 时，为什么仍不能断言 `knowledge_search` 会立刻命中？
3. SessionRepo 与 RecallIndex 哪一个是权威数据？索引命中后为什么还要精确回读？
4. Academy BM25、Senza local Knowledge 和 Session Recall 分别应标成什么成熟度？
5. 若要把 Memory 从 preview 升为 stable，至少需要补哪三类后端或端到端证据？
6. 为什么历史会话内容应作为不可信数据注入，而不是直接变成系统指令？

## 延伸阅读

- [《动手学 AI Agent》第 3 章：用户记忆和知识库](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter3.md)
- [Lab 07：Knowledge、Memory、Recall 的边界](../../../academy/labs/07_knowledge_memory_recall/README.md)
- [真实 RAG 示例](../../../live-tests/examples/36_rag_qa.py)
- [基础设施装配示例](../../../live-tests/examples/23_infra_integration.py)
- [教材术语表](appendix-glossary.md)
