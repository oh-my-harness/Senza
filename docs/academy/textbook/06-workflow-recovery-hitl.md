# 第 6 章：Workflow——在步骤边界恢复、暂停与引入人工决策

> 成熟度：**stable**。WorkflowEngine、Executor、TaskStore、按步恢复、暂停/取消和外部事件 Tool
> 均有当前 Senza/Runtime 源码与测试支持；配套 recorded checkpoint 是 **teaching** 实现，不等同于
> 真实 WorkflowEngine 或事件通道。

## 本章回答的问题

当一个任务同时包含开放式写作、确定性检查、人工审批和不可重复的外部动作时，把所有决定都交给
一个自由循环并不稳妥。本章回答六个工程问题：

1. 哪些工作适合留在 LLM step 内，哪些边界应该写进 Workflow？
2. Executor、Judge 和 Agent Core 在一条流程中分别负责什么？
3. TaskStore 保存了什么，又为什么不能把它当成数据库事务？
4. `restore_from_step()` 究竟截断什么，哪些状态不会随历史一起回滚？
5. Workflow 的 `pause()` 与 `wait_for_external_event` Tool 有何不同？
6. 为什么“支持恢复”和“外部副作用只发生一次”是两项不同能力？

本章使用“生成发布说明 → 规则检查 → 人工批准 → 发布”这一条完整链路来回答这些问题。重点不在
画出更多方框，而在确定每个方框之间能作出什么可靠承诺。

## 学习目标与先修知识

完成本章后，你应该能够：

- 把开放决策留在 step 内，把审批、恢复和终止条件放到明确的 step 边界；
- 区分 LLM step、确定性 Executor 与 StepTransitionJudge；
- 解释普通恢复、`restore_from_step()`、`resume()` 和再次 `run()` 的关系；
- 设计不会误用旧审批、不会重复扣款或重复发布的恢复协议；
- 正确选择状态机暂停或外部事件等待，并说明各自的可恢复性限制；
- 从 step history、checkpoint、WorkflowEvent 与业务系统记录中组织审计证据。

建议先掌握[第 1 章的 Agent/Workflow 区分](01-react-tool-calling.md)和
[第 3 章的能力装配](03-plugin-composition.md)。理论背景可阅读本地《动手学 AI Agent》的
[第一章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)与
[第六章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter6.md)。

## 理论直觉：把不确定性关在步骤里，把保证放在步骤间

### Workflow 不是 Agent 的反义词

开放问题需要模型理解语义、生成候选方案或处理不完整输入；合规检查、额度计算和状态流转则通常
有明确规则。Workflow 的价值不是消灭模型，而是给模型划定作用域：一个 step 内仍可运行完整的
Agent Core，step 之间由显式状态机接管。

可以把一条混合流程理解为：

```text
LLM step：生成候选内容
      │ StepResult
      ▼
Executor：执行确定性规则检查
      │ StepResult
      ▼
Judge：根据结果选择 To / Retry / Pause / Fail / Abort
      │
      ▼
下一 step 或终态
```

LLM step 负责在约束内解决开放问题；Executor 运行注册好的程序，不需要为纯计算消耗一次模型调用；
Judge 只决定下一条 Transition，而不是代替 step 完成业务工作。三者分离以后，我们可以分别测试
内容质量、确定性计算和路由规则。

### step 边界是恢复边界，也是治理边界

模型一次生成中途的隐藏推理状态通常无法可靠序列化，外部命令也可能已部分生效。因此 Runtime 把
可恢复语义落在 step 记录、当前 step、共享 context 和 checkpoint 上。一个 step 完成并持久化以后，
引擎才有稳定的“上一步已完成、下一步从哪里开始”事实。

这条边界也适合放审批和策略决策：发布 step 是否可进入，不依赖模型在长上下文中记得一句“请先
确认”，而依赖前一 step 的结构化结果与明确 Transition。安全性由状态机控制流表达，而不是只由
自然语言提醒表达。

不过，step 边界只说明**从哪里重新驱动状态机**。它不会自动撤销已经发送的邮件、已经写入的数据库
或已经调用的支付接口。外部副作用还需要幂等键、业务状态查询、outbox、补偿动作或人工处置。

### 持久化状态不等于时间旅行

