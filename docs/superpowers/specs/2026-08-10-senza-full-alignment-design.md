# Senza 全量对齐 llm-harness-runtime 设计文档

> 日期：2026-08-10
> 状态：已确认，待实现
:> 范围：将 Senza Python SDK 全量对齐到 runtime `5eae99e`（v0.5.0），覆盖 9 个新 crate 的 PyO3 绑定、src/ 目录重组、examples 全能力覆盖。

---

## 背景

:Senza 当前 pin 在 runtime `247e380`，落后 91 个 commit。runtime 已从 v0.4.x 升级到 v0.5.0，新增 9 个 crate（strategy / knowledge / knowledge-local / session-recall / memory / audit-jsonl / trace-otel / sandbox-bwrap / sandbox-seatbelt），现有 crate 也新增了 grep/glob 工具、BashTool 截断、LoopSafety、内置 EventStream 实现等能力。Senza 需全量对齐。

### 决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 范围 | 全量对齐 | 用户明确要求 |
| 暴露粒度 | YAGNI 筛选 | 只暴露有真实 Python 用户场景的 API，跳过内部契约/测试类型 |
| src/ 结构 | 按 crate 分子目录 | 文件数从 22 增至 ~37，flat 不可维护 |
| examples | 不按编号对齐 live-tests，但覆盖所有已暴露能力 | 用户明确 |
| 执行方式 | 按 crate 组分 4 阶段 | 每阶段独立验证，出问题隔离在阶段内 |

---

## 执行阶段

### 阶段 1：Foundation

#### 1.1 Pin 升级 + 破坏性变更修复

**Pin 升级**：

Cargo.toml 中所有 `llm-harness-*` 依赖的 rev 从 `247e380ed4d9ea1b0d2b2f275637c4cab27acc66` 推到 `5eae99ed1c42dd558529bede9957518ba15eef5c`。新增以下 crate 依赖：

- `llm-harness-strategy`
- `llm-harness-runtime-knowledge`
- `llm-harness-runtime-knowledge-local`
- `llm-harness-runtime-session-recall`
- `llm-harness-runtime-memory`
- `llm-harness-runtime-audit-jsonl`
- `llm-harness-runtime-trace-otel`
- `llm-harness-runtime-sandbox-bwrap`（仅 Linux 编译）
- `llm-harness-runtime-sandbox-seatbelt`（仅 macOS 编译）

同步更新 `senza-pkg/runtime.lock`。

**已知破坏性变更**：

- `follow_up_message` 返回 `Result` 而非静默丢弃 — `pyharness.rs` 中对应 Python 方法需处理 `Err` 分支，转为 Python 异常。
- `compaction_prompt` / `compaction_query` setter 新增 — 不破坏现有 API，需补充绑定。
- 其余破坏性变更在升级后编译时发现并逐一修复。

**验证**：`cargo build` 通过 + 现有 22 个测试文件全绿。

#### 1.2 src/ 目录重组

从 flat 22 文件重组为按 crate 分组：

```
src/
├── lib.rs                    # module 入口（更新 mod 声明路径）
├── shared/                   # 跨 crate 共享基础设施
│   ├── value_conv.rs
│   ├── event_stream.rs
│   ├── pyerror.rs
│   └── pylogging.rs
├── core/                     # llm-harness-agent + loop + types
│   ├── pyharness.rs
│   ├── pybuilder.rs
│   ├── pytool.rs
│   ├── pyplugin.rs
│   ├── pyprovider.rs
│   ├── pyhooks.rs
│   ├── pyeventstream.rs
│   ├── pyresponseformat.rs
│   ├── pyagent.rs
│   ├── pyloop.rs
│   └── pyviewer.rs
├── runtime/                  # llm-harness-runtime
│   ├── pyworkflow.rs
│   ├── pybudget.rs
│   ├── pyrules.rs
│   ├── pyskills.rs
│   ├── pymcp.rs
│   └── pypricing.rs
├── strategy/                 # 阶段 2 填充
├── knowledge/                # 阶段 3 填充
└── infra/                    # 阶段 4 填充
```

