# 第 4 章：Context Layers——把上下文当成受预算约束的工作区

> 成熟度：**stable**。本章涉及的 Skill、StatusPanel、手工压缩与自动压缩都有当前
> Senza API 和 Runtime 源码支持；配套 recorded trace 只负责解释结构，不冒充 Provider 抓包。

## 本章回答的问题

一次 Agent 请求里既有长期不变的系统规则，也有刚刚发生的工具结果。若把它们都当成“一大段
Prompt”，我们就很难回答下面这些工程问题：

1. 哪些内容应该尽量稳定，哪些内容必须随执行更新？
2. 为什么 Skill 只常驻目录信息，完整正文要等到需要时再读？
3. 状态栏和原始轨迹分别解决什么问题，为什么二者不能互相替代？
4. 上下文接近窗口限制时，手工压缩和自动压缩分别怎样触发？
5. 压缩以后哪些信息必须保留，又有哪些信息注定会损失？

本章把模型每次看到的工作区拆成五个教学层：**稳定前缀、Skill、Status、Trajectory 和
Compaction**。这五层是分析框架，不是五种固定的 API message role。

## 学习目标与先修知识

完成本章后，你应该能够：

- 根据变化频率为上下文信息分层，而不是不断扩写 system prompt；
- 解释 Senza 中 `load_skills()`、`builder.skills()` 与 `skill_read` 的分工；
- 沿着 `StatusPanelPlugin` 找到它贡献的工具和 Hook；
- 区分 `harness.compact()` 与 `.auto_compact(True)` 的触发时机和失败语义；
- 为压缩摘要列出任务约束、关键决策、失败证据与下一步，而不把摘要当成无损存档。

建议先完成[第 1 章](01-react-tool-calling.md)和[第 3 章](03-plugin-composition.md)，知道
Agent Core 如何消费工具结果，以及 Plugin 是构建期能力包。理论背景可先读本地《动手学 AI
Agent》的[第一章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)与
[第二章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter2.md)。

## 理论直觉：上下文是一张不断变化的工作台

### 先按“变化速度”分类

想象一张开发者的工作台。墙上的安全规范很少变化；工具说明书只在使用时翻开；白板上的 TODO
会持续更新；终端记录不断增长；桌面太乱时，人会把旧记录整理成一页交接摘要。上下文治理做的
正是同一件事：不让不同生命周期的信息彼此污染。

| 教学层 | 它回答什么 | 典型变化频率 | 主要风险 |
| --- | --- | --- | --- |
| Stable prefix | 我是谁、必须遵守什么、有哪些核心工具 | 低 | 动态内容混入前缀，增加重算与歧义 |
| Skill | 当前任务需要哪份专项操作手册 | 按需 | 所有正文常驻，挤占预算、稀释注意力 |
| Status | 任务此刻进行到哪里、工具用了几次 | 每轮或每次动作后 | 状态计算错误后被模型直接相信 |
| Trajectory | 用户、模型与工具实际发生了什么 | 持续追加 | 长度增长、噪声累积、关键约束被淹没 |
| Compaction | 旧轨迹中以后仍需使用的高密度结论 | 接近阈值或人工触发 | 有损摘要漏掉理由、失败路径或来源 |

这里的第一原则不是“越短越好”，而是**让每类信息待在适合自己的生命周期里**。稳定内容尽量
不动，动态状态放在靠近模型下一次输出的位置，大段专业指令按需加载，旧证据则在确有必要时批量
提炼。

### Skill 是渐进披露，不是工具的别名

Skill 更像一份专项工作手册：目录中的名称与描述先让模型知道“有这项能力”，任务命中后再通过
`skill_read` 读取正文或子文件。Tool 则是改变或观察环境的可执行接口。一个代码审查 Skill 可以
要求先检查测试、安全和错误处理，但真正读取文件、运行测试仍要调用 Tool。

这种分离带来两个收益：没有被选中的领域知识不占据完整上下文；Skill 正文和参考资料又可以独立
版本化。代价是路由描述必须写清楚，否则模型可能不加载该加载的 Skill，或把无关 Skill 拉进轨迹。

### Status 是“提前算好的结论”，Trajectory 是证据