TaskStore 可以保存 Workflow 定义、WorkflowState 与 checkpoint，使新进程能够重建引擎。保存下来的
step history 是审计链，current step 是下一次驱动位置，context 是各步共享的黑板。

但恢复不是把整个世界退回某个时刻。尤其是 `restore_from_step(target)`：它截断目标 step 本身及其
后续历史，却**不会回滚当前 context 黑板**。这是一项刻意且有测试覆盖的语义。若下游 step 曾把
`approval=true` 写进 context，从更早的 check 重跑时，业务代码必须清除、带版本读取或重新验证这项
值，不能因历史被截断就假设黑板也回到了过去。

## Runtime/Senza 架构映射

| 职责 | Senza 入口 | Runtime 落点 | 可作出的承诺 |
| --- | --- | --- | --- |
| 流程拓扑 | `WorkflowEngine(workflow, ...)` | `Workflow`、`Step`、`Edge` | entry、step id、edge 引用等在运行前被校验 |
| 开放式步骤 | workflow 中带 `prompt` 的 step | 每步构建 Harness 并运行 Agent Core | 在该 step 的工具/预算范围内生成结果 |
| 确定性步骤 | `.with_executor(name, executor)` | Executor registry | 用程序计算 `StepResult`，不必调用模型 |
| 路由 | `create_judge(callback)` | `StepTransitionJudge`、`Transition` | 在 step 结果之后选择下一状态 |
| 持久化 | `.with_task_store(dir)` | `TaskStore` / `JsonlTaskStore` | 保存流程、状态、上下文与 checkpoint 供恢复 |
| 按步重跑 | `WorkflowEngine.restore_from_step(...)` | `runner.rs` 的截断与重定位 | 保留目标之前历史，从已执行过的目标 step 重驱动 |
| 操作者暂停 | `engine.pause(reason)` | `pause_requested` 标志 | 非阻塞请求，在受支持的 step 边界消费 |
| 人工/外部事件 | `create_event_channel()` + `.with_external_tool()` | `WaitForExternalEventTool` | Tool 内等待事件，事件到达后作为 ToolResult 续跑 |
| 观察与终止 | `state()`、`step_history()`、`cancel()` | `WorkflowEvent`、状态与取消令牌 | 暴露步骤级事实；取消不等于撤销外部副作用 |

### `restore()` 与 `restore_from_step()` 不是同一意图

普通 `restore()` 按已保存的 current step 和状态继续，适合进程异常退出后的常规恢复。
`restore_from_step(target)` 则是操作者明确要求“把这个已执行 step 以及下游作废，再从这里重跑”。它
执行以下动作：

1. 从 Store 加载并重新校验 Workflow、State 和 checkpoint；
2. 确认 target 既存在于 Workflow，也已经出现在 step history；
3. 用最后一次出现的位置截断历史，因而 Retry/rework 场景从 target 的最近一次执行处回退；
4. 将 current step 指向 target，把状态设为 Paused；
5. 清除旧的 reason、result、error 与 ended_at，并持久化改写后的状态；
6. 保留 task id、规划来源、checkpoint 与当前 context；调用方随后再执行 `run()`。

target 未执行过时不能凭空从那里恢复。若 target 是入口 step 且曾执行过，历史会被清空。恢复后的
provider、model、judge 和需要的 execution env 由 Python 调用重新提供；自定义 Executor、Tool、Hook
等运行期依赖也应按流程需要重新注册，不能假设函数对象已被 JSON 持久化。

### 两种“等待人”的语义必须分开

第一种是**状态机暂停**。Judge 可以返回 `pause:<reason>`，Runtime 在当前 step 已产生结果、应用
Transition 时把 WorkflowState 写成 Paused。外部代码也可调用 `engine.pause(reason)`；该调用只是设置
标志并立即返回，运行循环在 `To` 或 `Retry` 的 step 边界检查它。它不是对正在进行的 Provider 请求
或任意宿主进程的强制抢占。

暂停后，直接再次 `run()` 可以完成 Paused → Running。`resume()` 的作用是把 Paused/Failed 准备成
可继续状态并发出 Resumed 事件；它本身不运行下一步，调用方仍需 `run()`。Succeeded 与 Cancelled
是终态，不能用 `resume()` 重新打开。