**原则**：只移动文件位置 + 更新 `mod` 声明，不改文件内容。`pyworkflow.rs`（87KB）和 `pyhooks.rs`（53KB）的内部拆分不在本次范围内。

#### 1.3 现有 crate 新能力暴露

属于 Senza 已依赖的 crate 但未暴露到 Python 的能力：

| 能力 | 来源 crate | Python 绑定 | 场景 |
|------|-----------|-------------|------|
| `GrepTool` / `GlobTool` | runtime-tools | 加入 `create_fs_tools_plugin()` 自动注册 | 文件搜索是 coding agent 基本需求 |
| BashTool 输出截断 | runtime-tools | `create_fs_tools_plugin()` 自动获得 | 长输出不爆上下文 |
| `compaction_prompt(query)` setter | runtime builder | `HarnessBuilder.compaction_prompt()` / `.compaction_query()` | 自定义压缩提示 |
| `UsageLedger` | runtime | `harness.usage_ledger()` 返回共享状态 | 多 agent 共享用量统计 |
| `WorkflowRunRequest` | runtime | `WorkflowEngine` 新方法 | 可配置的 run 请求 |

**验证**：新增绑定有对应 Python 测试覆盖；`scripts/check_stubs.py` 零偏差。

---

### 阶段 2：Strategy 层绑定

#### 2.1 暴露清单

从 strategy crate 50+ 公开类型中，按真实场景筛选：

| 绑定 | Python API | 场景 |
|------|-----------|------|
| `SafetyDefaultsPlugin` | `create_safety_defaults_plugin(env, config?)` | bash 黑名单 + 路径穿越防护 |
| `LoopSafetyPlugin` | `create_loop_safety_plugin(config)` | 死循环/重复/失败断路器 |
| `StatusPanelPlugin` | `create_status_panel_plugin(config)` | 状态栏 XML 注入 + todo_write 工具 |
| `MemoryDefensePlugin` | `create_memory_defense_plugin(builder)` | 持久记忆注入防御 |
| `InjectionFilterPlugin` | `create_injection_filter_plugin(patterns)` | prompt 注入检测过滤 |
| `SourceTagPlugin` | `create_source_tag_plugin(entries)` | 来源标记包装 |
| `ProjectInstructionPlugin` | `create_project_instruction_plugin(env, config?)` | 项目指令文件自动注入 |
| `AuditPlugin` | `create_audit_plugin(sink)` | 工具调用审计 |
| `NotifyPlugin` + `NotifyUserTool` | `create_notify_plugin(channel)` | 主动通知用户 |
| `ToolOutputGuardPlugin` | `create_tool_output_guard_plugin(env, config?)` | 工具输出截断兜底 |
| 内置 EventStream | `create_timer_stream()` / `create_heartbeat_stream()` / `create_filter_stream()` / `create_webhook_stream()` | 定时器/心跳/过滤/webhook |
| `context_aware_prompt_spec()` | `create_context_aware_compaction_prompt()` | context-aware 压缩提示 |

**不暴露**（无直接 Python 用户场景）：

- `CommandTokenizer` / `DefaultCommandBlacklist` — SafetyDefaultsPlugin 内部实现
- `ToolCallCounter` / `ToolCallCounterHook` — StatusPanel 内部
- `TodoStore` / `TodoWriteTool` / `TodoItem` — StatusPanel 内部，通过 plugin 整体暴露
- `SideChannelCollector` / `EnvironmentCollector` — 内部采集器
- `DeathSpiralGuardHook` / `FailureCircuitBreakerHook` 等单独 hook — 通过 LoopSafetyPlugin 整体暴露
- `render_status_xml` / `is_status_text` — 内部工具函数

#### 2.2 配置类型策略

- **简单配置** → Python dict 作为参数，Rust 侧反序列化（如 `LoopSafetyConfig` 从 dict 构造）
- **Builder 模式** → 暴露为 Python builder class（如 `MemoryDefensePluginBuilder` → `senza.MemoryDefensePluginBuilder`）
- **无配置或有默认** → 零参数构造函数

