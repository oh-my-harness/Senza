# Live Tests 与 Academy Example 场景统一计划

> 日期：2026-08-21
> 状态：P1 Catalog / Runner / Academy manifest bridge 已实现；native scenario adapters、
> 统一 result envelope 与 strict verifier 尚未实现
> 范围：Senza 仓库中的 `academy/`、`live-tests/examples/` 与
> `live-tests/test_*_layer.py`

## 1. 决策摘要

我们不把 Academy Lab、live example 和 layer test 简单拼成一个目录，也不让三者继续各自维护
一套相似故事。目标是引入一个 **Single Scenario Catalog**：一个场景只描述一次意图、输入、
能力边界、运行要求和预期证据，再由不同 adapter 生成三种证据。

| 证据角色 | 回答的问题 | 当前载体 | 目标 adapter |
| --- | --- | --- | --- |
| 教学证据 | 原理是什么，事件为什么按这个顺序发生？ | Academy recorded Lab | `recorded` |
| 真实运行证据 | 当前 Python API、Provider 和真实回调能否走通？ | `live-tests/examples/*.py` | `senza-live` |
| 严格行为证据 | 哪条契约必须自动判定 pass/fail？ | 五个 `test_*_layer.py` | `pytest-strict` |

统一的是 **Scenario 的语义和结果契约**，不是三种证据的强度。recorded 轨迹不能替代真实
Provider，live example 的弱观察不能替代严格断言，严格测试也不承担完整教学叙事。

P1 已提供统一入口：

```bash
python -m examples list
python -m examples describe agent.tool_calling
python -m examples doctor agent.tool_calling
python -m examples run agent.tool_calling
python -m examples list --course academy
python -m examples course 01 --mode recorded
python -m examples course 01 --mode live
```

当前 `run` 先做 requirements preflight，再以子进程执行 Catalog 指向的 legacy script；
`course` 则从 Academy manifest 选择 recorded Lab 或 live scenario。`show`、`verify` 和通用的
`run --mode` 不是 P1 命令；native adapters/strict verifier 属于 P2+ 工作。现有
`python academy/labs/.../demo.py`、`python live-tests/examples/NN_*.py` 和
`python -m pytest live-tests/` 都继续有效。

## 2. 现状盘点

### 2.1 数量基线

截至本计划日期，静态源码盘点得到：

- `live-tests/examples/` 有 **40** 个编号脚本：`01`–`23` 共 23 个，`30`–`46`
  共 17 个；
- 五个 layer 文件有 **42** 个顶层 `test_*` 函数，按
  agent / loop / runtime / strategy / tools 分别为 **9 / 4 / 10 / 9 / 10**；
- 42 个测试按当前源码意图可分为约 **32** 个真实 Provider 测试、**5** 个离线 construction
  smoke，以及 **5** 个带显式 `pytest.mark.skip` 的外部/已知问题测试；
- Academy 有 **10** 个 Lab；
- 10 个 Lab 的 live 委托形成 **20** 条 Lab → example 边；
- 20 条边只涉及 **18** 个不同脚本，因为 `12_tracing_audit.py` 和
  `32_plugins.py` 各被两个 Lab 复用；
- 40 个脚本中仍有 **22** 个没有进入 Academy Lab 的 live 路径。
- P1 Catalog 已覆盖 **40/40** 脚本，Academy manifest 的 20 条引用通过稳定 scenario ID
  解析到上述 18 个脚本。

这里的 42 是对当前 Python 源码做的静态统计，不等同于某次有 Provider、特定平台和外部服务的
pytest collected/pass 数。后续应在已安装 Senza 的 CI 环境同时保存 AST 统计与
`pytest --collect-only` 机器报告。

### 2.2 三套资产当前如何连接

P1 之前，Academy 的 `demo.py --mode live` 通过
`academy.common.run_live_example` 直接执行一个 `live-tests/examples` 文件，映射分散在
10 个 `demo.py`、README 和 recorded trace 中。现在 `academy/course_manifest.json`
保存 scenario refs，`academy.common.catalog` 将它们解析到 `examples/catalog.json`，
再交给 `python -m examples run`。旧 filename 视图仍保留以兼容现有 Lab 测试。

P1 解决了“一个稳定 ID 指向哪个 legacy script”以及 requirements preflight，但 layer tests
仍按架构层独立组织，recorded/live/strict 也还没有共享 native adapter 和 result envelope。
后续仍要回答：

