# 第 10 章：从 Bad Case 到待审批改进提案

> 本章成熟度：`teaching`。诊断、提案生成、boundary/retention replay 与审批状态机位于 Senza
> Academy；Runtime/Senza 提供 Hook、Plugin、Audit 等积木，但当前没有自动进化、自动发布或
> SFT/RL 产品闭环。最终决策必须由独立人工审批。

## 本章回答的问题

评测发现同一种失败反复发生后，系统不应只写一段“下次注意”，更不应让 Agent 直接修改正式
安全规则。本章展示一条受控离线路径：保留 bad case 证据，定位首个错误步骤，选择合适的改进
载体，把实际回放的结构化规则与提案绑定，限制候选声明的目标范围，最后停在人工审批。真正的审批
门、审计和发布信任根仍由外部系统保护。

本章回答：

1. 如何从多条轨迹中形成可复核的根因，而不是一次自我反思；
2. 什么时候把改进写成 Skill，什么时候应提出 Plugin/程序硬边界；
3. 为什么修复 boundary set 还不够，必须验证 retention set；
4. 哪些目标不能由提案生成器自我修改，以及为什么通过测试仍不能自动发布。

## 学习目标与先修知识

学完本章，你应当能够：

- 把 bad case 连接到原始轨迹、期望动作和首个错误步骤；
- 根据知识、指令、程序和参数的职责选择改进载体；
- 设计 boundary、retention 与 candidate preflight 三类离线门，并说明它们可证明的范围；
- 解释 `awaiting_human_approval` 与 installed/published 的区别；
- 准确说明 Academy proposal helper、Runtime Plugin/Hook 与外部训练系统的边界。

建议先完成第 3、5、9 章。理论背景见本地
[《动手学 AI Agent》第 9 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter9.md)；参数更新的外部路径可参看
[第 8 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter8.md)。

## 理论直觉：持续改进是双循环，不是在线自改

一次运行中的 Context 适应不会自动变成长期能力。反过来，把每次反馈立刻写进 Prompt、Skill、
代码或模型参数，会把噪声、误判和提示注入放大到后续任务。更稳妥的工程形态是在线与离线双循环：

```text
在线执行循环
任务 → 工具/环境 → 结果验证 → 保存证据
                              │
                              ▼
离线改进循环
聚类 bad cases → 定位根因 → 生成候选 → 回放与回归 → 人工审批 → 独立发布
```

在线循环只完成任务和记录证据，不修改正式能力；离线循环可以探索改进，但先产出候选版本。两条
循环通过版本化轨迹、评测集和审计记录连接。这样失败可以触发学习，却不能绕过软件发布与安全治理。

### 先选对更新载体

不同错误适合不同载体：

| 失败原因 | 候选载体 | 适合表达什么 |
| --- | --- | --- |
| 缺少或过期事实 | Knowledge/Memory | 可追溯、可更新的信息 |
| 可语言化操作流程 | Prompt/Skill | 柔性指导、步骤和风格 |
| 不可绕过的安全规则 | Plugin/Hook/程序 | 确定性 allow/modify/deny |
| 需要改变通用模型行为 | SFT/RL/蒸馏 | 外部训练系统中的参数更新 |

Skill 能提醒操作者“删除前先 SELECT 预览”，却不能保证模型一定遵守；“无 WHERE 的 DELETE 不得
进入 executor”属于硬边界，更适合 `before_tool_call` 中的确定性 Plugin 候选。参数训练也不适合
承载精确业务禁令，因为概率行为不能替代运行时强制门。

### 改善失败集，还要保持已有能力

`boundary set` 包含触发目标失败的案例，要求候选修复；`retention set` 包含原先正常的邻近行为，
要求候选不造成回退。只让所有 DELETE 都失败，虽然修复了“无 WHERE 删除”，却可能破坏合法的
带 WHERE 维护任务。持续改进的最低标准因此是“修边界 + 保能力”，而不是只对 bad case 过拟合。

## Runtime/Senza 架构映射

当前项目中的职责分布如下：

| 层次 | 组件 | 当前角色 |
| --- | --- | --- |
| Runtime/Senza | Agent Core、12 Hooks、Plugin、Audit、usage/budget | 执行能力、治理边界与证据来源 |
| Academy Lab 09 | cases、重复运行、verifier | 发现并描述 bad cases |
| Academy Lab 10 | diagnosis、structured proposal、offline gates | 绑定内存候选并回放其规则 |
| 人与发布系统 | code review、审批、CI、灰度、回滚 | 决定是否进入正式能力 |
| 外部训练系统 | dataset curation、SFT、RL、蒸馏 | 参数更新；不属于 Runtime/Senza |

```text
Audit / evaluated bad cases
            │
            ▼
  Academy proposal helper
   ├─ Plugin rule_config：硬边界候选
   ├─ Skill content：操作指导候选
   ├─ 规范化 diff preview
   └─ candidate_digest：绑定来源、artifact 与 diff
            │
            ▼
 schema/digest/target preflight
            │
            ▼
 proposal.rule_config → boundary + retention replay
            │
            ▼
 awaiting_human_approval
            ╳  本课不 install、不 publish、不训练
```

