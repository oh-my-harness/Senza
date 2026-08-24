# 第 8 章：受限多 Agent——隔离、通信与生命周期

> 本章成熟度：`teaching`。Runtime 的 spawn 协议和工具类型真实存在；本章 recorded 状态机属于
> Academy，当前 Senza Python child 也不是带专业工具与 profile 的“数字团队”。

## 本章回答的问题

“多开几个 Agent”不会自动提高结果质量。它同时引入上下文隔离、消息投递、并发成本、终止传播
和结果合并等新问题。本章聚焦当前 Senza 可以准确解释的一种形态：主 Agent 作为 Manager，把
独立纯推理任务交给子 Agent，再通过受控工具管理其生命周期。

我们将回答：

1. 什么任务值得 spawn，什么任务留在单 Agent 更好；
2. 隔离上下文时，Main 与 child 怎样显式交换信息；
3. Runtime 定义的 7 个协议工具与 Senza 当前自动挂载的工具有什么差别；
4. `role`、`description`、NoopPlugin 和取消操作各自真正改变了什么。

## 学习目标与先修知识

学完本章，你应当能够：

- 用“新信息、隔离价值、并行收益、通信成本”判断是否拆分子任务；
- 区分 Main 的任务上下文、child 的独立轨迹和显式移交包；
- 正确列出主侧 5 个管理工具与底层 child-side 2 个通信工具；
- 解释为什么当前 Senza child 的 `NoopPlugin` 不等于一个 Coding/Research profile；
- 为 spawn 场景设计 done、aborted、timeout 和未知 Agent 等终态处理。

先修内容是第 1 章的 Agent Core/Tool Calling 和第 3 章的 Plugin 构建期装配。理论背景见本地
[《动手学 AI Agent》第 10 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter10.md)。

## 理论直觉：把多 Agent 当作受控的并发进程

书中用两个维度描述多 Agent：上下文共享还是隔离，以及控制拓扑是对等、Manager 还是去中心化。
Senza 当前 spawn 最适合用“**隔离上下文 + Manager 拓扑**”理解：Main 创建 child，传入 prompt
和显式 context，通过消息总线查询、补充指令、等待或取消，最后只接收明确返回的结果。

这个模型与操作系统进程很像：

| 进程概念 | 本章中的 Agent 概念 |
| --- | --- |
| 创建进程 | `spawn_agent` |
| 私有地址空间 | child 独立上下文与轨迹 |
| IPC | prompt/context、定向消息、完成事件 |
| `ps` | `query_subagent` |
| `wait` | `await_subagent_reply` |
| 取消信号 | `abort_subagent` |

类比只用于理解控制面。上下文隔离并不自动提供文件系统、凭证或操作系统级权限隔离；这些仍要由
执行环境和安全策略单独保证。

### 什么时候值得拆分

多 Agent 的收益通常来自至少一项：

- 子任务可以并行，且结果之间依赖很少；
- 子任务需要独立上下文，避免主轨迹被大量试错细节污染；
- 不同子任务能访问新的环境证据，例如测试结果、代码区域或不同信息源；
- 需要故障隔离，某一分支失败不应破坏另一分支的状态。

若多个 child 只读同一段文本、使用同一模型重复猜测，系统往往只是增加 token 和协调成本。
因此“能 spawn”不是“应 spawn”。Manager 还必须为子任务定义完成条件、输入边界和停止策略。

### 控制面与数据面

spawn 工具、状态、消息和取消构成控制面；文档、代码、测试产物等真实工作结果构成数据面。本章
只证明控制面状态和显式 context 隔离，没有证明共享文件系统的并发一致性，也没有为 child 配置
专业工具权限。

## Runtime/Senza 架构映射

Runtime 的协议一共定义 7 个 LLM 可见工具，但它们分属两侧：

| 一侧 | 工具 | 语义 |
| --- | --- | --- |
| Main | `spawn_agent` | 异步创建 child，立即返回 `agent_id` |
| Main | `message_subagent` | 向运行中的 child 发消息，不等待回复 |
| Main | `await_subagent_reply` | 等待消息或完成事件 |
| Main | `query_subagent` | 非阻塞查询 running/done/aborted |
| Main | `abort_subagent` | 向运行中的 child 发取消信号 |
| Child protocol | `message_main` | child 向 Main 报告中间消息 |
| Child protocol | `await_main_message` | child 等待 Main 的后续消息 |