长轨迹里可能散落着三次 `read`、两次失败测试和一个仍未完成的 TODO。让模型每轮重新统计，既浪费
推理，也容易数错。StatusPanel 用代码维护 TODO、环境和工具计数，再把结构化结果放到上下文末尾。

但状态栏只回答设计者预先选择的维度。例如“`read` 调用了 3 次”不能告诉我们第三次到底读到了
什么。因此 Status 是对 Trajectory 的**有损投影**；做决策时可以快速参考，做审计时仍要回到原始
消息、工具结果和外部产物。

### Compaction 是改写表示，不是删除事实的许可证

压缩把较老的轨迹换成更高密度的摘要，并保留近期消息供模型继续工作。好的摘要应至少回答：目标
是什么、已经完成什么、作过哪些关键决定、下一步是什么、哪些约束和证据绝不能丢。它能控制长度，
也能减少模型反复从原始记录中归纳状态的成本。

压缩仍然是有损操作，而且通常要额外调用一次模型。摘要模型可能遗漏早期架构理由，也可能把尚未
验证的推测写成事实。真正需要长期保留的决策、测试结果和用户约束，应该同步写入项目文档、审计
记录或业务 Store，而不是只寄希望于会话摘要。

## Runtime/Senza 架构映射

| 教学层 | Senza 装配面 | Runtime 落点 | 由谁维护 |
| --- | --- | --- | --- |
| Stable prefix | `HarnessBuilder.system_prompt()` 与构建期工具集合 | Harness state 与 Provider request 转换 | 应用在构建期确定，Core 在请求间复用 |
| Skill catalog | `load_skills()`、`.skills()` | run 开始时注入 `<available-skills>` 元数据 | Skill loader 与 Agent Core |
| Skill content | 自动注册的 `skill_read` | `SkillReadTool` 在 Skill 根目录内读取正文/子文件 | 模型按需调用，Runtime 校验路径 |
| Status | `senza.strategy.status_panel()` | `transform_context` + `after_tool_call`，并贡献 `todo_write` | Plugin 内的 store、collector 与 Hook |
| Trajectory | `Harness` 的多轮消息接口 | Session entries 与 Agent messages | Agent Core 按真实交互追加 |
| Compaction | builder 的窗口/保留配置、`harness.compact()` | `try_auto_compact()`、`before_compact`、summary 与 Session compaction entry | Core 决定时机，摘要模型生成表示 |

两个实现细节尤其重要。

第一，当前 Runtime/Senza 的自动压缩默认值是 **false**，必须显式调用 `.auto_compact(True)` 才会在
每次新 run 入口检查阈值。阈值由模型上下文窗口减去 reserve 得到；`keep_recent_tokens` 控制近期仍
保留原文的预算。自动检查发生在本次 `before_run` 之前，而不是在某个 Provider 流式响应中途突然
改写上下文。

第二，`harness.compact()` 是已经暴露给 Python 的手工 API。它要求 Harness 处于 Idle，会尝试
执行一次真实压缩并返回 `tokens_before`、`tokens_after`、`compressed_entries`。手工压缩不受自动
压缩熔断器限制，但仍可能因为历史不足、没有合法切点或摘要模型失败而报错；“可以调用”并不等于
“每次都应调用”。

## 一条完整执行故事：审查支付补丁

用户给 Developer Agent 一个任务：“审查支付补丁，引用证据，不要改文件。”以下故事把一次长任务
拆回五层，而不是只展示最终 prompt 字符串。

### 1. 构建期：确定稳定部分

应用设置系统规则“先检查再行动”，安装 `read`、`grep`、测试等核心工具，并挂载三个 Skill。这个
组合一旦 build 完成，就不应为了加入当前时间或临时 TODO 而反复改写开头。Skill 的完整正文此时
还没有全部进入上下文。

### 2. run 开始：目录可见，正文尚未加载

Agent Core 看到存在可读 Skill，于是在初始用户消息之后追加 `<available-skills>` 元数据。目录只含
名称、描述和位置，并提示可以使用 `skill_read`。模型由此发现 `code-review` 与当前任务匹配。

注意：这里说“Skill 层”是概念分层。当前实现把目录作为 user message 追加到 run 的初始上下文；
其他 Harness 完全可以采用不同包装，不能把教材层名误当成跨运行时协议。

