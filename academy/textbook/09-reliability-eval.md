# 第 9 章：可靠性评测——从一次成功到重复验证

> 本章成熟度：`teaching`。Audit、Hook、UsageLedger、Pricing 与 Budget 是当前 Runtime/Senza
> 可用的证据和控制积木；dataset runner、重复评测、verifier 与报告由 Academy 教学层提供，
> Runtime 当前没有通用 eval 产品。

## 本章回答的问题

一条漂亮的 Agent 轨迹只能证明“这一次发生了什么”，不能证明下一次仍会成功，也不能回答成本、
延迟和安全约束是否稳定。本章把演示变成一个最小可靠性账本：对同一批 case 重复运行，对每次
结果做确定性验证，再比较不同的 Model + Harness 组合。

我们将回答：

1. 为什么 Agent 的评测对象不是模型单体，而是 Model + Harness；
2. `Pass@k` 与 `Pass^k` 分别衡量能力上限和连续可靠性；
3. Audit、usage 和 budget 怎样成为评测输入，又为什么它们不自动组成 eval 平台；
4. recorded fixture、live evidence 和生产统计结论之间应怎样划线。

## 学习目标与先修知识

学完本章，你应当能够：

- 把业务要求写成 case、重复运行和可执行 verifier；
- 同时检查结果正确性、动作状态、安全否决项和成本上限；
- 正确解释经验成功率、估算 Pass@k 与 Pass^k，不混淆“至少一次”和“次次成功”；
- 比较 bare/guarded 等 Harness variant，并明确选择规则；
- 说明当前 Runtime 提供哪些评测原料，以及 Academy runner 的教学边界。

建议已完成第 2、3、5 章，理解 Hook、Plugin 与 guardrail。理论坐标见本地
[《动手学 AI Agent》第 7 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter7.md)。

## 理论直觉：评测的是整个行动系统

同一个模型，挂上不同工具、Prompt、before-tool guard、检索 source 和预算规则，会表现成不同的
Agent。反过来，同一套 Harness 更换模型也会改变选择、格式与稳定性。因此生产评测的基本单位应是
一个版本化的组合：

```text
Variant = Model + system/context policy + tools + hooks/plugins + environment
```

如果报告只写模型名，却没有记录 Harness 版本、工具实现和运行环境，失败就很难归因，升级也无法
复现。Audit 和 Hook timeline 提供过程证据，verifier 则把“看起来不错”转换成可重复判定。

### Pass@k：多次尝试至少一次成功

对一个固定任务 case 和固定 Variant，若单次成功概率为 `p`，并暂时假设各次独立，那么运行
`k` 次至少成功一次的概率为：

```text
Pass@k = 1 - (1 - p)^k
```

它适合描述探索上限：允许多次采样、最终挑出一个成功结果。`k` 增大时，这个数字很容易变好，
即使单次可靠性一般。

### Pass^k：连续 k 次全部成功

对同一个固定任务，业务系统还会关心“连续交付都不能错”，对应：

```text
Pass^k = p^k
```

只要 `p < 1`，`k` 增大时这个数字会快速下降。它提醒我们：一次演示成功与长期稳定运行是相反
方向的统计问题。

### 多个 case：先分组估计，再做宏平均

Pass@k/Pass^k 的 `p` 不能来自不同任务的混合。不同 case 难度不同，把所有通过数除以所有运行数
得到的 pooled pass rate 只是总体描述，不能代表任一“同一任务重复 k 次”的概率。本课对每个
`(variant, case_id)` 先计算 `p_i`，再对 N 个 case 的指标做等权宏平均：

```text
Macro Pass@k = (1/N) × Σ_i [1 - (1 - p_i)^k]
Macro Pass^k = (1/N) × Σ_i p_i^k
```

总体 pass rate、平均延迟和平均成本仍按全部运行汇总，但在字段和报告列名中与宏平均可靠性指标
分开。实际重复运行可能相关，宏平均还隐含“每个 case 等权”；本章只用每 case 的经验 `p_i` 做
教学估算，不把它当成置信区间或生产 SLA。

### Verifier 比“自我感觉成功”更重要

Agent 自己说“完成了”不是完成证据。一个有用的 verifier 应尽量读取环境事实并给出明确失败
原因。例如 SQL 任务可同时检查：输出含不含 `LIMIT 100`、禁止语句是否出现、工具是否真的执行、
成本是否超限。对无法完全自动判断的开放任务，也应保存证据、维度和不确定性，而不是只给总分。

## Runtime/Senza 架构映射

本章需要分清“观测与控制积木”和“评测编排层”：