Runtime 的 Plugin 协议让候选将 tool 与 Hook 组合成构建期能力包；`before_tool_call` 是执行器之前的
稳定治理点。但 Runtime 没有读取 bad case 后自动诊断、修改源码、安装 Plugin 或发布新版本的
通用控制器。Academy helper 只展示如何绑定并回放一个内存候选；它不是文件、进程或训练作业的
通用副作用监控器。

## 一条完整执行故事

课程有 3 条合成的历史 bad case：`DELETE FROM sessions`、`DELETE FROM api_tokens` 和
`DELETE FROM audit_events` 都缺少 `WHERE`，观测动作却是 `allow`，首个错误一致记录为
“`before_tool_call` 放过了无作用域 DELETE”。这些 fixture 用来教方法，不是在声明当前
`32_plugins.py` 仍有漏洞；真实示例当前会拒绝所有非 SELECT SQL。

离线 pipeline 依次执行：

1. **读取证据**：保留每条 `case_id`、tool name、args、观测动作、期望动作与首错位置。
2. **聚类与归因**：只有所有案例都匹配相同模式时，接受根因
   `delete_without_where_admitted_by_before_tool_call`；否则拒绝把异质失败强行合并。
3. **生成 Plugin 候选**：把 `run_query` 的 `deny/modify/allow` 行为写入 proposal 内的结构化
   `rule_config`；无 WHERE 的 DELETE deny，无界 SELECT 改写为 `LIMIT 100`。
4. **生成 Skill 候选**：把 SELECT 预览、显式 WHERE 和“指导不能替代硬边界”写入结构化内容。
5. **绑定候选**：由 artifact 确定性渲染 diff preview，再用 SHA-256 `candidate_digest` 绑定 proposal
   ID、来源 case、根因、两个 artifact 与 diff。单独篡改 artifact 或 diff 会使 preflight 失败。
6. **限制声明目标**：两个 artifact target 必须精确匹配 review-only allowlist；实际 fixture 路径与
   教学 `trust_roots/*` catalog 显式列为 protected。即使重算 digest，越界 target 仍被拒绝。
7. **回放同一候选**：preflight 通过后，runner 从 proposal 中取出这份 `rule_config`。boundary set
   的 3 条无 WHERE DELETE 都必须 deny；retention set 的 allow/modify 行为不得回退。
8. **停在审批门**：三类教学门全部通过后，状态是 `awaiting_human_approval`。proposal 和 diff
   只在内存中；helper 没有 apply/install/train 操作。

接下来应由独立 reviewer 对照原始证据、风险模型和真实 parser/数据库控制审查提案。这里的摘要与
target gate 只约束传入的内存 bundle，不能证明任意目录外写入、外部安装、网络动作或训练任务没有
发生。即便批准，实际实现、沙箱/权限、CI、发布和回滚也属于本课之外的受控软件交付流程。

## 源码导读

1. [Academy proposal pipeline](../../../academy/labs/10_improvement_proposal/proposal.py)：
   - `diagnose_bad_cases` 要求同质证据并定位首错；
   - `build_proposal` 生成结构化 Plugin/Skill、规范化 diff 与稳定 digest；
   - `candidate_guard` 解释 proposal 内的 `rule_config`，replay 不再调用提案外的固定规则；
   - `proposal_boundary_checks` 检查 schema、摘要、artifact/diff 一致性、精确 allowlist 和显式
     protected paths；
   - `validate_proposal` 只有在 preflight 通过后才运行 boundary/retention；
   - `run_proposal_pipeline` 只返回内存报告，最终状态停在审批。
2. [Lab 10 tests](../../../academy/labs/10_improvement_proposal/test_demo.py)：负向测试分别篡改 artifact、
   diff 和 target；另一个测试修改规则、重新生成 diff/digest 后观察 retention 失败，证明 replay
   消费 proposal 内的规则。源码快照只覆盖 Lab 目录非缓存文件，不外推为全系统副作用证明。
3. [Senza Python Plugin binding](../../../src/core/pyplugin.rs)：Python `create_plugin()` 把 tools 与
   12 类 Hook 分发到对应 registry；它是候选未来可能使用的承载机制，不是自动改进器。
4. [真实 Plugin 示例](../../../live-tests/examples/32_plugins.py)：展示 `before_tool_call` 的 allow、
   modify、deny 以及 Harness/Workflow 装配。其 SQL 检查仍是演示级正则，生产应使用 parser 与数据库
   权限控制。
5. [真实 Audit 示例](../../../live-tests/examples/12_tracing_audit.py)：展示可供离线流程消费的审计
   证据；它不会自动触发诊断或提案。

阅读 `proposal.py` 时，注意它没有 `import senza`、包管理器、文件写或 apply API。这个“缺少”把
本课停在候选阶段；但源码检查不是 OS 沙箱，真实系统仍必须用权限与审计约束进程能力。

## 配套实验

实验说明见 [Lab 10 README](../../../academy/labs/10_improvement_proposal/README.md)。在 Senza 根目录运行：

