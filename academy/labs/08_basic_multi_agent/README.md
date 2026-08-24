# 08 · Basic Multi-Agent：隔离上下文与受控生命周期

这一课不搭建一个虚构的“AI 软件公司”，而是先回答更基础的问题：什么时候把任务交给
另一个 Agent，以及主 Agent 如何可靠地创建、通信、等待、查询和取消它？

《动手学 AI Agent》[第 10 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter10.md)用两个维度分析
多 Agent：上下文共享还是隔离，以及协作采用哪种拓扑。本课对应其中的
**隔离上下文 + Manager 拓扑**：每个子 Agent 有独立轨迹，主 Agent 只显式传入任务包，
再通过 MessageBus 的控制面收取结果和管理生命周期。

## Recorded 场景

默认 demo 运行一个纯 Python、完全确定性的状态模型：

1. Main 创建两个互不依赖的纯推理任务；
2. 两个子任务只收到各自的 prompt 与显式 context，不继承 Main 的私有上下文；
3. Main 查询二者状态，并只给第一个子任务补充一条消息；
4. 第一个子任务完成，Main 用 await 收取结果；
5. 第二个子任务仍在运行，Main 查询后将其取消，再收取 aborted 事件；
6. Main 只把明确返回的结果合入自己的上下文，不读取任何子 Agent 的私有轨迹。

状态模型不是 LLM 模拟器。它只让 `running → done` 与 `running → aborted`、消息定向和
上下文隔离变得可测试。

## 工具与装配面的准确边界

Runtime 的 spawn 协议定义了两侧共 7 个内建工具：

| 一侧 | 工具 | 用途 |
| --- | --- | --- |
| Main | `spawn_agent` | 异步创建子 Agent，立即返回 ID |
| Main | `message_subagent` | 给运行中的子 Agent 发消息，不等待 |
| Main | `await_subagent_reply` | 等待消息或完成事件 |
| Main | `query_subagent` | 非阻塞查询 running/done/aborted |
| Main | `abort_subagent` | 请求取消运行中的子 Agent |
| Child protocol | `message_main` | 子 Agent 向 Main 报告中间消息 |
| Child protocol | `await_main_message` | 子 Agent 等待 Main 的后续消息 |

这里必须区分“Runtime 定义了什么”和“当前 Senza Python 自动挂载了什么”：

- `HarnessBuilder.enable_spawn()` 当前只把 5 个 Main 工具挂到主 Harness；
- Senza 的 child plugin factory 返回 `NoopPlugin`，子 Harness 因此没有
  `spawn_agent`，不能递归创建孙 Agent；
- 同一个 `NoopPlugin` 也不会自动贡献 Runtime 的两个 child-side 通信工具；这两个工具
  是底层可装配协议，不应宣传为当前 Python child 的默认工具；
- Python `enable_spawn()` 只接受 model、provider、session directory，没有 child
  profile、专属 tool 或专属 plugin 的配置入口；
- spawn 参数里的 `role` / `description` 只用于查询和展示的元数据，不会改变 system
  prompt、工具集、权限或行为控制流。

源码依据：

- [Senza `wire_spawn`](../../../src/runtime/pyspawn.rs)
- [Runtime spawn tools](https://github.com/oh-my-harness/llm-harness-runtime/blob/03aed0ce550aa0c95cb26d9667f6440bc3dd3349/crates/llm-harness-subagents/src/tools.rs)
- [Runtime role 元数据](https://github.com/oh-my-harness/llm-harness-runtime/blob/03aed0ce550aa0c95cb26d9667f6440bc3dd3349/crates/llm-harness-subagents/src/message_bus.rs)

## 运行

在 Senza 仓库根目录执行：

```powershell
# 默认：确定性状态模型，无需安装 Senza 或配置 Provider
python academy/labs/08_basic_multi_agent/demo.py

# 在线：委托权威 spawn 示例
python academy/labs/08_basic_multi_agent/demo.py --mode live

# 本课离线验收
python -m pytest academy/labs/08_basic_multi_agent/test_demo.py -q
```

live 模式直接运行
[`live-tests/examples/11_spawn_subagent.py`](../../../live-tests/examples/11_spawn_subagent.py)。
该示例实际调用 spawn、await 和 query；message 与 abort 由同一 `enable_spawn()` 挂载，
但当前 live 场景没有实际调用它们。

## 能力边界

- 本课成熟度为 `teaching`：状态模型属于 Academy，不是 Runtime 内建模拟器；
- recorded 轨迹不证明真实 Provider 并发、调度公平性、token 成本或取消传播延迟；
- 两个子任务都是同一模型基础上的纯推理隔离任务，不能称为拥有专业权限和工具的
  Coding/Research 团队；
- 多 Agent 只有在隔离、并行或新信息足以抵偿通信和 token 成本时才值得使用；
- role 标签不是 profile，隔离上下文也不等于隔离文件系统、凭证或操作系统权限。