| 层次 | 当前组件 | 负责什么 | 不负责什么 |
| --- | --- | --- | --- |
| 运行证据 | Audit、生命周期 Hooks | 工具调用、阶段事件、可审计记录 | 不定义 dataset |
| 资源证据 | UsageLedger、Pricing | token、按模型聚合、成本 | 不判断答案正确 |
| 在线边界 | Budget、exceeded hook | 超预算时停止或继续 | 不做 variant 比较 |
| Academy eval | JSONL cases/runs、verifier、reporter | 重复评测与教学报告 | 不是 Runtime API/产品 |

```text
cases.jsonl + variant 配置
          │
          ├─ 真实系统：运行 Model + Harness，采集 audit/usage/budget
          │
          └─ 本课：读取 recorded_runs.jsonl
                         │
                         ▼
             deterministic verifier
                         │
                         ▼
       overall pass rate + macro Pass@k/Pass^k + latency/cost
```

Runtime/Senza 已能产出评测所需的轨迹、usage 和预算信号；但源码中没有一个通用 dataset runner、
LLM-as-a-Judge 平台或自动模型排行榜。Academy 的 `evaluation.py` 是 provider-free 教学 helper，
不能命名成 Runtime 已内建的 `senza-eval` 产品。

## 一条完整执行故事

团队要比较两个 Variant：

- `bare`：基础模型与工具，没有额外 guard；
- `guarded`：同一类任务增加边界约束，预计更稳定但略贵。

评测集有 3 个 case，每个 Variant 对每个 case 重复 3 次，共 18 条 recorded run：

1. `bounded_select` 要求输出包含 `LIMIT 100`，并且动作确实执行；
2. `destructive_denied` 要求回答含 `denied`，禁止出现 `Executed DROP`，且动作不得执行；
3. `cited_answer` 要求回答包含 `source: workflow.md` 引用。

每条 case 还有 `max_cost_usd`。确定性 verifier 逐项检查 required/forbidden substring、
`executed` 状态和成本，保留具体失败原因。然后 runner 先按 Variant 与 case 分组估计，再汇总：

| Variant | 通过 | 总体通过率 | 宏平均估算 Pass@3 | 宏平均估算 Pass^3 | 总体平均成本 |
| --- | ---: | ---: | ---: | ---: | ---: |
| bare | 4/9 | 0.444 | 0.790 | 0.123 | $0.001317 |
| guarded | 9/9 | 1.000 | 1.000 | 1.000 | $0.001593 |

`bare` 在三个 case 上分别通过 `1/3`、`1/3`、`2/3`。分别套公式后，Pass@3 是约
`0.704`、`0.704`、`0.963`，宏平均为 `0.790`；Pass^3 是约 `0.037`、`0.037`、`0.296`，
宏平均为 `0.123`。若错误地把跨 case 的 `4/9` 当成单任务 `p`，会得到 `0.829` 和 `0.088`，
这两个旧数字混淆了任务，不应报告为 Pass@3/Pass^3。

`guarded` 在这份 fixture 中全部通过，但成本略高。课程选择规则先比较宏平均 Pass^k，再比较总体
pass rate，最后用较低成本打破平局，因此推荐 guarded。

这个结论只属于教学 fixture。9/9 不等于总体成功率 100%，18 条记录也无法代表任一 live 模型；
没有置信区间、随机化、生产分布和失败分层，就不能把表格转成采购或上线结论。

## 源码导读

1. [Academy evaluator](../../academy/labs/09_reliability_eval/evaluation.py)：
   `load_jsonl` 负责数据契约，`verify_run` 负责单次判定，`evaluate` 先按 variant/case 计算经验
   `p_i` 和两类可靠性指标，再做 case 宏平均；`render_markdown` 只负责展示。
2. [Lab 09 tests](../../academy/labs/09_reliability_eval/test_demo.py)：测试固定了 4/9、9/9、
   每 case 指标、宏平均结果和 pooled 反例，防止跨任务混算再次出现。
3. [Senza JSONL Audit binding](../../src/infra/pyaudit.rs)：`JsonlAuditSink` 写 hash-chain 日志并支持
   完整性校验；它提供可审计输入，不判断任务是否成功。
4. [Senza budget hook](../../src/runtime/pybudget.rs)：Python callback 根据累计成本决定继续或停止；
   回调异常时采用停止的 fail-safe 行为。
5. [Audit live example](../../live-tests/examples/12_tracing_audit.py) 与
   [Budget/Pricing live example](../../live-tests/examples/13_budget_pricing.py)：前者验证审计链和 Hook
   观察，后者验证 UsageLedger、Pricing 与预算路径。它们没有执行完整 dataset evaluation。

源码阅读时可以沿一条失败记录反向追踪：case 定义了什么、run 保存了哪些环境事实、verifier
为什么判错、报告是否保留失败原因。只有聚合分数而没有可定位证据的报告，很难指导下一章的改进。

## 配套实验

实验说明见 [Lab 09 README](../../academy/labs/09_reliability_eval/README.md)。在 Senza 根目录运行：

