# 第 2 章：12 个 Hook——在固定生命周期边界扩展 Agent Core

> 成熟度：**stable**。Runtime 当前公开 12 个 Hook 类型，并为同类 Hook 定义了确定的组合语义。
> Academy recorded 图谱用于核对全部契约；当前 Python live example 只覆盖其中四类，不代表单次
> 在线运行触发了全部 Hook。

## 本章回答的问题

安全策略、上下文治理、成本观测和最终答案校验都需要进入 Agent 循环，但它们不应该各自复制一套
循环。Runtime 怎样让这些能力在正确时机生效？Plugin 是否能在源码任意一行插入逻辑？多个能力
同时挂在一个位置时，谁先执行、谁能覆盖谁？

答案是：Agent Core 预先声明 **12 个 Hook 类型**。Hook 的开放性体现在“同一个固定槽位可以注册
不同实现”，而不是“扩展者可以随意选择代码位置”。每个槽位还有自己的输入、输出和组合代数；
只有理解这些语义，才谈得上安全组合 Plugin。

## 学习目标与先修知识

完成本章后，你应当能够：

1. 准确列出 Runtime 的 12 个 Hook 类型，并说明它们的职责；
2. 区分通知、变换、门禁、合并和聚合等组合语义；
3. 解释 Hook 位置为什么由 Agent Core 定义；
4. 根据注册顺序预测两个同类 Hook 的结果；
5. 为安全、观测或上下文需求选择合适边界，而不是修改 Core 主循环。

先修知识：完成[第 1 章](01-react-tool-calling.md)，理解 run、turn、Provider 调用、Tool Call 与
Tool Result 的关系。

## 理论直觉：稳定循环与可变策略分开

[《动手学 AI Agent》第 1 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)把生产 Agent 展开为
Model 与 Harness，并把 Harness 的工作概括为上下文管理、工具接口、约束、验证与纠正。这个理论
回答了“系统需要哪些职责”，但工程实现还必须回答“这些职责何时获得控制权”。

如果每种能力都直接改 Agent 循环，结果通常是：安全插件复制工具分派，成本插件复制 Provider
调用，记忆插件复制 run 初始化；几次迭代后，任何一处改动都可能破坏其他能力。Hook 的设计把
稳定机制与可变策略分开：

```text
                  Agent Core 拥有控制流
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
  Context Hook       Tool Hook       Answer Hook
  改模型所见信息     管动作与结果      守提交边界
       │                 │                 │
       └──── Plugin / application 提供实现 ┘
```

Core 决定“什么时候问”，Hook 实现决定“在这个边界返回什么”。这种反转控制使 Core 可以保持
稳定，同时让业务策略独立演进。

### Hook 不是事件监听器的同义词

有些 Hook 只观察，例如 `after_provider_response`；有些能修改数据，例如
`transform_context`；有些是门禁，例如 `before_tool_call`。如果把它们都理解成“收到一个事件后
执行 callback”，就会忽略返回值对控制流的影响，也无法判断多个实现怎样组合。

### Hook 也不是 Plugin

Hook 是一个生命周期协议；Plugin 是构建期能力包。应用可以直接向 Builder 注册 Hook，也可以让
Plugin 同时贡献 Tool 和 Hook。两者关系类似“插座规范”与“一组使用这些插座的设备”，不能用
Hook 数量推算 Plugin 数量。

## Runtime/Senza 架构映射

Runtime 的
[`HarnessHooks`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-agent/src/harness/state.rs)保存 12 个
Hook 向量。Builder 按注册顺序追加实现；构建后的 Harness 在运行时把同类实现包装成
[`Composite*`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-loop/src/composite.rs)，再由 Core 在固定
边界调用。

Senza 把 Python callback 包装为对应的 Rust Hook trait。入口定义在
[`Senza/src/lib.rs`](../../../src/lib.rs)，包装与返回值解析位于
[`Senza/src/core/pyhooks.rs`](../../../src/core/pyhooks.rs)，`.hooks([...])` 的装配位于
[`Senza/src/core/pybuilder.rs`](../../../src/core/pybuilder.rs)。