### 3. 第一次动作：按需加载操作手册

模型调用 `skill_read(skill_name="code-review")`。工具只允许在该 Skill 根目录内读取文件，并把正文
作为 ToolResult 返回。于是完整检查表进入 Trajectory，而另外两份无关 Skill 仍只有目录信息。

### 4. 多轮观察：Trajectory 增长，Status 更新

模型读取 `payment.py`、查找签名验证调用、运行聚焦测试。每次 Assistant tool call 与 ToolResult 都
按顺序进入轨迹。StatusPanel 的 `after_tool_call` 统计调用次数；下一次 Provider 请求前，
`transform_context` 生成最新 `<agent_status>`，把 TODO、环境和计数放到上下文末尾。

用户中途再次强调“不要改文件”。这条约束是新的原始证据，应该保留在 Trajectory，而不是只在
状态栏写一个 `read_only=true` 就删除用户原话。

### 5. 接近预算：自动或手工触发压缩

若应用显式启用了自动压缩，那么下一次 `run()` 入口会估算当前 live region 的 token。超过阈值且
存在合法切点时，Runtime 发出 CompactionStart，调用摘要模型，将较老记录提炼为 Goal、Progress、
Key Decisions、Next Steps 与 Critical Context，再把 compaction entry 写入 Session。

若自动压缩未启用，操作者也可以在 Harness Idle 时调用 `harness.compact()`。两条路径共用压缩
核心，但自动路径有阈值、熔断和“上下文仍放得下时可静默跳过”等控制；手工路径表达的是“现在就
尝试一次”。

### 6. 下一次请求：近期证据与摘要共同工作

下一次上下文仍保留稳定系统规则和工具定义，带上近期用户约束、最新状态栏以及旧轨迹摘要。模型
据此继续跑测试并提交审查意见。若摘要遗漏了“不修改文件”，后续行为就可能偏离任务——这正是
压缩必须有任务感知模板、测试和审计的原因。

## 源码导读

建议沿着一次真实请求从 Python 向 Runtime 追踪，而不是只看导出函数名。

1. [`pyskills.rs`](../../../src/runtime/pyskills.rs) 扫描 `SKILL.md` 并构造 Python `Skill`；
   [`pybuilder.rs`](../../../src/core/pybuilder.rs) 的 `.skills()` 把它们装进 builder。
2. Runtime [`builder.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime/src/builder.rs)
   在存在可见 Skill 时自动注册 `SkillReadTool`；
   [`loop_driver.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-agent/src/harness/loop_driver.rs)
   在 run 开始时注入目录元数据。
3. [`skills.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-agent/src/skills.rs) 展示目录 XML、正文读取、
   路径约束和 256 KiB 截断边界。
4. [`pystatuspanel.rs`](../../../src/strategy/pystatuspanel.rs) 只是 Senza 工厂；真正的能力组合在
   [`status_panel/plugin.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-strategy/src/status_panel/plugin.rs)，
   上下文末尾注入逻辑在
   [`status_panel/hook.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-strategy/src/status_panel/hook.rs)。
5. Python 的手工入口位于 [`pyharness.rs`](../../../src/core/pyharness.rs)；自动阈值、
   `before_compact` 决策、熔断和 Session 写入位于
   [`compaction_ops.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-agent/src/harness/compaction_ops.rs)。

阅读时可以特别核对三个事实：StatusPanel 同时贡献 `todo_write`、`transform_context` 和
`after_tool_call`；Skill catalog 不修改 system prompt；自动压缩默认关闭。

## 配套实验

配套材料位于 [Lab 04](../../../academy/labs/04_context_layers/README.md)。先在 Senza 仓库根目录
运行无 Provider 的 recorded 模式：

```powershell
python academy/labs/04_context_layers/demo.py
python -m pytest academy/labs/04_context_layers/test_demo.py -q
```

实验会输出四个上下文快照之间的 diff：`=` 表示该层没变，`+` 表示新增，`~` 表示内容增长或
替换。请按顺序验证：

