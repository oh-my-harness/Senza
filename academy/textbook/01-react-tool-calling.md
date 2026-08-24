# 第 1 章：ReAct 与 Tool Calling——让模型真正作用于环境

> 成熟度：**stable**。本章描述的 Tool 注册、Agent Core 循环和工具结果回流均有当前
> API、源码与测试支撑；recorded 实验只用于稳定展示因果链，真实 Provider 决策由 live
> example 验证。

## 本章回答的问题

一个聊天模型可以告诉你“应该读取配置文件”，但 Developer Agent 必须真的读取文件，并根据
读取结果继续工作。文字建议是怎样变成结构化行动的？行动结果又怎样回到模型眼前？在这条链路
中，Model、Agent Core、Tool callback 和 Environment 各自负责什么？

本章从最小闭环入手。读完后，你应该能分清三件经常被混在一起的事：模型**提出 Tool Call**、
Harness **分派并执行 Tool**、Environment **返回 Observation**。只有三者闭合，系统才是
Agent，而不只是带函数说明的聊天接口。

## 学习目标与先修知识

完成本章后，你应当能够：

1. 用 Model—Harness—Environment 三层关系解释 ReAct；
2. 说明 Tool definition、Tool Call、callback 和 Tool Result 的区别；
3. 沿源码找到 Senza Python Tool 如何进入 Runtime Agent Core；
4. 从事件轨迹判断一次工具调用是否真正形成了闭环；
5. 区分 recorded 教学证据与 live 端到端证据。

先修知识仅包括 Python 函数、JSON 对象和基本命令行操作。建议先读
[序言](00-preface.md)，了解本教材的四层架构与证据等级。

## 理论直觉：Agent 不是“会输出函数名的模型”

[《动手学 AI Agent》第 1 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)用
“LLM + 上下文 + 工具”描述最小 Agent，并用“思考—行动—观察”解释 ReAct。工程上更有用的
理解是：模型负责在当前观察下选择下一步，Harness 负责把选择变成受控执行，Environment 才是
真实状态所在之处。

```text
       当前上下文                         结构化行动
Environment ── observation ──> Harness ──────────> Model
     ^                              <──────────
     │                                  decision
     └──────── Tool callback ────────────┘
                 读取或改变真实状态
```

例如，模型输出“默认模型大概是 gpt-5.6”只是生成文本；输出
`inspect_file({"path": "agent.toml"})` 是提出行动；callback 真正读取文件才改变了系统掌握的
事实；读取结果作为 Tool Result 进入下一轮上下文，模型才有证据给出最终回答。

这里有两个边界需要先钉牢：

- **Tool 是 Agent 与 Environment 的接口，不是 Environment 本身。** 文件内容、数据库行、
  进程和网页状态属于 Environment；Tool 的名称、参数协议、适配器和调用治理属于 Harness。
- **模型拥有决策权，不拥有执行权。** 模型可以提出任意字符串，但只有命中已注册 Tool、参数
  可解析且通过 Harness 边界的请求才会执行。

因此，ReAct 的价值不在于把三个英文单词排成循环，而在于每一轮都使用了上一轮的真实观察。
如果工具结果没有回到轨迹，模型只能猜测行动是否成功，循环便从闭环退化为开环。

## Runtime/Senza 架构映射

同一条链路在项目中分为四层：

| 层 | 主要对象 | 本章职责 |
| --- | --- | --- |
| 应用层 | Developer Agent、业务 prompt | 定义任务与完成条件 |
| Senza Python 装配面 | `create_tool()`、`HarnessBuilder.tool()`、`prompt_and_collect()` | 声明 Tool 并构建可运行 Harness |
| Runtime | `HarnessBuilder`、`AgentHarness`、`agent_loop` | 维护 run/turn、调用 Provider、分派 Tool、保存轨迹并收敛 |
| Environment | 文件、数据库、API、系统进程 | 产生真实状态变化和观察 |

### 一次 run 与多个 turn

用户的一次 `prompt()` 构成一个 **run**。run 内部可以经历多个 **turn**：一次 Provider
响应如果包含 Tool Call，Core 执行工具、追加 Tool Result，然后进入下一个 turn；如果模型给出
最终回答并满足停止边界，run 才结束。不要把“一次用户请求”“一次模型调用”和“一次工具调用”
都叫作一轮，它们的生命周期并不相同。

### Tool 的四个面

Senza 中一个 Tool 至少有四个面向：

1. `name`：模型和 Core 用来匹配动作的稳定标识；
2. `description`：告诉模型何时使用该动作；
3. `parameters_schema`：约束结构化参数的形状；
4. `callback(args, ctx)`：把调用连接到真实 Environment，并返回结构化结果。

前三项构成模型可见的动作说明，第四项处于执行边界。改好 description 可能提升模型选对工具的
概率，却不会替代 callback；写了 callback 但没有把 Tool 注册给 Builder，模型也看不到它。

## 一条完整执行故事：查询天气与时间

