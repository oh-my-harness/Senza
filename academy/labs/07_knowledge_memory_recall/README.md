# Lab 07：Knowledge、Memory、Recall 的边界

## 要回答的问题

Knowledge、Memory 和 Session Recall 都会给模型增加信息，但它们解决的是三个不同问题：

| 能力 | 核心问题 | 当前 Senza 证据 | 本课成熟度 |
| --- | --- | --- | --- |
| Knowledge | 当前请求要从外部文档找什么？ | 本地 Markdown/text 的 BM25 + `knowledge_search`/`knowledge_read` | 可运行 |
| Memory | Agent 可以写入或忘记什么状态？ | policy + mutation gate + write/forget tools + demo store | 契约预览 |
| Session Recall | 哪些过去会话与当前请求相关？ | repo + index + source + plugin contracts | 契约预览 |

书中把 Context 与 Environment 分开：检索到的片段进入本轮 Context，原始文档、Memory
backend 和会话仓库仍是 Agent 外部状态。不能因为这些信息最后都出现在 Prompt 中，就把
三个子系统当成同一个“记忆功能”。

理论参考：[`ai-agent-book/book/chapter3.md`](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter3.md) 的
Knowledge、Memory 与 RAG 分层；Agent/Environment 边界见
[`chapter1.md`](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)。

## 先运行真实的离线检索证据

recorded 模式不重放一个虚构的检索结果，而是用 Python 标准库实现最小 Okapi BM25，
现场索引 `fixtures/` 中三篇 Senza 文档并输出排序分数：

```powershell
python academy/labs/07_knowledge_memory_recall/demo.py
python academy/labs/07_knowledge_memory_recall/demo.py --top-k 2
```

实现包含词频、文档频率、IDF 与长度归一化，测试固定验证：Knowledge 查询首先命中
`knowledge_bm25.md`，Memory/Recall 查询首先命中 `memory_recall.md`。这证明 BM25
检索机制与证据排序，不证明 Senza binding 或真实模型已经运行。

## 对应到真实 Senza

Senza 的 `local_source` 对本地文本和 Markdown 使用 BM25，而不是稠密向量、混合检索或
reranker。真实 RAG 应运行权威 live example；Academy 不复制第二份 Senza 接入代码：

```powershell
python academy/labs/07_knowledge_memory_recall/demo.py --mode live --live-example rag
```

该命令委托到 `live-tests/examples/36_rag_qa.py`，由真实 Senza
`local_source`、Knowledge Plugin、Provider 与工具调用证明 RAG 路径。

也可以查看三类组件如何装配：

```powershell
python academy/labs/07_knowledge_memory_recall/demo.py --mode live --live-example infra
```

它委托到 `23_infra_integration.py`。该示例只证明装配和 Knowledge/RAG 路径，不证明
Memory 写后读取或 Session Recall E2E。

## Memory：这里只能做契约预览

当前 Python API 暴露 Memory write policy、可选 mutation gate、`memory_write` /
`memory_forget` 和 Senza 内置 store。必须同时看清三条边界：

1. 内置 `memory_store()` 是进程内 `Mutex<Vec>` demo，不持久化；
2. `gate=None` 当前默认 `AllowAllGate`，不能把缺省值宣传成安全审批；
3. `source_id == read_source_id` 只是 MemoryService 的契约校验。写入 store 不会自动同步到
   `local_source`，也不会自动变成 `knowledge_search` 可检索内容。

所以本课的 Memory 事件使用 `kind: "memory"` 与 `status: "preview"`，不使用一段预录的
“下次启动成功记住用户偏好”来冒充持久 Memory。

## Session Recall：缺少公开的索引填充链路

Senza 已有 SessionRepo、RecallIndex、SessionRecallKnowledgeSource 和 HistoryRecallPlugin
的 Python 构造接口。但当前 Python surface 没有公开 projector/index population 完整链路。
创建一个空 index 再挂载 plugin，只能证明对象可装配，不能证明它能召回过去会话。

因此本课 maturity 是 `preview`：Knowledge/BM25 部分真运行；Memory 与 Recall 只展示
contract preview。产品后续补齐持久 backend 与 projector 后，应先增加 E2E 测试，再升级
课程成熟度。

## 观察点

1. Knowledge 的输出必须带文档 ID/分数等可复核证据；
2. Store 决定写到哪里，Plugin 只把能力挂进 Agent，二者不是同一个角色；
3. “能构造对象”不等于“数据链路已填充”；
4. RAG 命中不能替代 Memory 写后读或跨会话 Recall 的测试；
5. recorded trace 中 `knowledge` 与 `memory` 是两类事件，边界会被离线测试锁定。
