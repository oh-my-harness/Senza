# 02 · Hook X 光片

这一课回答：安全、上下文、观测和收敛策略要进入 Agent 循环时，究竟挂在哪里？

《动手学 AI Agent》在[第 1 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)把生产形态展开为
`Agent = Model + Harness`，并将 Harness 的职责概括为上下文管理、工具接口、约束、
验证与纠正。书给出“为什么”；Runtime 把这些职责落到 Agent Core 预先定义的 12 个
生命周期边界。Hook 的开放性是“可在固定边界注册多个实现”，不是 Plugin 可以选择源码
任意一行插入逻辑。

权威定义见 Runtime 的
[`HarnessHooks`](https://github.com/oh-my-harness/llm-harness-runtime/blob/03aed0ce550aa0c95cb26d9667f6440bc3dd3349/crates/llm-harness-agent/src/harness/state.rs)；多 Hook
组合语义见
[`composite.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/03aed0ce550aa0c95cb26d9667f6440bc3dd3349/crates/llm-harness-loop/src/composite.rs)。

## 13 个固定挂载点

| Hook | Core 中的时机 | 同类 Hook 的组合语义 |
| --- | --- | --- |
| `before_run` | 一次 `prompt()` run 开始前 | 全部按注册顺序执行；追加消息累积，最后一个非空 system prompt 胜出 |
| `before_turn` | 每个 turn 开始前 | 全部执行，纯通知 |
| `transform_context` | 每次模型调用前转换结构化上下文 | 链式；后一个看到前一个的输出 |
| `before_provider_request` | Provider 请求前 | 全部执行，并依次修改同一个 `StreamOptions` |
| `after_provider_response` | Provider 响应后 | 全部执行，纯观测 |
| `before_tool_call` | 工具执行前 | 第一个 `Modify` 或 `Deny` 短路；全为 `Allow` 才放行 |
| `after_tool_call` | 工具执行后 | 链式；每个 `Replace` 成为下一个 Hook 的输入 |
| `after_turn` | turn 结束后 | 全部执行，纯通知 |
| `prepare_next_turn` | 根据上一轮准备下一轮 | 全部执行；每个字段采用最后一个非空值 |
| `should_stop` | 模型自然停止后 | 全部执行，不短路；任一返回 `true` 则停止 |
| `before_compact` | 实际压缩前的条件分支 | 第一个非 `Proceed` 决策短路 |
| `final_answer_validator` | 候选答案越过提交边界前 | 按序校验，第一个拒绝短路 |
| `after_run` | run 结束、Harness 回到 Idle 后 | 全部执行，纯通知 |

这张表也解释了为什么“Plugin 可以随意组合”只在契约范围内成立：多个 Plugin 可以向
同一固定槽位贡献 Hook，但顺序和返回类型会决定组合结果；不能假设所有 Hook 都是简单
广播，更不能把 Hook 当成运行时任意插桩或热补丁。

## 运行

在 Senza 仓库根目录执行：

```powershell
# 默认：覆盖 13 类固定挂载点的教学图谱
python academy/labs/02_hook_xray/demo.py

# 在线：委托当前 Python Hook 权威示例
python academy/labs/02_hook_xray/demo.py --mode live

# 本课离线验收
python -m pytest academy/labs/02_hook_xray/test_demo.py -q
```

live 模式直接运行
[`live-tests/examples/07_hooks.py`](../../../live-tests/examples/07_hooks.py)。该 Python 示例
当前实际证明的是 `before_turn`、`after_turn`、`before_tool_call`、`after_tool_call` 四个
边界及工具前后对称性；本课不会把它描述为“单次 live 覆盖 13 个 Hook”。

## 怎样阅读 recorded timeline

recorded trace 是生命周期图谱，不是一条真实 run 的逐纳秒日志。前十项组成常见的
run/turn/tool 主路径；`before_compact` 与 `final_answer_validator` 显示两个条件分支。
它们被放在一份轨迹里是为了核对 13 类契约，并不声称每次 run 都会触发全部 Hook，
也不声称图谱顺序替代 Runtime 源码中的实际控制流。

## 能力边界

- 12 个位置由 Agent Core 定义；Plugin 只能选择已声明的槽位；
- Hook 的注册顺序是构建期配置，不是 built harness 上的任意热插拔；
- recorded 图谱证明命名、职责和组合契约的一致性，不证明 Provider 时序或调用次数；
- Python `07_hooks.py` 的在线覆盖面小于 Runtime 全部 Hook 面，缺失边界需由对应 Runtime
  测试或其他专项示例证明。