1. 一个课程概念有哪些 recorded、live、strict 证据？
2. 一个 live 脚本究竟证明了什么，哪些只是打印出来供人观察？
3. 代码或 API 改动后，应该更新哪几个 Lab、example 和 test？
4. 哪些脚本需要密钥、网络、shell、平台能力或外部服务？

## 3. 逐 Lab 映射与精炼建议

下表保留当前 20 条边，同时给出精炼建议。scenario ID 是 P1 Catalog 与 Academy manifest
当前使用的 canonical ID。

| Lab | 当前 live example | 当前课程意图 | Catalog scenario ID / 精炼方式 |
| --- | --- | --- | --- |
| 01 ReAct | `02_tool_calling.py` | 模型选择 Tool、回调执行、结果回到下一轮 | `agent.tool_calling`；作为首批 pilot，与 agent/loop strict 断言共用 |
| 02 Hook X-ray | `07_hooks.py` | 12 个固定 hook 点与单次运行观察 | `agent.hooks`；recorded 展示 12 点图谱，live/strict 只声明实际触发点 |
| 03 Plugin | `32_plugins.py` | Plugin 将 tool、hook、状态打包 | `plugin.composition`；DB safety 作为 recorded fixture，不冒充内建 DB plugin |
| 04 Context | `06_skills_model_switch.py` | Skill catalog、按需读取、模型切换 | `context.skills_model_switch`；把 model switch 标成相邻能力而非 Skill 必然行为 |
| 04 Context | `16_status_panel.py` | 动态状态注入 | `context.status_panel`；记录注入前后 context 证据 |
| 04 Context | `21_context_aware_compact.py` | 压缩触发与 context-aware prompt | `context.compaction_prompt`；区分 prompt helper、手动触发和自动触发 |
| 05 Guardrails | `22_fs_tools.py` | 文件工具闭环 | `tools.filesystem`；所有写操作使用 disposable workspace |
| 05 Guardrails | `14_rules_approval.py` | RuleChain allow/deny/rate-limit | `safety.rules_approval`；拆成确定性三子场景，消除共享计数 |
| 05 Guardrails | `15_safety_injection.py` | safety defaults 与 injection filter | `safety.defaults_injection`；分别断言 lexical safety 和输入过滤 |
| 06 Workflow | `08_workflow.py` | 基础 step/edge/judge | `workflow.basic`；作为其他 workflow 场景的最小基线 |
| 06 Workflow | `39_executor_steps.py` | LLM step 与 Executor step 混合 | `workflow.executor`；结果 envelope 标明每步 executor 类型 |
| 06 Workflow | `41_human_in_the_loop.py` | 外部事件等待与提交 | `workflow.hitl`；明确仅为进程内 event handle，不声称持久审批 |
| 06 Workflow | `45_hooks_retries.py` | retry、hook、restore | `workflow.retry_replay`；拆分 retry 与持久恢复断言，避免一个故事掩盖失败点 |
| 07 Knowledge | `36_rag_qa.py` | 本地知识检索 | `knowledge.rag`；以固定 fixture 验证命中来源 |
| 07 Knowledge | `23_infra_integration.py` | Knowledge、Memory、Recall 装配 | `knowledge.infrastructure_wiring`；当前只把 Knowledge 标为 E2E，Memory/Recall 为 construction |
| 08 Multi-Agent | `11_spawn_subagent.py` | 主 Agent 派发、查询、等待 | `multi_agent.spawn`；区分主侧 5 tools 与当前 child 无递归 spawn |
| 09 Reliability | `12_tracing_audit.py` | audit、生命周期观察 | `observability.audit`；Audit 为真实链，Tracing 保留为 hook analog |
| 09 Reliability | `13_budget_pricing.py` | token/cost/budget 原料 | `observability.budget_pricing`；Academy runner 才负责重复统计，不说成 Runtime eval 平台 |
| 10 Improvement | `32_plugins.py` | 候选 guard 的可装配边界 | 复用 `plugin.composition` 证据，不复制第二个 Plugin 场景 |
| 10 Improvement | `12_tracing_audit.py` | 可供离线分析的审计输入 | 复用 `observability.audit`；proposal/approval 仍属于 Academy 教学层 |

未进入 Academy live 路径的 22 个脚本是：