下面沿用权威 live example 的任务：“东京天气如何，UTC 现在几点？”这条故事描述机制，具体
模型可能选择串行调用、并行调用或不调用某个工具，因此不要把某一种输出顺序写成业务保证。

### 1. 构建动作空间

应用用 `create_tool()` 分别声明 `get_weather` 和 `get_time`。每个 Tool 带有 JSON Schema 和
Python callback，再通过 `HarnessBuilder.tool()` 注册。Builder 构造完成后，当前 Harness 的
动作空间才包含这两个名字。

### 2. Core 构造 Provider 请求

用户消息进入 run。Agent Core 从 Session 构造消息轨迹，把 system prompt、消息和当前 Tool
definitions 转成 Provider 请求。Tool definition 此时只是“可选动作菜单”，没有 callback 被
执行。

### 3. Model 提出结构化 Tool Call

模型根据上下文决定是否行动。若它返回 `get_weather({"city": "Tokyo"})` 与
`get_time({"timezone": "UTC"})`，这仍然只是 Assistant Message 中的 ToolUse 数据。Core 会按
Tool 名查找注册表；未知 Tool 不会被当作任意 Python 函数执行。

### 4. Core 分派，callback 访问 Environment

Runtime 为匹配到的调用生成 `ToolContext`，发出 `ToolExecutionStart`，再执行 callback。示例
callback 返回天气和时间文本；真实应用可以在此访问 API、文件或数据库。独立调用在默认配置下
可以并行执行，所以业务逻辑不应依赖两个 callback 的偶然先后顺序。

### 5. Tool Result 成为 Observation

Core 为每个 ToolUse id 配对一个 Tool Result，并发出 `ToolExecutionEnd`。结果被转换成模型消息
加入上下文，也被转换成 Session 消息进入待写队列。这个配对很关键：如果某个 ToolUse 没有结果，
Runtime 会补合成错误结果以保持轨迹完整，避免下一次 Provider 请求携带孤立调用。

### 6. Model 基于观察继续决策

下一次 Provider 调用能看到刚才的结果。模型可以补充调用，也可以生成最终文本。最终文本不是
callback 的返回值原样“透传”，而是模型基于 Observation 形成的新决策。

### 7. Core 收敛 run

候选答案通过最终答案边界后，Core 结束 turn、刷新 Session 写入并发出 settled。若 Provider、
Hook 或工具链发生不可恢复错误，则走错误边界；“打印了一段看起来完整的文本”不等于 run 已经
成功收敛。

把整条链压缩成一句话就是：

```text
User → Context → Model ToolUse → Core dispatch → callback → Tool Result
     → Context → Model final answer → validation/stop → settled
```

## 源码导读：沿一条 Tool Call 追进去

阅读源码时建议按“Python 声明 → Rust 适配 → Core 循环 → Harness 事件”顺序，而不是从巨大
事件枚举开始搜索。

### 入口一：Senza 创建 Tool

[`Senza/src/lib.rs`](../../src/lib.rs) 中的 `create_tool()` 接收 dict 或 JSON 字符串形式的
Schema，构造 `PyTool` 并返回 Python 可持有的包装对象。`create_sync_tool()` 当前只是同一入口
的显式别名；`create_tool()` 会识别同步和异步 callback。

[`Senza/src/core/pytool.rs`](../../src/core/pytool.rs) 实现 Runtime 的 `Tool` trait。重点看三
件事：

- `name()`、`description()`、`parameters_schema()`提供模型可见定义；
- `execute()`把 JSON 参数和 `ToolContext`交给 Python callback；
- `parse_tool_result()`把 Python 字符串或 dict 解析为 Runtime `ToolResult`。

`ToolContext` 还暴露取消状态和部分结果更新，但它没有把 Runtime 内部任意状态都开放给 Python。
这是稳定接口边界，而不是能力缺失的临时绕行。

### 入口二：Senza 把 Tool 装进 Builder

[`Senza/src/core/pybuilder.rs`](../../src/core/pybuilder.rs) 的 `.tool()` 将 Python 包装中的 Tool
指针追加到 Runtime `HarnessBuilder`。`.build()` 再解析 Provider、Environment、Session 等依赖，
返回真正的 `AgentHarness`。默认 Environment 是 `UnsupportedEnv`；需要文件或 Shell 的 Tool
必须显式提供相应执行环境，callback 自己访问外部服务时也要自行持有其客户端与凭证。

### 入口三：Runtime 维护循环

`agent_loop()` 是 Model/Tool 控制循环。可以重点跟踪：

1. 当前消息和 Tool definitions 被构造成 Provider 请求；
2. Assistant Message 中的 ToolUse 按名称匹配已注册 Tool；
3. Core 批量执行工具并为每个调用生成结束事件；
4. Tool Result 追加到 `ctx.messages` 后进入下一 turn；
5. 无 Tool Call 或命中最终答案边界时停止。

Agent Core 还消费底层事件，维护 `pending_tool_calls`、Session 待写消息、SavePoint 和最终 settled/error
状态。这种分层说明 Agent Core 不只是一个 `while`：它还负责可观察状态、持久轨迹边界和失败清理。

## 配套实验