#### 2.3 文件组织

```
src/strategy/
├── mod.rs              # re-exports
├── pysafety.rs         # SafetyDefaultsPlugin
├── pyloopsafety.rs     # LoopSafetyPlugin + config
├── pystatuspanel.rs    # StatusPanelPlugin + config
├── pymemorydefense.rs  # MemoryDefensePlugin + builder
├── pyinjection.rs      # InjectionFilterPlugin + patterns
├── pysourcetag.rs      # SourceTagPlugin
├── pyprojectinstr.rs   # ProjectInstructionPlugin
├── pyaudit.rs          # AuditPlugin
├── pynotify.rs         # NotifyPlugin + NotifyUserTool + channel
├── pytoolguard.rs      # ToolOutputGuardPlugin
├── pyeventstreams.rs   # timer/heartbeat/filter/webhook streams
└── pycompaction.rs     # context_aware_prompt_spec
```

**验证**：每个绑定有 Python 测试；至少一个 example 演示 strategy plugin 组合使用；stub 零偏差。

---

### 阶段 3：Knowledge + Memory + SessionRecall 绑定

三个 crate 有依赖关系：memory 依赖 knowledge 的 `KnowledgeSource` trait，session-recall 依赖 knowledge 的 registry/citation 体系。

#### 3.1 Knowledge（llm-harness-runtime-knowledge + knowledge-local）

| 绑定 | Python API | 场景 |
|------|-----------|------|
| `LocalDocumentSource` | `create_local_knowledge_source(path, config?)` | 本地 Markdown/text 文档作为知识源 |
| `KnowledgeRegistry` | `senza.KnowledgeRegistry` (builder) | 注册多个知识源 + 访问控制 |
| `KnowledgePlugin` | `create_knowledge_plugin(registry, config)` | 将知识工具注册到 harness |
| `KnowledgeToolConfig` | dict 参数 | 配置知识工具行为 |

**不暴露**：

- `KnowledgeAccessControl` / `KnowledgeAuthorizer` / `AllowAllAuthorizer` — 通过 registry builder 内部处理
- `CitationRecord` / `EvidenceProviderId` / `KnowledgeCitationPolicy` — citation 校验是 plugin 内部行为
- `KnowledgeError` / `KnowledgeErrorCode` — 转为 Python 异常
- `contract` 模块 — test-utils only
- `Bm25DocumentSearchIndex` / `DocumentParserRegistry` / `IndexedDocument` 等 — LocalDocumentSource 内部实现

knowledge-local 不单独暴露 — 通过 `create_local_knowledge_source()` 封装。

#### 3.2 Memory（llm-harness-runtime-memory）

| 绑定 | Python API | 场景 |
|------|-----------|------|
| `MemoryService` | `create_memory_service(store, config?)` | 记忆服务组合（读源 + 写存储） |
| `MemoryPlugin` | `create_memory_plugin(service)` | 将记忆工具（write/forget）注册到 harness |
| `MemoryStore` trait | `create_sqlite_memory_store(path)` / `create_in_memory_store()` | 持久化/临时记忆存储 |
| `SecureMemoryWritePolicy` | `create_secure_write_policy(config)` | 安全写入策略 |

**不暴露**：

- `MemoryMutationGate` / `MemoryContentGuard` / `DefaultMemoryContentGuard` — 内部授权机制
- `MemoryProvenance` / `MemoryWriteIntent` / `MemoryMutationRequest` — 内部请求类型
- `MemoryWriteTool` / `MemoryForgetTool` — 通过 plugin 整体暴露
- `MemorySessionId` — 内部标识
- 各种 error/enum 类型 — 转为 Python 异常或 dict

#### 3.3 SessionRecall（llm-harness-runtime-session-recall）