```powershell
# 默认：生成内存 proposal，运行三类离线门，停在人工审批
python academy/labs/10_improvement_proposal/demo.py

# live 只观察真实 Plugin 边界和审计证据
python academy/labs/10_improvement_proposal/demo.py --mode live --live-example plugins
python academy/labs/10_improvement_proposal/demo.py --mode live --live-example audit

python -m pytest academy/labs/10_improvement_proposal/test_demo.py -q
```

运行后核对：根因及 3 个 evidence ID、两个结构化 candidate artifact、64 位十六进制摘要、boundary
与 retention 通过，以及 candidate preflight 通过。最后确认：

```text
final state: awaiting_human_approval
candidate digest bound: true
targets allowlisted: true
candidate applied: false
proof scope: in-memory bundle + declared targets; not arbitrary external side effects
```

可做三个扩展实验：

1. 在 retention fixture 中加入另一种合法 SQL，观察过宽正则是否造成回退；
2. 修改 `rule_config` 中的 LIMIT 但不更新 diff/digest，确认摘要门拒绝；随后规范化重绑定，确认 replay
   真正表现为新规则并由 retention 判错；
3. 把 target 改成 `fixtures/retention_cases.jsonl` 并重算摘要，确认 allowlist 与 protected-path 门仍拒绝。

扩展时仍只修改教学 fixture/helper，不要写安装代码。若要实施真实改进，应另开受审查变更，使用
真实 parser、数据库最小权限、完整回归与灰度计划。

## 常见误解与能力边界

### “测试都通过了，所以系统已经自我进化”

错误。测试通过只把候选推进到 `awaiting_human_approval`。没有安装、发布、线上流量、收益验证或
长期保持证据，就不能称为已完成持续进化。

### “这些 bad cases 证明当前 Plugin 有 SQL 漏洞”

错误。fixture 是合成历史案例，用于固定教学根因。当前 `32_plugins.py` 的 guard 会拒绝所有非
SELECT；课程没有对现有产品漏洞作声明。

### “Skill 可以替代硬安全 Hook”

错误。Skill 是模型可遵循的行为指导，可能被忽略或误解。不可绕过的执行禁令应放在 Harness/Plugin
的确定性边界，并配合数据库权限等纵深防御。

### “让提案生成器修改 approval gate，能提高迭代效率”

错误。审批门、评测集、verifier、审计日志、发布阈值和稳定备份是信任根。允许候选修改自己的
评分与批准规则，会让“通过验证”失去意义。安全机制不能自我修改。

### “digest 与 target gate 通过，就证明没有任何副作用”

错误。digest 证明本次 replay 消费的内存字段与被摘要字段一致；allowlist 只约束 proposal 声明的
target。它们不监视目录外文件、进程、网络、包管理器或训练平台。真实信任根还要靠独立进程权限、
不可变存储、审计和发布系统保护。

### “Runtime 已有 Hook 和 Audit，所以自动进化闭环已经内建”

错误。它们是执行与证据积木。诊断、候选搜索、离线门、人工审批、发布和回滚的通用系统当前不在
Runtime；本课实现位于 Academy 教学层。

### “本课没有 train 操作，所以训练能力已经安全接入”

错误。helper 没有 train 操作，只说明这条教学路径不启动训练。SFT、RL、蒸馏、奖励建模和训练任务
编排属于外部后训练系统；Runtime/Senza 当前没有这些能力。

完整口径见 [Academy 能力边界](../capability-boundaries.md)。

## 小结

安全的持续改进从可追溯 bad case 开始，把评价、归因、载体选择、候选绑定、boundary replay 与
retention regression 组织成离线提案流程。Plugin 适合确定性硬边界，Skill 适合操作指导；参数训练
属于外部系统。Academy 能验证一个内存 bundle 的摘要、声明 target 与回放结果，不能替代外部信任
根和副作用隔离。三类教学门通过后的正确终点是独立人工审批，而不是自动安装和自我发布。

## 复习题

1. 为什么单条失败后的“自我反思”不足以成为长期能力更新？
2. 对“删除必须有 WHERE”这一要求，Skill 与 Plugin 分别承担什么角色？
3. boundary set 与 retention set 各自防止哪一种错误？
4. 为什么 verifier、审批门和发布阈值必须独立于候选生成器？
5. `awaiting_human_approval` 明确排除了哪些已完成状态？
6. 哪些 Runtime/Senza 组件可以为改进系统提供积木，哪些关键环节目前仍属于 Academy 或外部系统？
7. 若未来接入 SFT/RL，怎样防止未经验证的生产轨迹和提示注入直接进入训练集？
8. 提案获批后，一个真实软件发布流程还应包含哪些检查与回滚机制？

## 延伸阅读

- [《动手学 AI Agent》第 9 章：Agent 的持续进化](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter9.md)
- [《动手学 AI Agent》第 8 章：后训练](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter8.md)
- [Lab 10：从 Bad Case 到待审批改进提案](../../../academy/labs/10_improvement_proposal/README.md)
- [Lab 09：可靠性评测](../../../academy/labs/09_reliability_eval/README.md)
- [真实 Plugin 示例](../../../live-tests/examples/32_plugins.py)
- [Academy 能力边界](../capability-boundaries.md)