第二种是 **Tool 内等待外部事件**。模型调用 `wait_for_external_event` 后，Tool 在
`stream.next().await` 上等待；同一进程中持有 handle 的另一线程或控制面调用
`handle.submit(...)`，事件成为 ToolResult，原来的 Agent loop 自然进入下一 turn，**不需要调用
`resume()`**。handle 底层是进程内 channel，不是网络或 IPC endpoint；外部服务需要由应用自建
webhook、消息队列或其他桥接。这段等待并不会自动把 WorkflowState 标成 Paused，所以 UI 和恢复
逻辑不能只看“Tool 名字像暂停”就推断状态机已暂停。

当前 Python `create_event_channel()` 构造 Tool 时没有注入 TaskStore。Runtime 底层 Tool 虽支持保存
event-wait descriptor，但 Python 这一工厂路径不会持久化该等待描述符；进程崩溃后重建 EventStream
仍是业务层职责。默认等待超时为 300 秒，超时返回普通 ToolResult 提示，而不是一次持久的人工审批。

## 一条完整执行故事：发布说明的生成、复核与发布

### 1. `draft`：让模型处理开放输入

产品变更由多条 issue、commit 和用户说明构成。`draft` step 允许 LLM 阅读这些材料并生成一版发布
说明。此处需要语义归纳，适合 Agent Core；工具范围仍应限定为只读数据源。

step 完成后，输出形成 StepResult，并在历史中留下记录。不要让模型在同一 step 顺手发布，因为那会
把开放生成与高风险副作用绑成一个难恢复单元。

### 2. `check`：用 Executor 做确定性检查

`check` Executor 验证必需标题、版本号、禁用词和链接格式。它接收共享 context 或前一步输出，返回
`passed` 及结构化错误列表。规则代码可以单元测试，也不会因为模型措辞变化而改变路由标准。

若检查失败，Judge 可将流程导向修订 step 或 Retry；若通过，则进入 approval 边界。重试次数必须有
上限，否则“确定性 Workflow”同样会形成无限循环。

### 3. `approve`：明确停在发布之前

流程到达审批点后应持久化“正在等谁批准哪一版内容”。一种设计是让 Judge 返回 Pause，使状态变为
Paused；另一种设计是在审批 step 中调用外部事件 Tool。两者都应把待审批对象的内容哈希或版本号
交给审批系统，避免审核者批准 v1，恢复后却发布已经变化的 v2。

Academy recorded 场景选择一个小型 JSON checkpoint，写下 `status=paused`、
`current_step=approve`，并确认 history 中尚无 publish。它便于无 Provider 地展示不变量，但不是
WorkflowEngine、TaskStore 或 EventStream 的替身。

### 4. 模拟故障：从 `check` 重放

假设审批前发现规则版本配置错误。操作者选择从已经执行过的 `check` 恢复：旧 check 及旧 approval
历史被废弃，draft 记录保留，current step 回到 check，状态为 Paused。再次 `run()` 后，新规则重新
检查，再产生新的审批请求。

真实 Runtime 取 step history 中 check 的**最后一次出现**作为截断点。Lab 里的 `attempt=2` 是教学
模型自己维护的可视化字段，并非据此推导 Runtime 有完全相同的 attempt schema。

此时尤其要检查 context。Runtime 不会把黑板回滚到旧 check 之前，旧 approval、旧规则版本或下游
缓存可能仍在。稳健做法是让每份结果绑定 workflow revision，并在进入 publish 前重新读取权威审批
记录，而不是只相信 context 中一个布尔值。

### 5. 审批事件到达：验证身份与对象

Reviewer 提交 `approved=true`、身份和被批准内容的版本。业务接入层先验证认证、授权、防重放和对象
一致性；若 Reviewer 位于另一个服务，业务接入层还要把外部事件桥接到持有 handle 的进程，再提交
到 channel，或先写入业务 Store。`EventStreamHandle.submit()` 只负责进程内传递 content/details；
一个字符串形式的 `reviewer="alice"` 本身不构成身份认证。

若使用外部事件 Tool，ToolResult 回到同一 step，模型可据此完成内容；若使用 Workflow Pause，控制
面准备好状态后再调用 `run()`。两条路径不应混写成“submit 以后 resume 一定要调用”。