## 12 个固定 Hook 类型

下表中的“组合语义”不是建议，而是当前 Composite 实现的契约。

| Hook | 生效边界 | 单个实现能做什么 | 多实现组合语义 |
| --- | --- | --- | --- |
| `before_run` | 一次 `prompt()` run 开始前 | 追加初始消息、修改 system prompt | 全部按序执行；消息累积；最后一个非空 system prompt 胜出 |
| `before_turn` | Harness 观察到 turn 开始时 | 读取当前配置快照 | 全部按注册顺序执行，纯通知 |
| `transform_context` | 每次 Provider 调用准备上下文时 | 替换结构化 `AgentContext` | 链式；后一个看到前一个的输出 |
| `before_provider_request` | 发起 Provider 请求前 | 原地调整 `StreamOptions` | 全部按序修改同一组选项 |
| `after_provider_response` | 成功得到 Provider 响应后 | 观察延迟、usage、模型等元数据 | 全部按序执行，纯观测 |
| `before_tool_call` | Tool callback 之前 | `Allow`、改参数 `Modify`、拒绝 `Deny` | 第一个非 `Allow` 决策短路 |
| `after_tool_call` | Tool callback 之后 | 保留或替换完整结果 | 链式；每个 `Replace` 成为下一个 Hook 的输入 |
| `after_turn` | Harness 观察到 turn 结束、刷新 Session 前 | 观察本 turn 新消息 | 全部按序执行，纯通知 |
| `prepare_next_turn` | 需要继续时准备下一 turn | 修改上下文、模型、温度、工具等 | 全部执行；每个字段取最后一个非空值 |
| `should_stop` | 模型自然停止后 | 返回是否停止 | 全部执行且不短路；任一 `true` 则聚合为停止 |
| `before_compact` | 真正压缩前的条件分支 | `Proceed`、`Skip`、`Compact`、`Override` | 第一个非 `Proceed` 决策短路 |
| `final_answer_validator` | 候选答案越过 committed boundary 前 | 接受或给出脱敏拒绝原因 | 按序校验；第一个拒绝短路 |

### 五种组合代数

把表背下来不如掌握五种代数：

1. **全执行**：所有实现都获得机会，适合观测或不可遗漏的副作用；
2. **首个决策短路**：一旦得到非默认决策便停止，适合门禁；
3. **链式变换**：前一项输出成为后一项输入，适合可叠加处理；
4. **字段合并**：每个实现只覆盖自己关心的字段；
5. **聚合查询**：所有实现都执行，再把布尔结果汇总。

例如两个 `before_tool_call` Hook 依次为“补默认路径”和“拒绝敏感路径”。如果第一个返回
`Modify`，第二个不会看到修改后的参数，因为该槽位的语义是首个非 Allow 短路，而不是链式改写。
若需要“先规范化再鉴权”，应合并为一个 Hook、调整边界设计，或在 Tool 内建立明确流水线，不能
凭直觉假设多个 Modify 会串联。

反过来，两个 `after_tool_call` Hook 可以串联：注入过滤器先替换结果，来源标签 Hook 再处理已过滤
结果。注册顺序会改变最终嵌套方式，因此顺序必须属于配置和测试的一部分。

## 一条完整执行故事：带安全和观测的 Tool turn

假设 Developer Agent 要调用 `run_query`，我们同时安装以下策略：

- `before_run` 注入当前租户信息；
- `transform_context` 裁剪与本任务无关的旧消息；
- `before_provider_request` 设置本次超时；
- `after_provider_response` 累积 token 使用量；
- `before_tool_call` 只允许只读 SQL；
- `after_tool_call` 给结果附加来源标签；
- `final_answer_validator` 要求最终回答包含证据。

一次成功路径可以这样阅读。

