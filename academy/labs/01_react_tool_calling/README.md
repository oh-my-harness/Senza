# 01 · ReAct 与 Tool Calling

这一课回答一个最小但关键的问题：模型怎样从“给建议”变成“对环境采取行动”？

《动手学 AI Agent》在[第 1 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)先给出
`Agent = LLM + 上下文 + 工具`，随后在“工具调用”和“ReAct 循环”两节说明闭环：
模型选择行动，Harness 校验并执行工具，工具结果作为新的观察进入轨迹，模型再据此决定
下一步。Runtime 的 Agent Core 正是这条循环的稳定执行者；Senza 负责用 Python 注册
Tool、构建 Harness 并消费事件。

## 你会看到什么

默认 recorded trace 固定展示以下因果链：

```text
User request
    → Model chooses a structured tool call
    → Agent Core dispatches the Tool
    → Tool result becomes an observation
    → Model answers from that observation
    → Agent Core validates and settles the run
```

重点不是“模型会调用函数”这一个 API，而是职责边界：Model 选择下一步；Tool callback
读取或改变 Environment；Agent Core 维护轨迹、执行与收敛。工具结果必须回到上下文，
否则模型看不到行动结果，ReAct 就失去 Observation 环节。

## 运行

在 Senza 仓库根目录执行：

```powershell
# 默认：无模型、无密钥的审阅轨迹
python academy/labs/01_react_tool_calling/demo.py

# 在线：委托权威示例，不复制另一套 Tool 实现
python academy/labs/01_react_tool_calling/demo.py --mode live

# 本课离线验收
python -m pytest academy/labs/01_react_tool_calling/test_demo.py -q
```

在线模式直接运行
[`live-tests/examples/02_tool_calling.py`](../../../live-tests/examples/02_tool_calling.py)，
由真实 Provider 决定是否调用 `get_weather` / `get_time`，并执行当前 Senza Tool callback。

## 观察点

1. Tool definition 属于模型每轮可见的动作接口，callback 属于 Harness 与 Environment 的
   执行边界。
2. Tool call 和 Tool result 是两件事：前者是模型提出的结构化行动，后者是环境观察。
3. 最终文本不是工具执行本身；它是模型看过 observation 后的新一轮输出。
4. `settled` 是 Core 对一次 run 的收敛状态，不应由演示脚本凭空宣告。

## 能力边界

- recorded 模式是经审阅的教学轨迹，不会调用模型，也不证明 Provider 或 callback 可用；
- live 模式才证明当前 Senza API、真实模型决策与 Tool callback 的端到端链路；
- 能调用工具不等于工具天然安全。权限、参数校验、审批和结果验证由后续 Hook/Plugin
  课程补上；
- 本课只演示一次工具往返，不以此宣称长任务规划、自动恢复或持续可靠性。