```
01, 03, 04, 05, 09, 10, 17, 18, 19, 20,
30, 31, 33, 34, 35, 37, 38, 40, 42, 43, 44, 46
```

“未覆盖”不等于“必须塞进十课”。P0/P4 应把它们分类为：课程必需场景、API recipe、回归场景、
外部集成场景或可合并/退役的重复场景。Catalog 必须收录其处置状态，Academy 只选择能支撑
学习目标的场景。

## 4. 已发现的漂移与证据失真

这些问题不表示脚本没有价值，而是说明 filename/docstring、执行路径和实际证据强度之间出现了
偏差。迁移时应先建 regression case，再修场景；不能只是改文案掩盖行为。

### 4.1 可直接导致结论错误的漂移

下列 5 个脚本正是 P1 的完整隔离集合：Catalog 中均为
`tier=quarantined / status=needs-fix`，runner 默认返回 `refused`/exit 2。只有修复并加入
对应 regression assertion 后才能解除；显式诊断运行不计作能力通过证据。

| 脚本 | 发现 | 迁移要求 |
| --- | --- | --- |
| `14_rules_approval.py` | 三个 part 共享模块级 `EXECUTED`；rate-limit 小节用累计 echo 次数判断 `<= 2`，会混入前两个 part 的调用 | 每个 case 独立 state；断言 attempted、allowed、callback executed 三个层次 |
| `20_notify.py` | `tools_called` 先转成 set 再排序，随后用 `count('notify_user')` 统计三次调用，结果最多只能是 1 | result envelope 保留有序 tool-call records；通知次数从记录而非去重集合计算 |
| `40_pause_cancel.py` | 依赖 `sleep(0.3)` 与 LLM 请求竞速；标题声称 pause 和 cancel，正文实际没有执行 cancel 路径 | pause/cancel 拆成两个确定性 case，用同步点而非墙钟竞速 |
| `42_shell_executor.py` | judge 对所有 step 返回终止决定，可能在第一步后结束，使第二个 compute step 和 edge 无法得到证明 | strict adapter 必须断言完整 step 顺序和两个 shell 结果；命令按平台声明 |
| `46_data_analysis.py` | 注册了 `transform` executor，但 workflow 没有引用该 executor；“LLM + executor 混合”与实际拓扑不一致 | catalog schema 校验“已注册但未使用”和“引用但未注册”；把 transform 设为真实 step 后再宣称混合 |

### 4.2 部分 analog 被误读为完整证明的风险

| 脚本 | 当前真实边界 | Catalog 中的正确声明 |
| --- | --- | --- |
| `10_sandbox.py` | `seatbelt_sandbox` 是已说明的 gap；纯 Python echo callback 没有执行 OS 操作，挂上 env 不足以证明隔离 | 只证明 env/sandbox construction；真实隔离另建有平台要求的场景 |
| `12_tracing_audit.py` | JSONL audit hash chain 是真实路径；Tracing 只是占用相同 hook slots 的近似 timeline，且模块级列表需隔离 run | 将 `audit` 与 `tracing` claim 分开，Tracing 标 `not_proven` |
| `18_loop_safety.py` | `settled and tool_calls <= 4` 在零次调用时也可通过，正常收敛不能证明 guard 曾触发 | strict case 需要可控重复工具源，并断言具体 guard decision |
| `19_memory_defense.py` | 结论主要依赖模型是否调用工具和最终文字；write callback 本身不写文件，也没有对 guard 后的原始结果做强断言 | recorded 展示原理，strict adapter 直接观察 callback 是否执行及 tool result 是否截断 |
| `23_infra_integration.py` | Knowledge search 是 live E2E；Memory 和 Session Recall 只有 construction/wiring，没有写入、索引和召回 | 分成 `knowledge.local-rag`、`memory.write`、`recall.inject` 三个 claims |
| `37_mcp_blender.py` | 不 build、不连接 Blender MCP，也没有 MCP tool call | 标成 T4 external recipe / construction，不是 live MCP E2E |
| `41_human_in_the_loop.py` | 用线程模拟同进程提交；依赖模型主动调用 wait tool，不证明跨进程、持久审批或崩溃恢复 | 只声明 in-process event wait/submit，并为 tool call 和 event payload 加 strict assertion |

