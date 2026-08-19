# Lab 05：Coding Agent 与确定性 Guardrail

## 要回答的问题

为什么“模型说已经修好”不算完成？因为 Coding Agent 的闭环必须包含可观察环境、最小
动作和独立验证。书中第 5 章把读取、搜索、编辑、执行与测试组织为 Coding Agent 的基本
动作空间；第 1 章进一步强调 Harness 负责验证与纠正。

理论来源：[`ai-agent-book/book/chapter5.md`](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter5.md)、
[`chapter1.md`](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)。

## 对应到 Senza

- `FsToolsPlugin` 提供 read/write/edit/bash/grep/glob；
- Agent Core 把工具结果作为下一轮 observation；
- `before_tool_call`、Rules 与 SafetyDefaults 在动作生效前做确定性判断；
- 测试工具提供外部证据，最终答案不能替代测试结果。

recorded 模式会把一个带单行 bug 的 fixture 复制到临时目录，先看到测试失败，再做一行
修改并看到测试通过。同时它只判断、不执行 `rm -rf /`，证明 deny 发生在执行前。这个
场景不调用模型，因此只证明闭环和边界，不证明模型能够自主定位任意 bug。

```powershell
python academy/labs/05_coding_guardrails/demo.py
python academy/labs/05_coding_guardrails/demo.py --mode live --live-example fs
python academy/labs/05_coding_guardrails/demo.py --mode live --live-example approval
python academy/labs/05_coding_guardrails/demo.py --mode live --live-example safety
```

## 观察点

1. 第一次失败是建立基线，不是坏消息；
2. 修改只有一行，便于复核和回滚；
3. 同一测试在修改后通过，构成结果证据；
4. `create_os_env(working_dir)` 约束工作目录，但不应称为强 OS 沙箱；
5. SafetyDefaults 是分层护栏的一部分，不理解完整 shell 语义。