### 运行前：准备任务级输入

用户调用 `prompt()` 后，Core 先处理 run 入口，再调用 `before_run`。Hook 可以追加租户上下文或
覆盖 system prompt。它不能在这里直接替换整个 Agent Core，也不意味着每个 turn 都会重复执行。

`before_compact` 属于压缩分支。自动压缩在 run 开始前按条件发生，因此它不应被强行塞进每一条
普通 Tool timeline；没有达到压缩条件时，这个 Hook 不触发。

### Provider 前后：治理上下文与传输

每次准备模型调用时，`transform_context` 链依次处理结构化上下文。随后 Core 形成 Provider
请求，`before_provider_request` 可以调整当前请求的传输选项。成功收到响应后，
`after_provider_response` 观察 usage 和延迟，但不改写 Assistant Message。

源码中 `transform_context` 在底层循环发出 `TurnStart` 之前执行；`AgentHarness` 消费
`TurnStart` 时再分派 `before_turn`。这说明不要仅凭 Hook 名字猜测源代码的物理先后，重要时应
沿 [`loop_fn.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-loop/src/loop_fn.rs) 与
[`loop_driver.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-agent/src/harness/loop_driver.rs)
核对实际控制流。

### Tool 前后：门禁、执行、结果治理

模型提出 `run_query` 后，Runtime 用 `HookedTool` 包装真实 Tool。`before_tool_call` 先检查名称与
参数：只读且有界的查询返回 Allow；无界查询可以返回 Modify；写操作返回 Deny。只有 Allow 或
Modify 后的有效调用才进入 callback。callback 完成后，`after_tool_call` 链可以替换结果，再把
最终结果作为 Observation 加入轨迹。

### turn 结束：决定下一步

有 Tool Result 且任务尚未终止时，底层 loop 调用 `prepare_next_turn` 合并下一轮配置，然后发出
`TurnEnd`；`AgentHarness` 消费该事件时调用 `after_turn` 并刷新 Session。名称上的 “after turn”
和 “prepare next turn” 不能直接推导内部调用顺序，recorded 图谱也不替代源码时序。

当模型自然停止时，`should_stop` 聚合所有查询。它的全执行语义很重要：即使预算 Hook 已返回
`true`，后面的异步消息 Hook 仍需运行以处理队列，不能因为早期真值而被跳过。

### 提交答案：最后一道边界

模型给出候选最终回答后，`final_answer_validator` 按序校验。第一个拒绝会终止后续 validator，
被拒答案不会作为已提交答案进入上下文或 Session。它检查的是“能否提交”，不是事后给日志打标。

这条故事没有触发全部 12 个 Hook：压缩是条件分支，Tool Hook 只有发生 Tool Call 才出现，
`should_stop` 只在模型自然停止时查询。12 表示**契约类型数**，不是每次 run 的固定回调次数。

## 源码导读：从槽位到控制流

### 1. 类型层：Hook 能看到什么、能返回什么

[`llm-harness-types/src/hooks.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-types/src/hooks.rs)
定义各 Hook trait、上下文和决策类型。例如 `BeforeToolCallCtx` 提供 Tool 名、参数、turn index
和 run 引用；返回值只能是 Allow、Modify 或 Deny。这个类型边界决定 Plugin 能做什么，而不是
Python callback 自由返回任意对象。

### 2. Harness 层：12 个固定向量

[`harness/state.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-agent/src/harness/state.rs) 中的
`HarnessHooks` 明确列出 12 个字段。`none()` 构造全部为空的默认值。新增第 13 个生命周期类型需要
修改 Runtime 契约与控制流；普通 Plugin 不能在运行时“声明一个新槽位”让 Core 自动调用。

### 3. 组合层：同类 Hook 怎样合成