此外，所有模块级可变容器、固定 sleep、模型自由决定“是否调用工具”、只打印 `EXPECTED` 而不产生
机器断言的模式，都要在 Catalog/计划的 drift register 中登记。live example 可以保留弱断言，但不能把
“没有抛异常”升级为具体能力已得到证明。

## 5. 目标架构

P1 当前已经落地 Catalog、CLI Runner、requirements doctor、legacy subprocess dispatch 和 Academy
manifest bridge。下图中的 recorded / senza-live / pytest-strict native adapters 与 normalized
Result Envelope 是 P2+ 目标，不是 P1 现状：

```
                         +-------------------------+
                         | Single Scenario Catalog |
                         | id / claims / modes /   |
                         | requirements / security |
                         +------------+------------+
                                      |
                               Scenario Runner
                                      |
          +---------------------------+---------------------------+
          |                           |                           |
  recorded adapter             senza-live adapter          pytest-strict adapter
  deterministic trace          real Provider/API           contract assertions
          |                           |                           |
     Academy lesson             runnable document             layer CI
          +---------------------------+---------------------------+
                                      |
                           normalized Result Envelope
```

目标逻辑边界：

- **Catalog**：P1 已统一维护 ID、aliases、legacy path、tier/maturity/status、requirements 和
  proves/does-not-prove；后续再加入 fixture、security、adapter 映射和 owner；
- **Runner**：P1 已解析 ID、检查显式 requirements 并启动 legacy subprocess；隔离 run directory、
  native adapter 与规范化结果仍待实现；
- **Adapters**：只负责接入 recorded fixture、Senza live API、pytest assertion 或 legacy script，
  不重新定义 scenario 含义；
- **Renderers**：面向终端、Markdown 教材和 CI 生成不同视图；
- **Legacy adapters**：让旧脚本/旧 Lab 命令转发到 runner，迁移期不破坏使用者。

当前 P1 与 P2+ 目标布局：

```
examples/
  __main__.py          # P1
  catalog.json         # P1，覆盖 40/40 legacy scripts
  catalog.schema.json  # P1
  catalog.py           # P1 loader / resolver / validation
  runner.py            # P1 list / describe / doctor / run / course
  adapters/            # P2+ native adapters
  scenarios/           # P2+ native scenario implementations
    agent.tool_calling/
      recorded.json
      live.py
      strict.py

academy/
  course_manifest.json # P1 scenario_refs
  common/catalog.py    # P1 Academy bridge
```

## 6. Scenario Schema

P1 schema 已表达 `id / aliases / legacy_path / title / tier / maturity / status /
requirements / proves / does_not_prove`。下面是 P2+ 的目标扩展形态；它不是当前
`catalog.schema.json` 可直接接受的 payload：

```yaml
schema_version: 1
id: agent.tool_calling
title: Basic tool calling
concepts: [react, tool, hook-lifecycle]
academy:
  lab: '01'
  chapter: docs/academy/textbook/01-react-tool-calling.md
claims:
  proves:
    - registered tool can be selected and its callback result returns to the loop
  does_not_prove:
    - arbitrary model always selects a tool
modes:
  recorded:
    adapter: recorded
  live:
    adapter: senza-live
  strict:
    adapter: pytest-strict
requirements:
  python: '>=3.9'
  provider: optional-by-mode
  env: [OPENAI_API_KEY]
  platforms: [windows, linux, macos]
  commands: []
  services: []
security:
  network: provider-only
  filesystem: none
  shell: none
  secrets: env-only
  workspace: disposable
budgets:
  timeout_ms: 60000
  max_turns: 4
  max_tool_calls: 2
assertions:
  - id: callback-executed
    modes: [recorded, live, strict]
stability: stable
owners: [senza]
legacy:
  scripts: [live-tests/examples/02_tool_calling.py]
```

Schema 设计原则：

1. `claims.proves` 与 `claims.does_not_prove` 必填，避免 analog 被当成原生能力；
2. requirements 是机器可检查的运行前提，不把缺 key、缺平台或缺服务混成测试失败；
3. security 声明副作用；P2+ native runner 应默认拒绝未声明的 network、shell 和持久写入；
4. assertions 使用稳定 ID，教材、live 输出和 CI 可以引用同一条契约；
5. 一个 scenario 可以有多个 adapter，但同一 mode 只能有一个权威实现；
6. legacy path 是兼容入口，不是第二份语义定义。

## 7. 统一 Result Envelope

