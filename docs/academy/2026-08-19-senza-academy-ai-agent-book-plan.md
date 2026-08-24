# Senza Academy v1：基于《动手学 AI Agent》的框架学习计划

> 状态：v1 已完成
> 日期：2026-08-19
> 负责人：Senza / llm-harness-runtime 维护团队

## 1. 背景与目标

本计划以《动手学 AI Agent》的理论体系作为学习坐标，用
`llm-harness-runtime` 和 Senza 的真实实现替换泛化示例，形成一条从“为什么需要
Harness”到“如何装配可靠 Developer Agent”的连续学习路径。

课程不是对原书逐章改名，也不把尚未具备的能力包装成现状。它要同时做到：

1. 用通俗理论解释 Runtime/Senza 的架构选择；
2. 用可运行、可回放、可测试的实验证明关键机制；
3. 明确当前能力、教学能力与后续产品能力的边界；
4. 产出可复用的课程文档、实验、评测样例与独立学习版 PPT。

核心传播命题：

> 书回答“一个可靠 Agent 为什么需要这些机制”；Runtime 提供稳定的 Agent Core、
> 生命周期边界与组合协议；Senza 让开发者用 Python 装配具体的 Developer Agent
> 与 Workflow。

## 2. 固定事实基线

首版课程按以下源码快照验收；升级依赖后需重新执行事实校准：

| 来源 | 固定版本 | 用途 |
| --- | --- | --- |
| `oh-my-harness/llm-harness-runtime` | `03aed0ce550aa0c95cb26d9667f6440bc3dd3349` | Agent Core、Hook、Plugin、Workflow 等底层契约 |
| `oh-my-harness/Senza` | `53cb8b5e71cf6c8ddf41397039adbdcfbfce2685` | Python 装配面、课程实验与用户 API |
| `bojieli/ai-agent-book` | `1d2e04ee733dde245af2eb718cfc92d2d0542b7e` | 理论解释与概念出处；以当前 Markdown 为准 |

理论材料遵循原仓库 Apache-2.0 许可。课程需注明“理论参考《动手学 AI Agent》”，
不得暗示为该书官方课程或官方改编版。

## 3. 统一架构叙事

### 3.1 四层关系

```text
Developer Agent / Workflow 应用
              │
      Senza Python 装配面
              │
 Runtime Agent Core + 13 个固定 Hook + Plugin 协议
              │
 Model Provider / Tool / Store / Knowledge / OS / MCP 等外部后端
```

- **Agent Core** 持有稳定的 Run–Turn–Model–Tool 循环、状态与收敛规则。
- **Hook** 是 Core 预先定义的 12 个生命周期边界，不允许 Plugin 任意插入源码位置。
- **Plugin** 是构建期的能力贡献与复用单元；Rust Plugin 可贡献 tools、hooks、skills、
  templates，Python `create_plugin()` 当前只开放 tools 和 hooks。
- **Senza** 是 Runtime 的 Python SDK 与装配面，不是另一套 Agent Core，也不是单一 Agent。
- **Environment** 位于 Agent 边界之外，文件、网页、数据库和执行后端都属于环境状态。

### 3.2 与书中公式的对应

```text
Agent = LLM + Context + Tools
Agent = Model + Harness
Harness = Context Management + Tool Interface + Constraints + Validation + Correction
```

Runtime 负责 Harness 中稳定、通用的控制循环和协议；Plugin 把上下文、安全、审计、
知识等横切策略装到明确边界；Senza 让应用开发者按任务选择并组合这些能力。

## 4. 课程边界与事实矩阵

