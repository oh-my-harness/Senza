# 第 10 课：从 Bad Case 到待审批改进提案

这一课回答最后一个问题：当运行轨迹反复暴露同一种失败时，怎样把它转成可验证的改进
候选，同时避免 Agent 用一次局部成功直接改写正式能力或安全门槛？

本课是 **Senza Academy 的教学应用层**。它不表示 Runtime 已内建自动进化闭环，也不会
安装 Plugin、写入生产 Skill、修改 Runtime/Senza 源码或启动 SFT/RL。

## 理论坐标

理论参考本地《动手学 AI Agent》第九章
[`ai-agent-book/book/chapter9.md`](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter9.md)：

- “从运行轨迹中获得学习信号”：先评价并定位首个错误步骤，再生成改进假设；
- “将经验写成指令 / 程序”：可语言化流程可形成 Skill，高风险硬约束应形成可测试的
  程序或 Harness 候选；
- “构建可长期运行的持续进化闭环”：在线执行只记录证据，离线流程生成提案并验证；
- “持续进化的安全边界”：待验证能力与正式能力隔离，安全测试、审批门槛、审计日志和
  稳定版本不可由提案生成器自行修改。

书中的关键工程原则是：修复触发失败的 **boundary set** 必须改善，原本工作的
**retention set** 不能退化；即使两者都通过，结果仍只是等待独立审批的候选。

## 本课流程

```text
fixtures/bad_cases.jsonl
        │
        ▼
定位首个错误：before_tool_call 放过 DELETE without WHERE
        │
        ├── Plugin proposal：结构化 rule_config，作为硬边界候选
        └── Skill proposal：结构化步骤与边界说明，作为操作指导候选
        │
        ▼
规范化 diff + candidate_digest + target preflight
        │
        ▼
读取 proposal.rule_config 做 boundary replay + retention regression
        │
        ▼
awaiting_human_approval
        │
        └── 本课到此停止：不 install、不 publish、不改生产文件
```

[`proposal.py`](proposal.py) 是纯 Python、provider-free 的教学 helper。它读取 JSONL，把可执行的
Plugin `rule_config` 与 Skill 内容放进内存 proposal，由 artifact 确定性渲染 diff，再对关键字段计算
SHA-256 `candidate_digest`。preflight 通过后，boundary/retention replay 从这个 proposal 读取同一份
`rule_config`，不再验证一个与提案分离的硬编码替身。`demo.py` 只打印结果，不把 proposal 写入仓库。

Fixture 是合成的历史 bad case，不是在声明当前 `32_plugins.py` 或 Runtime 仍允许危险
DELETE。live 模式用于观察现有 Plugin 安全边界和审计证据，而不是证明自动进化。

## 运行

从 Senza 仓库根目录执行：

```powershell
# 默认 recorded：标准库即可，无 Provider、无 Senza 依赖
python academy/labs/10_improvement_proposal/demo.py

# live：分别观察真实 Plugin guard 与审计示例
python academy/labs/10_improvement_proposal/demo.py --mode live --live-example plugins
python academy/labs/10_improvement_proposal/demo.py --mode live --live-example audit

# 离线验收
python -m pytest academy/labs/10_improvement_proposal/test_demo.py -q
```

`plugins` 委托
[`32_plugins.py`](../../../live-tests/examples/32_plugins.py)，`audit` 委托
[`12_tracing_audit.py`](../../../live-tests/examples/12_tracing_audit.py)。两者展示可供改进流程
消费的真实组件与证据，但 Runtime 当前没有把它们自动串成“诊断→提案→验证→发布”系统。

## 产出的候选

- Plugin proposal：`rule_config` 在 `before_tool_call` 对 `DELETE` 且缺少 `WHERE` 的 SQL 返回
  结构化 `deny`；继续保留有界 SELECT、无界 SELECT 自动加 `LIMIT 100`、带 WHERE 的 DELETE 和
  非 SQL 健康检查行为。回放器实际解释这份配置。
- Skill proposal：结构化内容建议操作者在删除前先做同条件 SELECT 预览，并显式给出 WHERE。
  Skill 只是可审查的操作指导，不能充当不可绕过的安全边界。
- Diff preview 与 digest：diff 由两个 artifact 确定性生成；`candidate_digest` 绑定 proposal ID、来源、
  artifact 与 diff。任一内容被单独篡改，preflight 会拒绝回放。

## 审批与安全边界

- 默认课程候选在全部门通过后停在 `awaiting_human_approval`；任何门失败则拒绝，测试通过也不等于
  自动接受或发布。
- candidate target 必须精确等于两条 review-only 路径之一；这是**精确 allowlist**，不是字符串包含
  判断。真实的 `fixtures/bad_cases.jsonl`、`fixtures/retention_cases.jsonl` 与教学模型中的
  `trust_roots/*` 另列为 protected paths，候选不能把它们声明为目标。**安全机制不能自我修改**。
- preflight 同时检查 artifact schema、规范化 diff、`candidate_digest`、target 唯一性、allowlist 和
  protected paths；失败时拒绝运行 replay。即使重新计算 digest，受保护或未列入 allowlist 的 target
  仍会被拒绝。
- 本课不调用 `senza.create_plugin()`、`HarnessBuilder.plugin()`、包管理器或训练系统，且没有
  apply/install/train 操作；最终只返回内存 proposal，明确不 install、不 publish、不改生产文件。
- 这些测试只证明传入的**内存 bundle 与声明 target**满足教学契约，并快照 Lab 目录中的非缓存文件。
  它们不能证明任意目录外副作用、外部安装、网络动作或训练任务绝不发生；真实系统需要沙箱、权限、
  审计和独立发布基础设施。
- Runtime/Senza 能提供 Hook、Plugin、审计和运行轨迹等积木，但当前没有自动进化产品
  闭环；Academy helper 不是 Runtime API。
- SFT、RL、蒸馏和奖励训练属于外部训练系统。本课既不生成训练任务，也不声称测试结果
  能证明参数学习、长期泛化或线上收益。
