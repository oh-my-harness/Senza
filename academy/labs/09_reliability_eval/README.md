# Lab 09：可靠性账本与最小评测 Runner

## 要回答的问题

为什么一次演示跑通不能证明 Agent 可上线？《动手学 AI Agent》第 7 章强调评测对象是
Model + Harness 的组合，并区分“多试几次至少成功一次”的 `Pass@k` 与“连续 k 次都
成功”的 `Pass^k`：

```text
Pass@k = 1 - (1 - p)^k
Pass^k = p^k
```

这里的 `p` 必须来自**同一个任务 case、同一个 Model+Harness variant** 的重复运行。不同 case
难度不同，不能先把所有 case 的通过/失败混成一个 pooled `p` 再套公式。本课先按
`(variant, case_id)` 分组计算经验 `p_i` 和两项指标，再对各 case 做等权宏平均：

```text
Macro Pass@k = mean_i(1 - (1 - p_i)^k)
Macro Pass^k = mean_i(p_i^k)
```

总体 pass rate 仍作为全部运行的描述性汇总单独报告，但不用于推导 Pass@k/Pass^k。

理论来源：[`ai-agent-book/book/chapter7.md`](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter7.md)。

## 这一课新增了什么

Runtime/Senza 已有 Audit、Hook、UsageLedger、Pricing 与 Budget，它们能提供轨迹、成本
和中止信息，但不是完整 eval 平台。本课在 `evaluation.py` 中新增一个仅服务教学的
provider-free runner：

1. 从 JSONL 加载 case 与重复运行；
2. 用确定性 verifier 检查结果文本、禁止动作、执行状态与成本上限；
3. 比较 `bare` 和 `guarded` 两个 Model+Harness variant；
4. 输出总体通过率、按 case 估计后宏平均的 Pass@3/Pass^3，以及运行级延迟、成本与 token。

```powershell
python academy/labs/09_reliability_eval/demo.py
python academy/labs/09_reliability_eval/demo.py --mode live --live-example audit
python academy/labs/09_reliability_eval/demo.py --mode live --live-example budget
```

## 如何解释结果

recorded 数据故意让 `guarded` 更可靠、也略贵。`bare` 三个 case 的经验 `p_i` 分别为
`1/3`、`1/3`、`2/3`，所以宏平均估算 Pass@3 为 `0.790123`、Pass^3 为 `0.123457`；
总体通过率则是单独的 `4/9 = 0.444444`。选择规则先看宏平均连续可靠性，再看总体通过率，
最后才以成本打破平局。

这不是为某个生产模型背书：18 条结果是课程 fixture，只证明 runner、verifier 和统计口径可
复现。每个 case 只有三次重复，宏平均还会对每个 case 等权；真实结论需要替换为现场运行记录、
扩大样本，并给出置信区间、任务权重和失败归因。

## 能力边界

- 这是 Academy 教学层，不能宣传为 Runtime/Senza 内建 `senza-eval` 产品；
- Workflow 的 Judge 是路由器，不等于 LLM-as-a-Judge；
- Audit、usage、budget 是评测输入，不自动形成 dataset runner；
- Pass@k/Pass^k 必须在同一 case 内估计后再聚合，不能从跨任务 pooled pass rate 推导；
- 小样本的每 case 经验 `p_i` 与等权宏平均只能用于教学，不能代表总体可靠性；
- live 模式只展示审计与预算数据源，不会伪装成完整 live evaluation。