| 主题 | v1 可证明的现状 | 课程必须说明的边界 |
| --- | --- | --- |
| Hook | 13 个固定生命周期点；有短路、链式变换和聚合等组合语义 | Hook 位置由 Core 定义，不是任意代码注入点 |
| Plugin | 构建期安装；可安装到 Agent 或 Workflow step | 不是运行期热插拔；Python 自定义 Plugin 仅 tools + hooks |
| Strategy | 10 个 Plugin 工厂 + 2 个 helper | 不统一宣传为“12 个 Plugin” |
| Tool 冲突 | 正式 build 拒绝重名 Tool | 不宣传“后注册覆盖前注册” |
| Spawn | 主 Agent 获得 5 个管理工具；Runtime 另定义 2 个可由 child plugin 贡献的子侧工具 | 当前 Senza 子 Agent 使用 `NoopPlugin`，不自动挂载子侧工具且不能递归 spawn；Python 无角色专属 tool/plugin/profile 注入 |
| Knowledge | 本地文本/Markdown 的 BM25 搜索和读取可端到端运行 | 不是稠密向量、混合检索或 reranker |
| Memory | 有 write policy、mutation gate 和写/忘记工具；Senza 提供内存 demo store | 当前 store 是进程内 `Mutex<Vec>`，不持久；课程不声称完整“写后长期召回” |
| Session Recall | 有 repo/index/source/plugin 契约和实现 | Python 暂无 projector/index population 的完整公开链路 |
| Safety | 黑名单、词法路径检查、规则审批、tool hook 可组合 | 当前默认链路不可靠阻止 symlink/junction 逃逸；`create_os_env()` 是工作目录解析下的真实主机环境，不等于强 OS 沙箱 |
| Trace / Audit | JSONL 审计、Hook 轨迹、usage/pricing/budget 可用 | Python 暂无通用 tracing exporter 挂载 API；观测数据不等于评测平台 |
| Evaluation | v1 新增教学用离线 runner、确定性 verifier 与报告 | 不宣称 Runtime 已内建通用 eval、Pass@k 或 LLM-as-Judge 平台 |
| Continuous Improvement | 可从 bad case 生成 Plugin/Skill 候选并在保留集验证 | 仅生成待审批提案；不自动安装、不自我修改安全机制 |
| Model Training | Runtime 可产出轨迹与验证结果 | SFT/RL/奖励训练属于外部系统，不在 v1 实现范围 |

## 5. 交付目录

```text
Senza/
├── docs/academy/
│   ├── 2026-08-19-senza-academy-ai-agent-book-plan.md
│   ├── README.md
│   ├── architecture.md
│   └── capability-boundaries.md
└── academy/
    ├── README.md
    ├── common/
    ├── labs/
    │   ├── 01_react_tool_calling/
    │   ├── 02_hook_xray/
    │   ├── 03_plugin_db_safety/
    │   ├── 04_context_layers/
    │   ├── 05_coding_guardrails/
    │   ├── 06_workflow_recovery_hitl/
    │   ├── 07_knowledge_memory_recall/
    │   ├── 08_basic_multi_agent/
    │   ├── 09_reliability_eval/
    │   └── 10_improvement_proposal/
    └── tests/
```

`live-tests/examples/` 继续作为在线真实 API 示例的权威入口；`academy/` 是课程产品，
每个实验围绕一个可讲解问题组织，不复制出第二套无维护约束的通用 examples。

## 6. 十个连续实验

所有实验围绕同一条主线：构建一个能理解小型仓库、调用工具、遵守边界、执行验证、
记录证据并接受复核的 Senza Developer Agent。

每个实验统一包含：

- `README.md`：理论、架构映射、运行说明、观察点和能力边界；
- `demo.py`：live 模式与无需密钥的 recorded 模式；
- `fixtures/`：最小、确定性的任务环境；
- `expected_trace.json`：课堂演示的稳定事件轨迹；
- `test_demo.py`：离线断言，防止文档与实现再次漂移。