P1 `run --json` 当前只包装 legacy subprocess 的 status、exit code、stdout/stderr；这不是完整的
证据 envelope。P2+ 中每种 native adapter 应返回下列统一 envelope，原始 Provider event 或
pytest detail 可作为 artifact 保留：

```json
{
  "schema_version": 1,
  "scenario_id": "agent.tool_calling",
  "run_id": "generated-id",
  "mode": "live",
  "adapter": "senza-live",
  "status": "pass",
  "started_at": "RFC3339 timestamp",
  "duration_ms": 1234,
  "requirements": {
    "checked": true,
    "missing": []
  },
  "observations": {
    "turns": 2,
    "tool_calls": [
      {"name": "echo", "args": {"text": "ping"}, "outcome": "executed"}
    ]
  },
  "assertions": [
    {"id": "callback-executed", "status": "pass", "evidence": ["event:7"]}
  ],
  "claims": {
    "proven": ["registered tool callback executed"],
    "not_proven": ["model-independent tool selection"]
  },
  "artifacts": [],
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "estimated_cost": null
  },
  "skip_reason": null,
  "error": null
}
```

目标 envelope 的 `status` 只允许 `pass / fail / skip / error`。P1 compatibility runner
仍使用 `passed / failed / skipped / refused / timeout`，迁移时需由 adapter 规范化：

- `fail`：requirements 已满足，但契约断言失败；
- `skip`：声明过的 requirement 不满足，并给出稳定 reason code；
- `error`：runner、adapter 或未分类基础设施错误；
- `pass`：只表示本 mode 的 assertions 通过，不自动扩大到其他 mode 的 claims。

## 8. Requirements 与安全模型

### 8.1 Requirements

P2+ 完整 Requirements 目标中，每个场景必须声明：

- Python/Senza 版本与构建方式；
- Provider 类型、模型、环境变量和是否允许无 key recorded 运行；
- OS、架构以及 `bash / python3 / uvx` 等外部命令；
- 网络目的类型，不在 Catalog 中保存 endpoint token；
- MCP、Blender、HTTP 服务等外部依赖；
- timeout、token、turn、tool-call 和成本预算；
- 需要的 fixture、临时目录与清理策略。

P1 Runner 已检查显式 Provider env、必需 env、Senza Python module、commands 和 platform，分别报告
`missing-provider / missing-env / missing-python-module / missing-command / unsupported-platform`；
service 目前只声明、不主动探测。P2+ 应把这些 code 规范化进 envelope，并为 Blender 等外部服务
增加可控 preflight，不能让缺 key 与真实断言失败都表现为模糊 RuntimeError。

### 8.2 Security 目标

- P1 doctor 只检查本进程显式环境变量，不读取或回显 secret，也不加载 `~/.omp_llm_env`；
- P1 runner 使用仓库根为工作目录启动 legacy subprocess，它不是 sandbox；
- P2+ recorded 应是默认 native mode；live network、shell、真实文件写入需显式选择；
- 文件写场景默认使用 runner 创建的 disposable workspace，不允许把仓库根或用户目录当 scratch；
- shell 场景必须声明 command allowlist、参数策略和支持平台；
- secret 只从环境/凭据提供者读取，result、trace、snapshot 与错误信息统一脱敏；
- 外部 HTTP/MCP 场景声明允许的 host/service，不以 prompt 动态扩大权限；
- destructive、不可逆或真实业务写操作不进入默认 Academy 路径；
- adapter 结束后执行资源回收，并把 cleanup failure 写入 envelope；
- Catalog review 必须同时审查 `claims` 与 `security`，不能只审代码能否运行。

## 9. CI 分层：T0–T4

P1 已新增 `.github/workflows/examples-offline.yml`，在 Python 3.9/3.13 上执行 Catalog 查询、
统一 recorded 入口和全部 Academy/scenario contracts，因此 **T0/T1 的 P1 子集**已进入 PR 检查。
完整 schema/security 字段检查、native adapters 与 T2–T4 仍是后续目标：