1. 所有快照的 `stable_prefix` 完全一致；
2. 第二个快照只在命中任务后增加 Skill 正文；
3. 第三个快照出现 Status，Trajectory 继续增长；
4. 第四个快照的旧 Trajectory 变短，并出现五段结构化摘要；
5. 压缩前后稳定前缀没有被教学模型改写。

recorded 通过后，再按条件运行三个 live 入口：

```powershell
python academy/labs/04_context_layers/demo.py --mode live --live-example skills
python academy/labs/04_context_layers/demo.py --mode live --live-example status
python academy/labs/04_context_layers/demo.py --mode live --live-example compaction
```

它们分别委托
[`06_skills_model_switch.py`](../../../live-tests/examples/06_skills_model_switch.py)、
[`16_status_panel.py`](../../../live-tests/examples/16_status_panel.py)和
[`21_context_aware_compact.py`](../../../live-tests/examples/21_context_aware_compact.py)。第三个 live
示例明确展示 `.auto_compact(True)` 与 `harness.compact()` 两条路径。

## 常见误解与能力边界

### 误解 1：五层对应五种固定 message role

不对应。五层是帮助设计和排错的概念模型。当前 Skill catalog 和 Status 使用 user message 追加，
但这是实现选择，不应写进跨运行时业务协议。

### 误解 2：稳定前缀就一定命中 Prompt Cache

稳定前缀为缓存创造条件，但是否命中还取决于 Provider、模型、请求字节序列和服务端策略。
recorded diff 只能证明教学快照没变，不能证明缓存命中或延迟改善。

### 误解 3：安装 Skill 就等于已经执行了能力

安装只让目录可发现并提供读取入口。模型是否选择 `skill_read`、是否正确遵循正文，仍需从工具事件
和结果验证。Skill 也不会自动增加文件系统或网络权限。

### 误解 4：状态栏可以替代原始轨迹

状态栏只保存被 collector 选择的投影，且模型通常会高度信任它。计数器或 TODO 一旦维护错误，反而
会稳定地误导模型。涉及事实、来源和审计时必须保留原始证据。

### 误解 5：自动压缩默认开启，或会在任意时刻发生

当前默认关闭，需显式 `.auto_compact(True)`。检查发生在新 run 入口、安全的上下文构造边界；不会
在正在生成的 Provider 响应中途改写消息。

### 误解 6：手工压缩比自动压缩“更可靠”

两者都会调用摘要模型，都是有损的。手工 API 只是绕过自动阈值与熔断，不能保证摘要质量，也不能
替代项目文档、持久化状态或外部证据。

## 本章小结

上下文工程的核心不是堆更多文字，而是管理信息的生命周期。稳定规则和工具尽量保持不动；Skill
正文按需加载；Status 把常用状态提前算好；Trajectory 保存实际发生的证据；Compaction 在明确的
边界把旧轨迹换成高密度但有损的表示。Senza 把这些职责分散到 builder、Tool、Hook、Plugin、
Session 和摘要模型中，因此每一层都可以独立验证和演进。

## 复习题

1. 为什么“当前时间”不适合每轮改写到 system prompt 开头？它更适合放在哪一层？
2. `load_skills()`、`.skills()` 与 `skill_read` 分别发生在什么阶段？
3. StatusPanel 为什么既需要 `after_tool_call`，又需要 `transform_context`？
4. 某次摘要保留了“测试已运行”，却丢掉“测试失败”。这是长度问题还是语义完整性问题？
5. 自动压缩默认是否开启？它在一次 run 的哪个位置检查？
6. `harness.compact()` 绕过熔断器意味着什么，又不意味着什么？
7. 如果任务要求“绝不能修改文件”，你会把这条约束同时保存在哪些位置？为什么？

## 延伸阅读

- 理论：[《动手学 AI Agent》第 2 章：上下文工程](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter2.md)
- 实验：[Lab 04 README](../../../academy/labs/04_context_layers/README.md)与
  [`expected_trace.json`](../../../academy/labs/04_context_layers/expected_trace.json)
- 真实 API：[Senza context-aware compaction 示例](../../../live-tests/examples/21_context_aware_compact.py)
- 源码地图：[Runtime/Senza 源码地图](appendix-source-map.md)
- 下一章：[Coding Agent 与确定性 Guardrail](05-coding-guardrails.md)