[`composite.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-loop/src/composite.rs) 是本章最值得精读
的文件。建议对照以下实现：

- `CompositeBeforeToolCallHook`：遇到首个非 Allow 立即返回；
- `CompositeAfterToolCallHook`：维护 `current_result`，让 Replace 串联；
- `CompositeTransformContextHook`：逐个传递 `AgentContext`；
- `CompositePrepareNextTurnHook`：按字段保留最后一个非空值；
- `CompositeShouldStopHook`：所有实现都执行，最后做 OR；
- `CompositeFinalAnswerValidator`：`?` 使首个拒绝短路。

这些实现旁边的回归测试是组合语义的直接证据。例如 after-tool 测试验证两个替换都保留，
should-stop 测试验证早期 `true` 不会跳过后续 Hook。

### 4. 运行层：Core 在哪里交出控制权

[`loop_fn.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-loop/src/loop_fn.rs)负责 Provider、Context、
Tool 与停止决策；
[`loop_driver.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-agent/src/harness/loop_driver.rs)负责
run/turn 通知、Session 写入和 Harness 状态。Tool 前后 Hook 不是散落在 callback 内，而是在构建
LoopConfig 时用 `HookedTool` 统一包住所有当前 Tool。

`before_run` 和自动压缩的入口还可以在
[`harness/core.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-agent/src/harness/core.rs)的
`run()` 中核对：自动压缩先处理，随后才是 `before_run`，最后进入 loop。

### 5. Python 层：callback 怎样变成 Hook

[`pyhooks.rs`](../../../src/core/pyhooks.rs) 将 Python callback 包装为 12 种 Hook trait。以
`before_tool_call` 为例，Senza 把 ctx 转为 Python dict，再把字符串或 dict 返回值解析为 Rust
决策；callback 异常会 fail-closed 为 Deny，而不是悄悄放行。

`HookKind` 只包含这 12 类，`push_into()` 根据类型把实现放入对应向量。因此 Python API 虽然写起来
像普通函数，实际仍受 Runtime 类型和槽位约束。

## 配套实验

实验位于 [`academy/labs/02_hook_xray`](../../../academy/labs/02_hook_xray/)。

### 第一步：查看 12 Hook 教学图谱

```powershell
python academy/labs/02_hook_xray/demo.py
```

输出把主路径、压缩分支和答案提交分支放在同一张图中，以便一次核对 12 个名称。请把它当作
**生命周期地图**，不要当作某次真实 run 的逐纳秒日志。

建议把每项标为三类之一：纯观测、可变换、可阻断。然后再标注它的组合代数。你会发现“发生在
前面还是后面”不足以描述 Hook，返回值和组合方式同样重要。

### 第二步：运行契约测试

```powershell
python -m pytest academy/labs/02_hook_xray/test_demo.py -q
```

测试确保 12 个名称各出现一次，并抽查四种不同组合语义：Tool 前短路、Context 链式变换、Stop
全执行聚合、答案首拒短路。它仍然是教学契约测试，不会伪造 Provider 时序。

### 第三步：运行 Python live 覆盖

```powershell
python academy/labs/02_hook_xray/demo.py --mode live
```

live 模式委托
[`live-tests/examples/07_hooks.py`](../../../live-tests/examples/07_hooks.py)，当前只注册
`before_turn`、`after_turn`、`before_tool_call` 和 `after_tool_call`。检查 Tool 前后计数是否对称，
并明确记录：这只能证明四类 Hook 的当前 Python 装配链路，不能外推为 12 类全部在线覆盖。

### 第四步：推演组合顺序

不必修改 Core。手工设计两个 Hook 组合：

1. 两个 `after_tool_call`：第一个给文本加 `[filtered]`，第二个加 `[source=db]`；预测交换顺序后的
   输出，再用单元测试验证。
2. 两个 `before_tool_call`：第一个对某工具返回 Modify，第二个返回 Deny；预测第二个是否会执行。

这两个小练习能直接暴露“所有 Hook 都是广播”这一错误心智模型。

## 常见误解与能力边界

### 误解一：Hook 可以挂在任意源码位置