| 绑定 | Python API | 场景 |
|------|-----------|------|
| `SessionRecallProjector` | `create_session_recall_projector(repo, index)` | 投影器：从 session repo 构建索引 |
| `SqliteSessionRecallIndex` | `create_sqlite_session_recall_index(path)` | SQLite 持久化索引 |
| `InMemorySessionRecallIndex` | `create_in_memory_session_recall_index()` | 临时索引 |
| `ObservedSessionRepo` | `create_observed_session_repo(repo, projector)` | 包装 repo 自动投影 |
| `SessionRecallKnowledgeSource` | `create_session_recall_knowledge_source(service)` | 作为知识源接入 registry |
| `HistoryRecallPlugin` | `create_history_recall_plugin(config)` | 将历史召回工具注册到 harness |

**不暴露**：

- `SessionRecallAccessContext` / `HistoryRecallRequest` — 内部扩展上下文
- `SessionRecallRef` / `SessionRecallDocument` / `SessionRecallCandidate` — 内部数据类型
- `SessionRecallUriMapper` trait — 内部映射，默认行为够用
- `SessionRecallBudget` — 内部预算控制

sqlite feature gate — `create_sqlite_session_recall_index` 在 Cargo.toml 启用 `sqlite` feature。

#### 3.4 文件组织

```
src/knowledge/
├── mod.rs                  # re-exports
├── pyknowledgeregistry.rs  # KnowledgeRegistry builder + KnowledgePlugin
├── pylocalsource.rs        # LocalDocumentSource + config
├── pysessionrecall.rs      # projector + index + knowledge source + plugin
└── pymemory.rs             # MemoryService + MemoryPlugin + store + policy
```

#### 3.5 Examples 覆盖

- 本地文档知识源 RAG（升级现有 `15_rag_qa.py`）
- 记忆服务写入+读取+遗忘
- 跨会话历史召回

**验证**：Python 测试覆盖每个绑定；stub 零偏差；knowledge/memory/session-recall 三者组合场景至少一个 example。

---

### 阶段 4：Infra 层 + 收尾

#### 4.1 Infra 绑定

| 绑定 | Python API | 场景 |
|------|-----------|------|
| `JsonlAuditSink` | `create_jsonl_audit_sink(path)` | SHA-256 哈希链审计日志 |
| `InMemoryTraceExporter` | `create_in_memory_trace_exporter()` | 测试用 trace 导出 |
| `BwrapSandbox` | `create_bwrap_sandbox(config)` | Linux bwrap 真隔离沙箱 |
| `SeatbeltSandbox` | `create_seatbelt_sandbox(config)` | macOS Seatbelt 真隔离沙箱 |

**不暴露**：

- `JsonlAuditSink::validate()` / `compute_hash()` — 内部完整性校验
- `SpanEvent` — 内部 trace 数据结构
- sandbox 的 `SandboxConfig` / `ResourceLimits` — 通过 dict 参数构造

**sandbox 平台处理**：bwrap 仅 Linux 编译，seatbelt 仅 macOS 编译。Python 侧用 `#[cfg(target_os)]` 条件编译，在不适用的平台上对应函数不注册（用户在错误平台上调用得到 `AttributeError`）。

#### 4.2 Examples 全量覆盖

目标：每个已暴露的能力至少有一个 example 演示。现有 28 个 example 保留，新增覆盖缺失能力：

| Example | 覆盖能力 |
|---------|---------|
| `agent/17_grep_glob.py` | grep/glob 搜索工具 |
| `agent/18_compaction_prompt.py` | 自定义 compaction_prompt/query |
| `strategy/01_safety_defaults.py` | SafetyDefaultsPlugin |
| `strategy/02_loop_safety.py` | LoopSafetyPlugin |
| `strategy/03_status_panel.py` | StatusPanelPlugin + todo_write |
| `strategy/04_memory_defense.py` | MemoryDefensePlugin |
| `strategy/05_injection_filter.py` | InjectionFilterPlugin |
| `strategy/06_source_tag.py` | SourceTagPlugin |
| `strategy/07_project_instruction.py` | ProjectInstructionPlugin |
| `strategy/08_audit.py` | AuditPlugin + JsonlAuditSink |
| `strategy/09_notify.py` | NotifyPlugin + NotifyUserTool |
| `strategy/10_tool_output_guard.py` | ToolOutputGuardPlugin |
| `strategy/11_event_streams.py` | timer/heartbeat/filter/webhook |
| `strategy/12_context_aware_compact.py` | context-aware compaction |
| `knowledge/01_local_rag.py` | 本地知识源 RAG（替代旧 15_rag_qa.py） |
| `knowledge/02_memory_service.py` | 记忆写入/读取/遗忘 |
| `knowledge/03_session_recall.py` | 跨会话历史召回 |
| `infra/01_audit_jsonl.py` | 审计日志哈希链 |
| `infra/02_tracing.py` | in-memory trace exporter |
| `infra/03_sandbox.py` | 平台沙箱（bwrap/seatbelt） |