当前 Senza Python 的实际装配要再收窄一层：

```text
HarnessBuilder.enable_spawn(...)
        │
        ├─ Main harness：自动挂载 5 个管理工具
        ├─ MessageBus + SpawnPlugin：投递事件并唤醒 Main
        └─ child factory：返回 NoopPlugin
                         ├─ 不贡献递归 spawn 工具
                         └─ 不自动贡献 2 个 child-side 通信工具
```

也就是说，底层 Runtime 有“主侧 5 + 子侧 2”的完整类型定义，但 Senza 的默认 Python child 并
没有那两个 child-side 工具。`NoopPlugin` 还阻止通过同一路径递归创建孙 Agent。Python
`enable_spawn()` 当前只配置 model、provider 和 session directory，没有 child profile、专属 tools
或专属 plugin 的公开入口。

`role` 和 `description` 会被清理、截断并保存在状态元数据中，方便查询和展示；它们不会改变 child
的 system prompt、工具集、权限或控制流。角色标签不是能力配置。

## 一条完整执行故事

Main 要比较 canary release 与 blue-green release。它保留一条私有备注：“领导倾向方案 B”，
但希望两个分析分支先独立给出技术判断。

1. Main 用 `spawn_agent` 创建 `sub-1`，只传入 canary prompt 和“最小化用户可见故障”标准。
2. Main 创建 `sub-2`，只传入 blue-green prompt 和“最小化回滚时间”标准。
3. 两个 child 状态都是 `running`；它们看不到 Main 的私有备注，也看不到彼此的 prompt。
4. Main 用 `query_subagent` 做非阻塞检查，再用 `message_subagent` 只给 `sub-1` 增加“给出可测
   回滚信号”的要求。`sub-2` 的 inbox 不发生变化。
5. `sub-1` 产生明确结果，状态从 `running` 变为 `done`。Main 用
   `await_subagent_reply` 收取结果，而不是复制 child 的私有轨迹。
6. `sub-2` 仍在运行，但其分支已不再需要。Main 查询确认后调用 `abort_subagent`；终态变为
   `aborted`，返回值没有伪造一个分析结果。
7. Main 只把 `sub-1` 的显式结果合入自己的上下文，再结合用户目标完成综合判断。

这条故事覆盖了主侧 5 个工具，却仍是 Academy 的确定性状态模型。它证明消息定向、上下文视图和
状态转换可以测试，不证明真实 Provider 同时运行、取消信号传播速度或模型一定遵守任务边界。

## 源码导读