不可以。Core 只会调用 `HarnessHooks` 中声明的 12 类。Plugin 可以选择一个或多个现有槽位并注册
实现；若业务确实需要新的生命周期时机，应先修改 Runtime 契约、控制流和测试，再向上暴露 API。

### 误解二：同类 Hook 都会依次执行到底

只有全执行类保证如此。`before_tool_call`、`before_compact` 和最终答案校验存在短路；而
`after_tool_call` 与 `transform_context` 虽都执行，后者看到的是前者变换后的数据。必须按每个
Composite 的语义判断。

### 误解三：后注册的安全 Hook 总能兜底

如果前面的 `before_tool_call` 已返回 Modify 或 Deny，后面的 Hook 不会运行。安全 Hook 的注册
顺序不能依赖“最后一道防线”的直觉，应通过组合设计与测试明确保证。

### 误解四：Hook 是 built Harness 的热插拔点

Hook 在 Builder 阶段收集并在 Harness 构建时组合。当前公开使用方式不是在正在运行或已经构建的
Harness 上任意增删 Hook；“生命周期扩展点”不等于“运行时热补丁”。

### 误解五：recorded 图谱证明全部实时顺序

图谱用于覆盖契约类型，把条件分支并排展示。真实顺序和调用次数要由 Runtime 源码、专项测试或
对应 live example 证明。尤其不要声称普通 Tool run 必然触发压缩 Hook。

### 能力边界

- Hook 类型固定为 12，数量不得与 Plugin 或 Senza 内置策略工厂数量混淆；
- Python 当前暴露 12 类包装，但每个 live example 的覆盖面可能更小；
- Hook callback 能使用的 ctx 由 trait/Python 适配明确提供，不自动获得任意内部状态；
- `before_provider_request` 当前直接作用于 Runtime 使用的部分 `StreamOptions`；其他传输字段是否
  生效还取决于 Provider adapter 支持，不能仅凭 Python dict 中出现字段就宣称已透传；
- Hook 提供控制边界，但外部持久化、身份系统、数据库事务或沙箱仍需相应后端基础设施。

## 小结

12 个 Hook 把 Harness 的可变策略安放在稳定 Agent Core 周围。真正决定可组合性的，不只是“有一个
Hook 点”，而是固定时机、类型化输入输出、注册顺序和 Composite 语义。Plugin 能轻松增加能力，
正因为它复用这些协议；也正因为协议固定，扩展不会退化为任意代码注入。

## 复习题

1. 为什么 `before_tool_call` 采用首个非 Allow 短路，而 `after_tool_call` 采用链式替换？
2. 两个 `prepare_next_turn` Hook 分别修改 model 和 temperature，结果如何合并？若都修改 model 呢？
3. `should_stop` 为什么不在第一个 `true` 时短路？请结合潜在副作用解释。
4. 哪些 Hook 可能在一次没有 Tool Call、没有压缩的 run 中完全不出现？
5. 你要实现“记录 Provider 成本”和“拒绝危险 Shell 参数”，分别应选哪个 Hook？为什么？
6. 如果需求是“在工具参数标准化之后再鉴权”，直接注册两个 `before_tool_call` Hook 有什么风险？
7. 什么情况下应新增 Plugin，什么情况下必须修改 Agent Core 增加新的 Hook 契约？

## 延伸阅读

- 理论坐标：[《动手学 AI Agent》第 1 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)中的 Harness
  工程、约束、验证与纠正；
- Hook 权威类型：[`hooks.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-types/src/hooks.rs)；
- 组合实现与回归测试：[`composite.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-loop/src/composite.rs)；
- Academy 图谱：[`Lab 02 README`](../../../academy/labs/02_hook_xray/README.md)；
- Python live 示例：[`07_hooks.py`](../../../live-tests/examples/07_hooks.py)；
- 下一章：[Plugin 装配](03-plugin-composition.md)，把 Tool 与 Hook 组合成可复用能力包。