**退役**：`agent/15_rag_qa.py` 被 `knowledge/01_local_rag.py` 替代。

**examples 目录重组**：从 `agent/` + `runtime/` 两层扩展为 `agent/` + `runtime/` + `strategy/` + `knowledge/` + `infra/`，与 src/ 目录分组对齐。

#### 4.3 Stub 更新

`senza-pkg/senza/__init__.pyi` 从 176 签名扩展。新增绑定全部补充 stub。`scripts/check_stubs.py` 保持零偏差。预期最终 stub 数约 220-240。

#### 4.4 Skills 文档更新

现有 3 个 skills 更新：

- **senza-agent** — 补充 grep/glob、compaction_prompt、UsageLedger
- **senza-workflow** — 补充 WorkflowRunRequest
- **senza-advanced** — 补充 strategy plugin 组合使用模式

新增 skill：

- **senza-strategy** — 策略层 plugin 选择指南 + 组合模式
- **senza-knowledge** — 知识源/记忆/召回配置指南

#### 4.5 文档更新

- `README.md` — 更新能力表、examples 列表、API 参考
- `docs/api-reference.md` — 新增所有绑定的方法签名
- `SENZA_DESIGN.md` — 更新缺口表（全部标记完成）、仓库结构、crate 依赖

#### 4.6 最终验证

- `./scripts/cargo_checks.sh` 全绿（fmt + clippy + cargo test + pytest）
- `scripts/check_stubs.py` 零偏差
- 每个 example 可运行（至少 import + 基本调用不报错）

---

## 阶段依赖与顺序

```
阶段 1 (Foundation)
  ├── 1.1 Pin 升级 + 破坏性变更修复
  ├── 1.2 src/ 目录重组
  └── 1.3 现有 crate 新能力暴露
        │
        ▼
阶段 2 (Strategy)
  └── 12 个绑定 + 12 个文件
        │
        ▼
阶段 3 (Knowledge + Memory + SessionRecall)
  └── 14 个绑定 + 4 个文件
        │
        ▼
阶段 4 (Infra + 收尾)
  ├── 4.1 Infra 绑定
  ├── 4.2 Examples 全量覆盖
  ├── 4.3 Stub 更新
  ├── 4.4 Skills 文档更新
  ├── 4.5 文档更新
  └── 4.6 最终验证
```

每个阶段独立 spec → plan → 实现 → 验证。阶段间有严格依赖：后续阶段的绑定代码依赖 Foundation 的 pin 升级和目录结构。

---

## 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| runtime 升级引入未知破坏性变更 | 阶段 1 编译失败 | 编译驱动修复，逐个 error 处理 |
| strategy crate 某些类型无法干净映射到 Python | 阶段 2 绑定复杂 | 用 opaque wrapper + dict 配置，不强行暴露 trait object |
| knowledge/session-recall 依赖链复杂 | 阶段 3 组装困难 | 参考 live-tests 的 tools_layer 测试用例确认正确组装方式 |
| sandbox 平台条件编译 | 非 Linux/macOS 无法测试 | CI 覆盖两个平台；本地开发用 macOS |
| stub 数量增长后手动维护成本 | check_stubs 失败 | 每个绑定同步更新 stub，不积累 |
