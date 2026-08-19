# Lab 06：Workflow、按步恢复与 Human in the Loop

## 要回答的问题

什么时候应该让模型自主决定路径，什么时候应该把流程写死？书中第 1 章区分自主 Agent
与确定性 Workflow，第 6 章解释外部事件与安全边界。步骤内部需要理解和生成时可以使用
LLM；跨步骤的合规检查、恢复点和审批应由 Workflow 明确控制。

理论来源：[`ai-agent-book/book/chapter1.md`](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)、
[`chapter6.md`](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter6.md)。

## 对应到 Senza

- `WorkflowEngine` 定义 step、edge 与 entry；
- Judge 负责路由，Executor 负责可验证计算；
- TaskStore 持久任务状态，`restore_from_step()` 从指定边界重跑；
- event channel 把审批作为外部事件提交，而不是写进模型的“请自觉确认”提示。

recorded 模式运行一个纯 Python 的 checkpoint 模型：draft 完成、check 通过、approve
暂停；随后模拟重启并从 check 重放；只有收到明确 reviewer 后才 publish。它用于稳定显示
状态语义，不假装自己就是 Senza 引擎。真实 API 分别由 08、39、41、45 号 live 示例证明。

```powershell
python academy/labs/06_workflow_recovery_hitl/demo.py
python academy/labs/06_workflow_recovery_hitl/demo.py --mode live --live-example recovery
python academy/labs/06_workflow_recovery_hitl/demo.py --mode live --live-example hitl
```

## 观察点

1. check 是确定性 Executor，不必浪费模型调用；
2. TaskStore 保存 paused 状态，publish 不会越过审批；
3. 从 check 恢复会废弃下游旧状态并增加 attempt；
4. Human approval 是带身份和内容的事件；
5. pause/cancel 通常在 step 边界生效，不能宣传为任意 Provider 请求的强制抢占。