| # | 实验 | 书中理论 | Runtime/Senza 组件 | v1 验收 |
| --- | --- | --- | --- | --- |
| 01 | ReAct 与 Tool Calling | Agent = LLM + Context + Tools | Builder、Tool、Agent Core、events、usage | recorded 时间线可离线重放；live 可见完整模型/工具循环 |
| 02 | Hook X 光片 | Harness 对上下文、约束、验证和纠正负责 | 12 Hook、组合/短路语义 | 两条轨迹覆盖主要 Hook 类别；文档明确固定挂载点 |
| 03 | DB Safety Plugin | 程序/Harness 是经验的更新载体 | `create_plugin`、tool、before/after tool hook、step plugin | 演示 allow/modify/deny；Agent 与 step 两种安装范围 |
| 04 | Context Layers | 稳定前缀、渐进披露、状态栏、压缩 | Skills、StatusPanel、manual/auto compaction | 输出分层 context diff；手动压缩 API 与当前实现一致 |
| 05 | Coding + Guardrails | Coding 闭环、动作空间、边界治理 | FS tools、rules、safety、loop safety | fixture 中修复 1 个失败测试；危险动作被确定性拒绝 |
| 06 | Workflow + Recovery + HITL | 自主 Agent 与确定性 Workflow、恢复点 | Workflow、Executor/Judge、TaskStore、restore、HITL | draft→check→approve→publish；从指定 step 恢复 |
| 07 | Knowledge / Memory / Recall | RAG、长期记忆、共享知识的边界 | local BM25、Memory/Recall contracts | RAG 真运行；Memory/Recall 标注“契约预览”，不伪造 E2E |
| 08 | Basic Multi-Agent | 上下文隔离、Manager 拓扑 | spawn/message/await/query/abort | 仅纯推理子任务；清楚展示 5 个主侧工具及子 Agent 限制 |
| 09 | Reliability Eval | Model+Harness 共同评估、Pass@k/Pass^k | audit、usage、budget + 教学 runner | JSONL cases、重复运行、确定性 verifier、成本/延迟、variant 报告 |
| 10 | Improvement Proposal | 在线执行与离线进化分离 | trace、Plugin/Skill proposal、approval gate | bad case→候选 diff→边界/保留集；只输出提案，不自动发布 |

## 7. 分阶段实施顺序

### Phase 0：计划与事实校准

- [x] 固定三个仓库的 commit 与课程范围；
- [x] 建立当前能力/边界矩阵；
- [x] 修正 Runtime 中 11/12 Hook 和 Tool 冲突语义的文档漂移；
- [x] 修正 Senza 中 Hook、Plugin 数量、spawn tool 数量的文档漂移；
- [x] 修正 compaction、memory gate、before-tool deny 等示例漂移；
- [x] 针对改动运行文档搜索、Python 语法检查和相关测试。

### Phase 1：课程骨架与首批稳定实验

- [x] 建立 Academy 公共 runner、trace schema 与离线测试约定；
- [x] 完成实验 01–03：Core、Hook、Plugin；
- [x] 完成实验 04–06：Context、Coding Guardrails、Workflow；
- [x] recorded 模式在无 Provider、无 API key 条件下全部通过；
- [x] live 模式遵循现有 `live-tests` 的无 key 跳过语义，不掩盖真实失败。

### Phase 2：进阶课程与教学评测层

- [x] 完成实验 07 的 RAG 真运行与 Memory/Recall 契约预览；
- [x] 完成实验 08 的受限 basic spawn；
- [x] 完成实验 09 的最小教学 eval runner；
- [x] 完成实验 10 的 proposal-only 改进流程；
- [x] 所有成熟度标识能被测试读取并校验。

### Phase 3：仓库级验证

- [x] Python 文件通过编译检查；
- [x] Academy 离线测试全绿；
- [x] Senza 相关单元/集成测试全绿；
- [x] Runtime 相关 `cargo fmt`、clippy 与测试通过，或记录可复现的环境阻塞；
- [x] 对 README、API 文档、源码注释执行关键事实一致性搜索；
- [x] 检查两个仓库 diff，确保没有覆盖用户的无关修改。

### Phase 4：独立学习版 PPT

- [x] 新建 [`Senza Academy：从 Agent 理论到 Runtime/Senza 实践`](assets/senza-academy-learning-deck.pptx) 学习版 deck；
- [x] 保留原领导版 `LLM-Harness-Runtime-架构与设计原则.pptx` 不变；
- [x] PPT 采用“理论问题 → Runtime 设计 → Senza 代码 → 实验证据 → 能力边界”叙事；
- [x] 每页 speaker notes 含 `[Sources]` 来源块；
- [x] 渲染并逐页检查文字溢出、遮挡、对齐和图示可读性；
- [x] 运行 deck overflow/结构检查并交付 `.pptx` 与预览图。

### Phase 5：教材正文

- [x] 建立教材体例、序言、术语表和源码地图；
- [x] 完成与十个 Lab 对应的十章中文正文；
- [x] 每章包含理论解释、架构映射、执行故事、源码导读、实验、能力边界和复习题；
- [x] 建立教材内容契约与本地链接自动检查；
- [x] 完成独立事实审查并修正发现的 P1/P2 教学问题；
- [x] 将教材入口接入 Senza README、Academy README 和文档索引。

