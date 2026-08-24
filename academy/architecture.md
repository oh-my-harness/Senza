# 从 Model–Harness 边界理解 Runtime 与 Senza

## 1. 先划边界

《动手学 AI Agent》给出两个互补视角：最小 Agent 由 LLM、上下文和工具组成；生产
Agent 可以理解为 Model 与 Harness 的组合。Model 决定下一步，Harness 负责准备输入、
执行动作、维护状态、施加约束、验证结果和纠正错误。

```text
Environment（文件、网页、数据库、OS）
               ↑ Tool 执行 / Observation
Senza 应用 → Runtime Agent Core → Model Provider
                  ↑
          fixed Hooks ← Plugins
```

Environment 不属于 Runtime 内核。Runtime 提供与环境交互的协议和工具运行边界，但不会
把第三方数据库、消息队列或操作系统隔离能力凭空变出来。

## 2. Agent Core 为什么要小而稳定

Core 只持有所有 Agent 都需要的控制面：Run、Turn、Provider request/response、Tool
call/result、上下文变换、压缩、下一轮准备、停止与最终答案校验。这样循环语义只有一个
权威实现，安全、记忆、审计等策略不必各自复制一套 Agent。

## 3. Hook 是固定生命周期，不是任意插桩

当前 Core 定义 14 个 Hook：

```text
before_run
before_turn / after_turn / should_stop
before_provider_request / after_provider_response
before_tool_call / after_tool_call
transform_context / before_compact / prepare_next_turn
final_answer_validator
after_run
on_abort
```

Hook 的“开放”是指在这些固定边界注册多个实现；Plugin 不能选择源码中的任意行作为
挂载位置。不同 Hook 有不同组合语义，例如 tool 前置策略可以短路，context transform
按顺序传递结果，stop 决策会聚合多个观察者。

## 4. Plugin 定义能力包，不定义主循环

Rust Plugin 协议可以贡献 tools、hooks、skills 和 prompt templates。Builder 在构建期
收集这些贡献，再验证重名 Tool、构造注册表并返回 Harness。Python `create_plugin()`
当前只开放 tools 与 hooks；Skills 通过 Builder 的专用装配路径进入。

这解释了“易扩展”的真正含义：

- Core 的状态机与收敛语义不被复制；
- 新能力只实现相关协议并在构建期安装；
- Agent 级与 Workflow step 级可以选择不同作用域；
- Plugin 可以独立开关，适合消融、回归和回滚；
- 冲突会在构建时暴露，而不是运行时静默覆盖。

它不等于运行中的热插拔、自卸载或任意动态改写 Core。

## 5. Senza 是装配面

Senza 通过 PyO3 暴露 Runtime，并增加 Python 友好的装饰器、async helper 与领域命名
空间。`HarnessBuilder → AgentHarness` 用于路径由模型决定的自主循环；
`WorkflowEngine` 用于步骤、边、Judge、Executor、恢复点和人工审批由开发者明确控制的
流程。Workflow 的 LLM step 仍会构建 Harness，因此公共 Hook、Plugin、预算与定价策略
仍能复用。
