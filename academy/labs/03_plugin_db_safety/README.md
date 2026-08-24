# 第 3 课：用 Plugin 复用 DB Safety

这一课回答一个工程问题：一条已经验证过的安全经验，怎样从某个 Agent 里的临时代码，
变成可复用、可限定作用域、可审查的 Harness 能力？

## 理论坐标

《动手学 AI Agent》第一章的“Agent 的学习机制：从上下文适应到持久更新”指出，跨任务
保留经验的一条路径，是把确定性流程与约束写进程序和 Harness，使其成为可审计、可修订
的外部产物。参见本地
[`ai-agent-book/book/chapter1.md`](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)，尤其是
“外部产物”一节。

Senza/Runtime 的 Plugin 正是这类工程载体之一：它不训练模型，而是在 Core 已定义的生命周期
边界上贡献能力。

## Runtime/Senza 映射

```text
纯 Python guard
      │
before_tool_call Hook ── allow / modify / deny
      │
create_plugin(name, tools=[...], hooks=[...])
      ├── HarnessBuilder.plugin(plugin)             Agent scope
      └── WorkflowEngine.with_step_plugin(id, ...)  step scope
```

- Plugin 在**构建期**安装：贡献先累积到 builder，构造 Harness 或 step runner 时形成工具表和
  Hook 链；它不是运行时热插拔，也不是任意源码注入点。
- `HarnessBuilder.plugin()` 让贡献作用于整个 Agent；
  `WorkflowEngine.with_step_plugin()` 只把同一能力装到指定 Workflow step。
- Runtime 的 Rust `Plugin` 协议可贡献 tools、hooks、skills、templates；Python
  `create_plugin()` 当前只开放 **tools 和 hooks**。
- 重名 Tool 不采用“后注册覆盖前注册”。正式 Harness build 会拒绝重复或保留的工具名，
  因而冲突在**构建时报错**，不会留到 dispatch 时随机选择。

对应实现可从
[`src/lib.rs`](../../../src/lib.rs)、[`src/core/pybuilder.rs`](../../../src/core/pybuilder.rs)、
[`src/runtime/pyworkflow.rs`](../../../src/runtime/pyworkflow.rs) 交叉核对。

## 运行

从 Senza 仓库根目录执行：

```powershell
# 默认：标准库即可，真正调用本课的纯 Python guard
python academy/labs/03_plugin_db_safety/demo.py

# 在线：委托权威示例，验证 Senza Plugin 和 Hook 的真实装配
python academy/labs/03_plugin_db_safety/demo.py --mode live

# 离线验收
python -m pytest academy/labs/03_plugin_db_safety/test_demo.py -q
```

recorded 模式依次提交三条输入：有界 `SELECT` 得到 `allow`，无界 `SELECT` 得到
`modify` 并补上 `LIMIT 100`，`DROP` 得到 `deny` 且不会进入模拟 executor。

## 观察点

1. guard 的返回值与当前 `before_tool_call` Python 契约一致：`"allow"`、
   `{"action": "modify", "args": ...}`、
   `{"action": "deny", "result": ...}`。
2. 修改发生在 executor 之前，因此 executor 看到的是改写后的参数。
3. deny 返回给模型的是结构化失败结果；被拒绝的 SQL 不进入 executor。
4. 相同 Plugin 可以装到 Agent 或单个 step，差异是作用域，不是 Hook 位置。

## 能力边界

- recorded 只证明纯 Python 策略函数和教学 trace，**不证明** Senza 已构造 Harness、模型一定
  发起工具调用，或 Runtime Hook dispatch 已运行；这些由
  [`32_plugins.py`](../../../live-tests/examples/32_plugins.py) 的 live 模式证明。
- 本课正则规则是最小教学策略，不是生产 SQL parser。生产系统还应使用只读数据库凭证、
  事务权限和结构化 SQL 校验形成纵深防御。
- Plugin 只能挂到 Core 已定义的 Hook；不能自行选择任意源码位置。
- Tool 冲突行为属于 build 路径。recorded trace 只陈述已核对的源码契约，不伪造一次 build。