实验位于 [`academy/labs/01_react_tool_calling`](../../academy/labs/01_react_tool_calling/)。
请在 Senza 仓库根目录执行。

### 第一步：运行 recorded 轨迹

```powershell
python academy/labs/01_react_tool_calling/demo.py
```

逐行回答以下问题：哪一项是模型提出调用？哪一项是 Core 分派？哪一项才是 Tool Result？如果删除
第四项 Observation，第五项回答还是否有工程证据？

recorded 模式不会导入 Senza、调用 Provider 或执行真实 callback。它的作用是把因果顺序固定下来，
便于代码审查和离线教学。

### 第二步：阅读断言

```powershell
python -m pytest academy/labs/01_react_tool_calling/test_demo.py -q
```

测试检查 `user → model → tool → tool → model → agent` 的结构、Tool Call 与 Tool Result 的区别，
以及最终 settled 事件。测试通过说明教学轨迹没有漂移，不等价于在线链路可用。

### 第三步：有条件运行 live example

```powershell
python academy/labs/01_react_tool_calling/demo.py --mode live
```

该命令委托
[`live-tests/examples/02_tool_calling.py`](../../live-tests/examples/02_tool_calling.py)，使用当前
Senza API 和真实 Provider。观察 `Tools called` 与 `Callbacks fired`：前者证明模型输出了 Tool
Call，后者证明 Python callback 实际执行。二者都出现，才构成这部分端到端证据。

### 第四步：做一个最小改造

不要复制整套 demo。可以在 live example 的副本中临时修改 Tool description，例如明确要求城市
采用英文名，然后比较模型选择和 callback 参数。再把 callback 改为返回结构化 `details`，观察
最终自然语言是否变化。这个练习用来区分“模型可见动作说明”和“环境执行结果”。

## 常见误解与能力边界

### 误解一：模型调用了 Python 函数

模型只生成结构化 ToolUse。名称匹配、参数传递、callback 调度和错误转换由 Harness 完成。把这
几层合成一句“模型执行函数”，会让权限与错误归属变得无法审查。

### 误解二：Schema 能保证业务安全

Schema 主要规定参数形状。它不能证明用户有权限读取文件，也不能判断一条 SQL 是否应被执行。
安全策略需要放在 Tool 实现、Hook、沙箱和后端权限等更强边界上；第 2、3 章会继续补全。

### 误解三：Tool Result 等于最终答案

Tool Result 是给模型的 Observation，最终答案是模型看过 Observation 后的输出。某些 Tool 可以
设置终止标记，Runtime 也支持显式最终答案机制，但不能把普通 callback 返回值一概称为最终回答。

### 误解四：一次成功调用证明 Agent 可靠

一次 live 调用只能证明当前配置下发生过一条成功路径。它不证明模型总会选对工具、长链稳定、
错误可恢复或高风险动作安全。可靠性需要重复评测、失败路径和环境级验证，本教材后续章节展开。

### 能力边界

- 本章 recorded trace 是审阅过的机制叙事，不证明真实 Provider 或 callback；
- live example 的 Tool 选择由模型决定，调用数量和顺序不构成固定 API 契约；
- `create_tool()`建立 Python callback 适配，但外部 SDK、凭证、数据库和操作系统能力不会凭空出现；
- Tool 只能访问 callback 或 `ExecutionEnv`明确提供的环境，Agent Core 不自动拥有宿主机全部权限；
- 本章只覆盖最小 ReAct 闭环，不宣称规划、恢复、记忆或多 Agent 已由此自动获得。

## 小结

ReAct 在工程中的核心不是“模型会思考”，而是行动结果能够以结构化 Observation 回到下一次决策。
Senza 负责用 Python 声明并装配 Tool，Runtime Agent Core 负责稳定执行 run/turn/model/tool 循环，
callback 连接真实 Environment。理解这条边界，后续才能把安全、上下文和验证放到正确位置。

## 复习题

1. Tool definition、Tool Call、Tool callback、Tool Result 分别由谁产生，面向谁？
2. 为什么“callback 已执行”仍不足以证明 ReAct 闭环成立？
3. 一个模型编造了未注册的 `delete_repository` Tool。Runtime 应在哪一层处理，为什么？
4. 如果工具结果只打印到终端而不进入下一轮上下文，Agent 可能出现什么行为？
5. `prompt()`、Provider 调用、turn、Tool Call 四者是一一对应的吗？请画出一个包含两个工具调用的
   可能时序。
6. 设计一个读取构建状态的 Tool：哪些字段属于 Schema，哪些检查应留在执行或安全边界？

## 延伸阅读

- 理论坐标：[《动手学 AI Agent》第 1 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)中的工具调用、
  ReAct 循环与 Model—Harness—Environment 边界；
- 权威实验说明：[`Lab 01 README`](../../academy/labs/01_react_tool_calling/README.md)；
- Python 端到端示例：[`02_tool_calling.py`](../../live-tests/examples/02_tool_calling.py)；
- Senza Tool 适配：[`pytool.rs`](../../src/core/pytool.rs)。