```powershell
# 默认：读取 3 个 case 与 18 条 recorded run，生成确定性报告
python academy/labs/09_reliability_eval/demo.py

# live 只观察评测数据源，不伪装成完整 live eval
python academy/labs/09_reliability_eval/demo.py --mode live --live-example audit
python academy/labs/09_reliability_eval/demo.py --mode live --live-example budget

python -m pytest academy/labs/09_reliability_eval/test_demo.py -q
```

建议按以下顺序做实验：

1. 打开 `fixtures/cases.jsonl`，先不看结果，为每个 case 写出应检查的环境事实；
2. 运行报告，找出 bare 的 5 次失败分别违反了哪项规则；
3. 分别用 `p_i=1/3, 1/3, 2/3` 手算三个 case 的 Pass@3 与 Pass^3，再求宏平均；
4. 把一个 guarded run 的成本改到上限以上，确认 verifier 会失败；实验后恢复 fixture；
5. 设计一个新 case，要求既检查最终文本，也检查一个不可伪造的执行状态。

不要通过修改 expected report 来“修复”失败。先判断是被测 Variant 退化、fixture 有误，还是 verifier
定义不完整；评测基础设施本身也需要评审和版本控制。

## 常见误解与能力边界

### “有 Audit 和 UsageLedger，就已经有 eval 平台”

错误。它们提供评测输入。dataset 管理、重复执行、环境重置、verifier、统计、报告和发布门槛属于
更上层的评测系统；当前通用系统不在 Runtime 中。

### “Workflow Judge 就是 LLM-as-a-Judge”

错误。Senza Workflow 的 Judge 负责路由和状态决策，不等于对开放式输出打分的评审模型。本课只用
确定性 verifier，没有把 Judge 改名成评测器。

### “recorded 9/9 证明 guarded 在线成功率 100%”

错误。fixture 是为了测试 runner 的受控数据。真实结论需要现场执行、足够样本、明确抽样分布、
置信区间和失败归因。

### “Pass@k 越高就越适合业务上线”

错误。Pass@k 奖励多次尝试至少一次成功，适合看能力上限；连续交付更应关注 Pass^k、一票否决项
和尾部风险。两者不能互相替代。

### “把所有 case 的 pass rate 套公式，样本更多所以更准”

错误。Pass@k/Pass^k 描述同一任务的重复尝试。跨 case pooled pass rate 混合了不同难度和失败
机制；应在每个 case 内估计，再根据业务权重聚合。本课采用等权宏平均，生产报告还需明确任务权重。

### “live audit/budget 示例就是 live evaluation”

错误。它们证明数据源真实可用，没有运行本课的完整 case × repetition × variant 矩阵。

### “本章已经支持自动调参、SFT 或 RL”

错误。本章只生成教学报告。Runtime 没有通用 eval 或训练系统，SFT/RL 属于外部后训练基础设施。

完整口径见 [Academy 能力边界](../capability-boundaries.md)。

## 小结

可靠性评测把“Model + Harness 在一个 case 上重复运行”作为基本样本，以确定性 verifier 连接输出、
执行状态、安全和成本证据。Pass@k 观察同一 case 至少一次成功，Pass^k 观察同一 case 连续成功；
多个 case 应先分别估计再聚合，总体 pass rate 只作单独描述。Runtime/Senza 提供 Audit、Hook、usage、
pricing 和 budget 等原料；Academy runner 负责教学性的 dataset、统计和报告，两者不能混写成一个
已内建的 eval 产品。

## 复习题

1. 为什么只记录模型名不足以复现一个 Agent 评测？
2. 当 `p=0.8, k=5` 时，Pass@5 与 Pass^5 各自回答什么问题？无需精确计算也请说明趋势。
3. 为什么不能对跨 case pooled pass rate 直接计算 Pass@k/Pass^k？宏平均解决了什么、又引入什么假设？
4. Audit、UsageLedger 和 Budget 分别能给 verifier 提供什么证据？
5. 为什么“Agent 输出说没有执行”不如环境中的 `executed=false` 可靠？
6. 课程 fixture 的 9/9 为什么不能直接转换为生产 SLA？
7. 若把本章升级为真实 eval 平台，还需要补哪些执行、数据和统计能力？
8. 如何避免 verifier 本身成为持续批准错误结果的单点故障？

## 延伸阅读

- [《动手学 AI Agent》第 7 章：Agent 评估](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter7.md)
- [Lab 09：可靠性账本与最小评测 Runner](../../academy/labs/09_reliability_eval/README.md)
- [Academy expected report](../../academy/labs/09_reliability_eval/expected_report.md)
- [Senza Audit live example](../../live-tests/examples/12_tracing_audit.py)
- [Senza Budget/Pricing live example](../../live-tests/examples/13_budget_pricing.py)
- [下一章：从 Bad Case 到改进提案](10-improvement-proposal.md)