1. [Runtime spawn tools](https://github.com/oh-my-harness/llm-harness-runtime/blob/03aed0ce550aa0c95cb26d9667f6440bc3dd3349/crates/llm-harness-subagents/src/tools.rs)：文件开头
   直接列出 7 个工具；继续查看每个 schema、并行/顺序执行模式和 timeout/abort 行为。
2. [Senza `wire_spawn`](../../../src/runtime/pyspawn.rs)：对照模块注释中的装配步骤，找到 Main 的
   5 次 `.tool(...)` 注册和 child factory 返回 `NoopPlugin` 的位置。
3. [Academy 状态模型](../../../academy/labs/08_basic_multi_agent/state_model.py)：
   `MAIN_SIDE_TOOLS`、`RUNTIME_CHILD_SIDE_TOOLS` 和 `SENZA_DEFAULT_CHILD_TOOLS` 把三层口径分开；
   `CoordinatorModel` 则固定 running/done/aborted 转换。
4. [Lab 08 tests](../../../academy/labs/08_basic_multi_agent/test_demo.py)：测试不仅检查终态，还验证
   Main 私有上下文未泄漏、消息只进入目标 inbox，以及 role 不驱动状态转换。
5. [真实 spawn 示例](../../../live-tests/examples/11_spawn_subagent.py)：用于核对当前 Senza API 和
   Provider 路径。该示例实际调用 spawn、await、query；message 与 abort 虽已挂载，但示例未调用。

阅读时要区分“某工具类型在 Runtime 文件里存在”“某工具被某个 Harness 注册”“某个 live 场景
实际调用过该工具”三个层级。本章关于 child-side 两个工具的限制正来自这种区分。

## 配套实验

实验说明见 [Lab 08 README](../../../academy/labs/08_basic_multi_agent/README.md)。在 Senza 根目录运行：

```powershell
# 无 Provider：运行确定性 Manager 状态模型
python academy/labs/08_basic_multi_agent/demo.py

# 委托真实 Senza spawn 示例
python academy/labs/08_basic_multi_agent/demo.py --mode live

python -m pytest academy/labs/08_basic_multi_agent/test_demo.py -q
```

运行 recorded 模式后，按事件序号完成以下检查：

1. 找出 `sub-1` 和 `sub-2` 各自唯一可见的 context；
2. 标出哪一条消息只到达 `sub-1`；
3. 找出 `done` 与 `aborted` 两个终态，并解释为什么 aborted 没有 result；
4. 列出 5 个主侧 lifecycle 工具，再说明底层两个 child-side 工具为何没有出现在 Senza 默认 child。

进一步可以在状态模型中新增第三个 child 和 timeout 分支，但不要把新增教学行为写成 Runtime 已有
语义；若要验证真实调度，必须新增 live/integration 测试。

## 常见误解与能力边界

### “Runtime 有 7 个工具，所以 Python child 默认也有 7 个”

错误。7 是两侧协议总数。Senza 当前给 Main 自动挂载 5 个；child factory 使用 `NoopPlugin`，
默认不贡献 `message_main`、`await_main_message`，也不贡献递归 spawn。

### “给 role 写 `code-reviewer`，child 就有代码审查能力”

错误。role/description 只是查询和展示元数据。当前 Python spawn schema 没有 child profile、专属
system prompt、专属 tool 或权限配置入口。

### “上下文隔离等于安全隔离”

错误。child 不继承 Main 的对话轨迹，不代表它拥有独立文件系统、凭证、网络或 OS 沙箱。数据面
隔离必须由工作目录、权限、容器或专门执行后端保证。

### “并行两次就一定比一个 Agent 更可靠”

错误。同质模型在相同信息上可能产生同源错误。只有独立证据、真正可并行的搜索空间、故障隔离
或上下文节省足以覆盖额外成本时，多 Agent 才有明确价值。

### “abort 是瞬时强杀，调用返回就没有任何资源”

错误。工具发送取消信号，真实传播延迟、Provider 可取消性和资源清理需要集成测试。本章 recorded
模型只验证状态从 running 到 aborted。

完整口径见 [Academy 能力边界](../capability-boundaries.md)。

## 小结

当前 Senza spawn 是一个受限的 Manager 控制面：Main 有 5 个管理工具，Runtime 另定义 2 个
child-side 协议工具，但 Senza 默认 child 的 `NoopPlugin` 不会自动挂载它们。上下文通过 prompt、
显式 context、定向消息和完成事件传递；role 只是元数据。多 Agent 的设计重点不是角色名称，而是
隔离边界、通信协议、生命周期、预算和可验证的新信息。

## 复习题

1. 为什么“隔离上下文 + Manager”适合描述当前 Senza spawn？
2. 请按方向列出 Runtime 的 7 个工具，并指出 Senza 当前自动挂载哪 5 个。
3. `message_subagent` 与 `await_subagent_reply` 的阻塞语义有什么不同？
4. `NoopPlugin` 当前带来哪两项直接限制？
5. 为什么 role/description 不能当作 profile 或权限配置？
6. 给出一个适合 spawn 的 Developer Agent 子任务，以及一个不适合拆分的任务，并解释成本判断。
7. 要把本章从 teaching 升级为“专业 child 团队”，至少需要哪些 Python API 和端到端测试？

## 延伸阅读

- [《动手学 AI Agent》第 10 章：多 Agent 系统](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter10.md)
- [Lab 08：Basic Multi-Agent](../../../academy/labs/08_basic_multi_agent/README.md)
- [Runtime spawn 工具实现](https://github.com/oh-my-harness/llm-harness-runtime/blob/03aed0ce550aa0c95cb26d9667f6440bc3dd3349/crates/llm-harness-subagents/src/tools.rs)
- [Senza spawn live example](../../../live-tests/examples/11_spawn_subagent.py)
- [Lab 06：Workflow、恢复与 HITL](../../../academy/labs/06_workflow_recovery_hitl/README.md)