## 8. PPT 建议叙事

1. 为什么“只调用一次模型”不是 Agent；
2. Agent = Model + Harness；
3. Runtime/Senza 四层架构与职责边界；
4. Agent Core：稳定的 Run–Turn–Tool 闭环；
5. 13 个 Hook：治理逻辑进入 Core 的固定位置；
6. Plugin：为什么能力可以组合、复用和做消融；
7. Senza：Python 如何装配 Agent 与 Workflow；
8. Context、Knowledge、Memory、Store 分别解决什么；
9. Coding Agent 与确定性 Guardrail；
10. Workflow、恢复、HITL 和事件边界；
11. 评测：一次跑通与连续可靠的差异；
12. 多 Agent 与持续改进的现状/演进路线；
13. 十个实验的学习地图与上手路径。

## 9. 验证命令

命令以实际仓库配置为准；若某项依赖在线 Provider，必须同时保留离线验收路径。

```powershell
# Senza：文档与 Python 课程
python -m compileall academy live-tests/examples
python -m pytest academy/tests academy/labs -q

# Senza：现有测试（按环境能力执行）
python -m pytest tests -q

# Runtime：格式、静态检查与测试
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-features
```

### 9.1 实际验证记录

- Academy 测试与 10 个 recorded demo 均可在无 Provider、无 API key 环境运行；具体用例数以
  当前分支的 CI collect/run 结果为准，避免随合同测试增长而漂移；
- Python：`compileall` 通过，并用 Python 3.9 语法树解析复核；Academy 的仓库内链接全部解析且
  保持在 Senza 根目录内，跨仓库引用固定到对应 commit 的 GitHub URL；
- Senza：`cargo fmt --check`、clippy、13 个 Rust 单元测试通过；使用 Python 3.13 环境
  执行 5 个 ignored Python 集成测试，全部通过；
- Runtime：`cargo fmt --check` 与 workspace/all-targets/all-features clippy 通过；本次改动相关
  Agent、Knowledge、Spawn、Tools 测试均通过；跳过两组平台专属用例后，全
  workspace/all-features 测试通过（20 filtered）；
- PPT：独立学习版共 16 页，16 页均含 `[Sources]`；608 个结构元素无越界，逐页渲染检查
  通过，导出后回读渲染与源渲染保持像素级一致；
- 环境说明：Windows 上 bundled `slides_test.py` 在生成全部检查图后，其底层 Node 进程以
  `-1073740791` 退出；因此使用直接导出、导入回读、结构边界扫描和逐页视觉检查完成等价验收。
  Runtime 不带过滤器的全量测试另有 18 个既有平台失败：Shell Monitor 测试固定调用当前
  Windows 环境中不存在的 `sh -c`，Path Safety 测试硬编码 POSIX `/workspace` 绝对路径；
  两组之外的完整测试均已通过。

## 10. 发布门槛与非目标

Academy v1 的发布门槛是：课程事实与固定源码一致、前六课无密钥可稳定演示、十课均有
清晰成熟度说明、离线测试通过、学习版 PPT 完成逐页验收。

以下不作为 v1 “偷偷补齐”的范围，也不得在宣传中提前声称已经具备：

- 生产级持久 Memory backend 和写后长期召回闭环；
- Session Recall 的 Python projector/index population 完整链路；
- 可注入专业工具、角色 profile 与配额的子 Agent；
- Python 通用 tracing exporter adapter；
- 平台级 dataset/eval/LLM-as-Judge 产品；
- SFT、RL 或其他模型后训练系统；
- Runtime Plugin 的运行时热插拔、自卸载或自我修改。

这些能力进入后续产品路线时，应先补端到端测试，再升级课程成熟度标签与演示。

## 11. 完成定义

本计划只有在以下产物同时存在并通过验证时才算完成：

1. 修正后的 Runtime/Senza 权威文档与示例；
2. 10 个 Academy 实验及其离线测试；
3. 一个可复现的教学评测报告；
4. 一份独立学习版 PPT，并完成逐页视觉检查；
5. 一份最终验证记录，列明通过项、环境限制和后续产品门槛。

教材正文的单独完成定义与验证记录见
[`2026-08-19-senza-academy-textbook-plan.md`](2026-08-19-senza-academy-textbook-plan.md)。