### 6. `publish`：让副作用具备幂等语义

发布 step 再次核对审批版本，然后以 task id + revision 作为幂等键调用发布系统。若网络在“服务端
已发布、客户端未收到响应”后断开，重跑会先查询幂等结果，而不是再次发布。

最终 Workflow 进入 Succeeded，step history、业务发布记录和审批系统记录共同构成证据。TaskStore
说明引擎经历了哪些状态；外部系统记录说明副作用实际发生了什么，二者缺一不可。

## 源码导读

建议沿着“定义 → 执行 → 持久化 → 恢复 → 外部事件”依次阅读：

1. [`workflow/model.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime/src/workflow/model.rs)
   定义 Workflow、不同 Step、WorkflowState、StepRecord 与 Transition；
   [`workflow/judge.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime/src/workflow/judge.rs)
   定义 step 结果到 Transition 的判断接口。
2. [`engine/runner.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime/src/workflow/engine/runner.rs)
   展示运行循环、step history 落盘、`restore_from_step()`、边界暂停、恢复和取消。这里的注释明确写出
   context 不回滚与 `rposition` 语义。
3. [`task_store.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime/src/lifecycle/task_store.rs)
   是 TaskStore 合约和 JSONL 实现；持久化格式是恢复输入，因此加载后仍需校验 Workflow。
4. Senza 的 [`pyworkflow.rs`](../../../src/runtime/pyworkflow.rs) 暴露 Python 构造、Executor/Judge 注册、
   restore、pause/resume/cancel 和 step history；`parse_transition()` 也可核对 `pause:<reason>`。
5. [`event.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime/src/lifecycle/event.rs) 实现
   `WaitForExternalEventTool` 的 event/timeout/abort 三路等待；
   [`pyeventstream.rs`](../../../src/core/pyeventstream.rs) 展示 Python channel 工厂为何使用
   `task_store=None`。
6. 若要核对边界行为，阅读
   [`engine/tests.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime/src/workflow/engine/tests.rs) 中
   restore、context 不回滚、暂停与恢复的用例，不要只根据 live 示例输出推断完整契约。

## 配套实验

在 Senza 仓库根目录运行 [Lab 06](../../../academy/labs/06_workflow_recovery_hitl/README.md)：

```powershell
python academy/labs/06_workflow_recovery_hitl/demo.py
python -m pytest academy/labs/06_workflow_recovery_hitl/test_demo.py -q
```

recorded 模式会创建临时 checkpoint，依次展示 paused、从 check 重放、再次等待审批、批准后 publish。
请验证以下不变量：

1. 首次 paused 状态下 history 里没有 publish；
2. 从 check 恢复后 draft 保留，check 与 approve 的教学 attempt 增加；
3. 旧下游历史被替换，而不是和新审批混在一起；
4. 未处于 approval 等待状态时，不能重复批准；
5. checkpoint 写在临时目录，不污染仓库。

随后阅读
[`workflow_scenario.py`](../../../academy/labs/06_workflow_recovery_hitl/workflow_scenario.py)，确认
`approve_and_publish()` 是确定性教学函数，不是 `create_event_channel()` 的实现。具备真实 Provider
配置后，可分别运行四个 live 入口：

```powershell
python academy/labs/06_workflow_recovery_hitl/demo.py --mode live --live-example workflow
python academy/labs/06_workflow_recovery_hitl/demo.py --mode live --live-example executor
python academy/labs/06_workflow_recovery_hitl/demo.py --mode live --live-example hitl
python academy/labs/06_workflow_recovery_hitl/demo.py --mode live --live-example recovery
```

它们委托
[`08_workflow.py`](../../../live-tests/examples/08_workflow.py)、
[`39_executor_steps.py`](../../../live-tests/examples/39_executor_steps.py)、
[`41_human_in_the_loop.py`](../../../live-tests/examples/41_human_in_the_loop.py)与
[`45_hooks_retries.py`](../../../live-tests/examples/45_hooks_retries.py)，分别验证基础路由、混合 Executor、
Tool 内等待事件和按步恢复。注意第 41 号示例演示的是 event Tool 等待，不等价于 WorkflowState=Paused。

## 常见误解与能力边界

### 误解 1：用了 Workflow 就不能在步骤里使用 Agent

