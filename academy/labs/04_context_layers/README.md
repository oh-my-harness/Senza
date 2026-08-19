# 第 4 课：上下文不是一大段 Prompt

这一课把一次模型请求拆成五个可独立演进的层：稳定前缀、按需 Skill、动态 Status、不断增长
的 Trajectory，以及对旧轨迹做有损提炼的 Compaction。目标不是记五个名词，而是看清每层
为什么出现、何时变化、由谁维护。

## 理论坐标

本课主要参考本地《动手学 AI Agent》第二章
[`ai-agent-book/book/chapter2.md`](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter2.md)：

- “从 API 视角看上下文的构成”：静态前缀 + 动态轨迹；
- “动态提示词与 Agent Skills”：少量目录常驻、完整正文按需加载；
- “Agent 状态栏”：把隐式进度与计数提炼为轨迹末尾的显式状态；
- “上下文压缩策略”：保持前缀，批量压缩旧历史，提高信息密度。

第一章
[`chapter1.md`](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md) 对系统提示、工具定义、用户消息、
模型回复和工具结果的五部分划分，是这套分层视图的入口。

## Senza 映射

| 教学层 | Senza/Runtime 组件 | 变化方式 |
| --- | --- | --- |
| Stable prefix | system prompt + 核心 tool schemas | 尽量保持稳定 |
| Skill | `load_skills()`、`builder.skills()`、`skill_read` | 目录可发现，正文按需进入轨迹 |
| Status | `strategy.status_panel()` 的 StatusBarHook | 每轮在上下文末尾注入当前 TODO、环境和工具计数 |
| Trajectory | User / Assistant / Tool messages 与 session ledger | 随 Agent 循环追加 |
| Compaction | auto-compaction、上下文感知 prompt、`Harness.compact()` | 用摘要替换较老轨迹，保留近期证据 |

Senza Python 当前已经有手工压缩 API：`harness.compact()` 返回 `tokens_before`、
`tokens_after` 和 `compressed_entries`；它不是 Runtime-only 能力。自动压缩则由 builder 的
上下文窗口、reserve、keep-recent 与 `auto_compact()` 配置驱动。

## 运行

```powershell
# 默认 recorded：输出五层的确定性 context diff
python academy/labs/04_context_layers/demo.py

# live：分别委托三个权威示例
python academy/labs/04_context_layers/demo.py --mode live --live-example skills
python academy/labs/04_context_layers/demo.py --mode live --live-example status
python academy/labs/04_context_layers/demo.py --mode live --live-example compaction

# 离线验收
python -m pytest academy/labs/04_context_layers/test_demo.py -q
```

映射关系为：`skills` →
[`06_skills_model_switch.py`](../../../live-tests/examples/06_skills_model_switch.py)，
`status` → [`16_status_panel.py`](../../../live-tests/examples/16_status_panel.py)，
`compaction` →
[`21_context_aware_compact.py`](../../../live-tests/examples/21_context_aware_compact.py)。

## recorded diff 怎么读

- `=`：该层字节内容保持不变；每个快照的 stable prefix 都应如此。
- `+`：原来为空，这次新增一层。
- `~`：该层发生替换或增长；例如 Skill 正文加载、Status 更新、Trajectory 增长。
- Compaction 快照会让旧 Trajectory 变短，并新增结构化摘要；它不应改写 stable prefix。

## 能力边界

- recorded 快照是可测试的**教学模型**，不是从 Provider 请求中截获的原始 messages，也不
  证明 Prompt Cache 命中、模型注意力分配或摘要质量。
- Skills 的 live 示例证明 Senza 的目录加载与 `skill_read`；不同 Harness 对 Skill catalog
  的具体消息角色和包装方式可以不同，不应把教学层名当作固定 API role。
- StatusPanel 是 Plugin 贡献的 tool + hooks 组合；状态栏是有损投影，不能无条件代替原始
  轨迹。
- Compaction 有损且会调用模型。manual `compact()` 已存在，但“API 可调用”不等于每份
  摘要都保留了任务所需信息，仍需按任务验证。
