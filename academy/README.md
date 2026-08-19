# Senza Academy

Senza Academy 用《动手学 AI Agent》的理论解释 Runtime/Senza 的真实设计，并用一条
连续的 Developer Agent 主线完成十个实验。课程的目标不是记 API，而是理解一个能力
为什么属于 Core、Hook、Plugin、Tool、Store 或外部基础设施。

系统化解释、源码导读和章后复习题见
[`docs/academy/textbook/`](../docs/academy/textbook/README.md)；本目录专注可运行实验与证据轨迹。

## 两种运行模式

- **recorded（默认）**：只用 Python 标准库，重放已审阅的事件轨迹；无需安装 Senza、
  无需模型密钥，适合课堂和 CI。
- **live**：转到 `live-tests/examples/` 的权威真实示例，调用当前 Senza API 和真实模型；
  没有 Provider key 时沿用现有示例的清晰跳过行为。

```powershell
# 从 Senza 仓库根目录运行
python academy/labs/01_react_tool_calling/demo.py
python academy/labs/01_react_tool_calling/demo.py --mode live

# 全部离线验收
python -m pytest academy/tests academy/labs -q
```

recorded trace 不是伪装成在线执行的结果。每份 trace 都写明：它证明什么、不能证明什么，
并列出对应 live example。需要证明 Provider、真实工具回调或持久化行为时，必须运行 live
示例或仓库集成测试。

## 学习地图

| 课 | 问题 | 关键组件 | 成熟度 |
| --- | --- | --- | --- |
| 01 | 模型如何从回答走向行动？ | Agent Core、Tool、ReAct | stable |
| 02 | 治理逻辑在循环的哪里发生？ | 12 fixed Hooks | stable |
| 03 | 一个能力包如何复用和限定作用域？ | Plugin、allow/modify/deny | stable |
| 04 | 上下文为什么不是一大段 Prompt？ | Skill、StatusPanel、Compaction | stable |
| 05 | Coding Agent 如何形成可验证闭环？ | FS tools、Safety、Rules | stable |
| 06 | 什么时候使用 Workflow？ | Judge、Executor、TaskStore、HITL | stable |
| 07 | Knowledge、Memory、Recall 有何区别？ | BM25、Memory contract、Recall contract | teaching/preview |
| 08 | 多 Agent 的真实价值和限制是什么？ | MessageBus、spawn lifecycle | teaching |
| 09 | 一次成功为什么不等于可靠？ | repeated runs、verifier、cost/latency | teaching |
| 10 | 如何从 bad case 安全地改进框架？ | proposal、retention set、approval | teaching |

完整范围、验收和非目标见
[`docs/academy/2026-08-19-senza-academy-ai-agent-book-plan.md`](../docs/academy/2026-08-19-senza-academy-ai-agent-book-plan.md)。