Workflow 约束的是跨步骤控制流。一个带 prompt 的 step 仍可运行 Agent Core 和允许的工具；另一个
step 可以是无模型的 Executor。真正的设计问题是把哪类不确定性放在哪个边界内。

### 误解 2：TaskStore 能像数据库事务一样回滚外部世界

TaskStore 保存引擎可恢复状态，不会撤销邮件、文件、支付或发布。涉及副作用的 step 必须自行实现
幂等、查询现状、补偿或人工确认。

### 误解 3：`restore_from_step()` 会恢复该 step 执行前的所有变量

它截断 step history，却保留当前 context 和 checkpoint。目标还必须存在且已经执行过。恢复后应把
context 当成“来自较晚时刻的黑板”，显式清理或按版本重新验证可能过期的值。

### 误解 4：调用 `pause()` 会立即打断任何正在执行的操作

外部 `pause()` 是非阻塞请求，运行循环在受支持的 step 边界消费。它不承诺抢占正在进行的 Provider
请求，更不会撤销已发生的系统调用。需要立即止损时可调用 `cancel()`，但取消仍依赖当前执行代码
响应取消令牌，且同样不回滚既有副作用。

### 误解 5：外部事件 Tool 会把 Workflow 状态改成 Paused

它阻塞在一个 Tool call 内，事件到达后返回 ToolResult 并自然续跑，无需 `resume()`。当前 Python
channel 工厂也不持久化等待描述符，不能把它宣传成进程重启后自动恢复的人审队列。

### 误解 6：event payload 带 reviewer 字段就完成了身份验证

Runtime 传输 JSON 内容，不替业务验证登录态、权限、签名、防重放或审批对象版本。高风险审批必须
由可信控制面验证后再提交事件。

### 误解 7：recorded checkpoint 已经证明真实引擎可恢复

recorded 场景只证明教材定义的状态不变量，并故意使用简单 JSON 与直接函数调用。真实持久化、Hook
调度和 Provider 行为要由 Runtime 测试与 45 号 live 示例证明。

### 误解 8：`resume()` 等于“恢复并继续执行”

当前 API 的 `resume()` 只准备状态并落盘，随后仍需 `run()`；Paused 状态也可由 `run()` 直接接续。
把状态转换与执行动作分开，能避免控制面一次调用隐式启动长任务。

## 本章小结

Workflow 的核心价值，是把开放式能力放进受控 step，把确定性计算、路由、审批和恢复放在明确边界。
Senza/Runtime 能持久化流程状态、从已执行 step 重放、在边界暂停，并通过 Tool 等待外部事件。但这些
能力不自动带来外部副作用事务、身份认证、context 时间旅行或进程重启后的事件流重建。可靠系统要
把状态机证据与业务系统的幂等、授权和审计记录结合起来。

## 复习题

1. 为什么生成草稿适合 LLM step，而字段校验更适合 Executor？
2. Judge 返回 `Pause` 与外部调用 `engine.pause()` 分别在什么时候生效？
3. `restore_from_step("check")` 对 step history、current step、status、context 和 checkpoint 各做什么？
4. 为什么从最近一次 target 执行处截断对 Retry/rework 场景很重要？
5. `resume()` 与 `run()` 的职责如何分工？
6. `wait_for_external_event` 收到事件后为什么不需要 `resume()`？
7. 若发布接口在返回前断网，Workflow 重跑时怎样避免重复发布？
8. 审批事件至少要绑定哪些身份与内容信息，才能避免批准对象错位？

## 延伸阅读

- 理论：[《动手学 AI Agent》第 1 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)与
  [第 6 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter6.md)
- 实验：[Lab 06 README](../../../academy/labs/06_workflow_recovery_hitl/README.md)与
  [`expected_trace.json`](../../../academy/labs/06_workflow_recovery_hitl/expected_trace.json)
- 真实恢复：[Senza hooks/retries/restore 示例](../../../live-tests/examples/45_hooks_retries.py)
- 真实事件等待：[Senza HITL 示例](../../../live-tests/examples/41_human_in_the_loop.py)
- 源码地图：[Runtime/Senza 源码地图](appendix-source-map.md)
- 下一章：[知识、记忆与召回](07-knowledge-memory-recall.md)