| Tier | 运行内容 | 依赖 | 触发方式 | 失败含义 |
| --- | --- | --- | --- | --- |
| T0 Catalog | schema、唯一 ID、链接、legacy target、未使用 adapter、claims/security 完整性 | Python 标准库 | 每个 PR | 元数据或引用错误 |
| T1 Recorded | 10 个 Lab 的确定性 fixture、trace 与 renderer | 无 Provider | 每个 PR | 教学契约或 fixture 回归 |
| T2 Offline integration | Senza import/construction、adapter contract、无网络 strict tests | 当前 wheel | 每个 PR | Python API/装配回归 |
| T3 Provider live | 选定 stable 场景、预算和超时受控的真实 Provider strict run | key + network | nightly、release、手动 PR label | 当前模型/API 端到端回归 |
| T4 External/system | MCP、Blender、shell/HTTP、平台 sandbox、长流程恢复 | 隔离 runner + 外部服务 | 受保护环境、人工触发 | 特定系统集成回归 |

T3/T4 的 skip 率、flaky retry 和成本都必须进入报告；不能用自动 retry 把首轮失败从结果中删除。
显式 skip 的 5 个现有 tools-layer tests 应逐个拥有 requirement/issue，而不是永久作为无主注释。

## 10. 迁移阶段：P0–P5

### P0：冻结事实与漂移登记（已完成基线）

- 已用静态盘点记录 40 scripts / 42 tests / 10 Labs / 20 edges / 18 unique /
  22 Academy-uncovered；
- 已为 40 个脚本分配 canonical scenario ID，并用 tier、maturity、status 与 claims 分类；
- 已在本计划和 Catalog 状态中登记首批 drift；后续仍需补 owner 与可查询 issue ID；
- 未移动 legacy 文件，旧命令保持。

### P1：Catalog、Runner 与 Academy bridge（已实现）

- `examples/catalog.json` 与 schema 覆盖 40/40 legacy scripts；
- `python -m examples list / describe / doctor / run / course` 已实现；
- loader 检查 ID/alias 唯一、路径不逃逸、target 存在与 40/40 覆盖；
- runner 检查显式 requirements，并以子进程运行 legacy implementation；`course` 可统一选择
  Academy recorded/live 入口；
- Academy manifest 的 20 条引用使用 canonical IDs，bridge 保留旧 filename/API 兼容；
- PR offline workflow 已覆盖 Python 3.9/3.13 的 T0/T1 P1 子集；完整目标检查仍按第 9 节推进；
- native recorded/senza-live/pytest-strict adapters、统一 result envelope 与 strict verifier
  **不属于已完成 P1**。

### P2：Tool Calling / Hooks native pilot（下一步）

- 迁移 `agent.tool_calling` 与 `agent.hooks` 两个 scenario；
- 旧 Lab 和旧脚本只做薄转发，输出统一 envelope；
- layer test 通过 stable assertion ID 调用 strict adapter；
- 对比新旧命令的退出码、关键 stdout、skip 语义和 artifacts；
- pilot 未通过兼容门槛时不批量迁移。

### P3：迁移现有 20 条 Academy 映射

- 按第 3 节逐 Lab 迁移，复用 18 个 unique scenarios；
- `12`、`32` 保持一份 scenario、多处课程引用；
- 修复或降级第 4 节中的过度声明；
- Academy `demo.py` 保留为课程友好的兼容 wrapper。

### P4：吸收剩余 live/test 资产

- 对已纳入 Catalog、但 Academy 未覆盖的 22 个脚本完成 native/recipe/quarantine 处置；
- 把五个 layer 文件中的严格断言绑定到 scenario assertion ID；
- T3/T4 单独调度，平台和外部服务要求机器可见；
- 删除重复实现前先证明新旧执行结果等价。

### P5：入口收敛与兼容退场

- 文档把 `python -m examples` 从 P1 catalog/legacy 入口升级为完整 native scenario 入口；
- 旧路径至少跨两个发布周期保留，发出定向 deprecation 提示；
- 根据仓库内引用、CI 和发布说明确认无人依赖后，再单独提案删除 wrapper；
- Catalog 与 CI 报告成为数量、覆盖和成熟度的权威来源。

## 11. 首批 Pilot 细化

### 11.1 `agent.tool_calling`

输入资产：

- Academy Lab 01 recorded trace；
- `live-tests/examples/02_tool_calling.py`；
- `test_agent_layer.py::test_tool_calling`；
- `test_loop_layer.py::test_tool_dispatch` 中可拆出的多工具调度证据。

共同 assertions：

1. tool schema 被注册；
2. 至少一次目标 tool call 有可解析 args；
3. callback 确实执行；
4. tool result 返回 Agent loop；
5. 运行 settle，且未超过预算。

recorded mode 用固定事件解释 ReAct；live mode 允许模型输出变化但必须保留 callback 证据；strict
mode 只断言稳定契约。这样三者共享故事，不共享错误的确定性假设。

### 11.2 `agent.hooks`

输入资产：

- Academy Lab 02 的 12-hook atlas；
- `live-tests/examples/07_hooks.py`；
- `test_agent_layer.py::test_hooks_fire`。

共同 assertions 按 hook ID 表达。recorded 可展示 12 个固定点；pilot live 只对实际注册并触发的
hook 标 pass，其他点标 `not_observed`，不能用一轮请求声称覆盖全部 12 点。strict mode 至少验证
before/after tool 对称性、decision 对工具执行的影响，以及 hook 异常如何进入 envelope。

## 12. 兼容策略

1. **入口已加，native 后迁**：P1 `python -m examples` 已实现 Catalog 查询、doctor 与 legacy
   run；不得把它描述成 native adapters 或 strict verifier 已完成。
2. **旧命令可继续运行**：旧脚本、Lab demo 和 pytest node ID 在迁移期保持；wrapper 透传退出码。
3. **无 key 可解释**：旧 direct script 的行为不变；P1 runner 只认可本进程显式 provider env，
   不加载 `~/.omp_llm_env`。非隔离 provider 场景缺 key 时输出结构化 `skipped` 并 exit 0；
   quarantined 场景先拒绝并 exit 2，除非显式使用诊断开关。
4. **编号可作 alias**：`02` / `02_tool_calling` 可解析到 `agent.tool_calling`，但稳定 ID
   不依赖目录序号。
5. **输出渐进兼容**：人类可读 stdout 保留；P1 各命令通过显式 `--json` 获取机器输出，P2+
   再引入统一 evidence envelope。
6. **不复制业务逻辑**：native migration 完成后，旧路径只能调用 runner/adapter，不能长期
   保留第二份 harness 构造。
7. **不提前宣告 native migration 完成**：只有三类 native adapter、CI 和 legacy parity 同时
   通过，README 才能把 P1 legacy dispatch 描述成完整 scenario execution。

迁移完成后，`live-tests/examples/` 的定位是 **legacy adapter 与 source pool**，不是所有示例的
“唯一归宿”；`live-tests/` 仍保留严格行为验证职责，最终可由 scenario-aware pytest adapter
驱动，但不会降级为只打印结果的 demo。

## 13. 完成定义

P1 已完成 40/40 Catalog、统一 CLI、requirements doctor、legacy subprocess runner 和 Academy
manifest bridge。全量合并仍需全部满足以下条件，而不是“新 CLI 能跑”：

- 40 个现有脚本在 P1 已有 scenario ID、处置状态、requirements 和 claims；P2+ 补齐 owner、
  security 与 native adapter；
- 10 个 Lab 的 20 条映射全部引用 Catalog，仍对应 18 个 unique scenarios，没有复制实现；
- 22 个 uncovered 脚本全部完成分类；
- 42 个当前顶层 tests 都被保留、替代或有明确退役决策，collect-only 数量变化可解释；
- 三种 adapter 都返回通过 schema 校验的 result envelope；
- Tool Calling/Hooks pilot 的旧、新入口通过 parity 检查；
- 第 4 节问题均已修复，或以准确 `does_not_prove`/requirement 降级；
- T0/T1/T2 为 PR 必跑，T3/T4 有受控触发、预算、skip 与 artifact 报告；
- 缺 key、缺命令、缺平台和真实断言失败能被明确区分；
- 默认流程不产生未声明的网络、shell、持久文件或外部系统副作用；
- 教材、根 README、live-tests README 和 CLI help 从同一 Catalog 生成或校验；
- 旧路径至少在兼容窗口内继续工作，删除需另行评审；
- 文档不把 recorded、construction、nearest analog 或未来 native migration 写成已实现能力。

## 14. 当前下一步

P1 已经落地。下一步进入 P2：只选择 `agent.tool_calling` 与 `agent.hooks`，实现
recorded / senza-live / pytest-strict native adapters 和统一 result envelope，并对旧 Lab、legacy
script、现有 pytest node 做 parity 验证。pilot 通过前不批量迁移其他 18 条 Academy 引用。
