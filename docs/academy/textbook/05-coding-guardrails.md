# 第 5 章：Coding Agent——让修改经过确定性 Guardrail 与验证闭环

> 成熟度：**stable**。文件工具、Rule Hook、SafetyDefaults 与真实 OS execution env 均有当前
> Senza/Runtime 实现；本章的单行修复 recorded 场景是 **teaching**，用于稳定讲清闭环。

## 本章回答的问题

模型说“已经修好”为什么不能作为 Coding Agent 的完成条件？因为自然语言结论只是一次预测，代码
库中的文件、编译器和测试结果才是环境事实。本章回答五个具体问题：

1. 一个 Coding Agent 至少需要哪些观察与动作？
2. 为什么修复前要先复现失败，修复后还要运行同一验证？
3. Rule、SafetyDefaults 和测试分别约束动作的哪个阶段？
4. `create_os_env(working_dir)` 提供了什么，又为什么不能称为强沙箱？
5. 如何把“最小修改、可回退、可验证”变成 Harness 的确定性结构，而不是一句提示词？

## 学习目标与先修知识

完成本章后，你应该能够：

- 写出“观察—建立基线—最小修改—复验—交付证据”的 Coding 闭环；
- 正确装配 `FsToolsPlugin` 与 `ExecutionEnv`，并说清二者缺一时会发生什么；
- 解释 `before_tool_call` 为什么比“请不要执行危险命令”更可靠；
- 区分工作目录、路径检查、命令黑名单与操作系统级隔离；
- 为一次代码修改设计正向测试、危险动作测试和回退手段。

先修内容是[第 1 章的 Tool Calling 闭环](01-react-tool-calling.md)、
[第 2 章的 Hook 生命周期](02-hook-lifecycle.md)与
[第 3 章的 Plugin 装配](03-plugin-composition.md)。理论可对照本地《动手学 AI Agent》的
[第一章“护栏与安全性”](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)和
[第五章“Coding Agent”](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter5.md)。

## 理论直觉：Coding Agent 是带反馈的控制器

### “会写代码”只是动作能力

一个只会根据需求输出代码块的模型是代码生成器。Coding Agent 还必须观察仓库、执行动作、接收
环境反馈并修正策略。它的最小闭环可以写成：

```text
理解任务
  → 读取项目约束与相关代码
  → 运行验证，建立失败基线
  → 做最小且可复核的修改
  → 运行同一验证
  → 根据结果继续修正或提交证据
```

这里最关键的一步是“验证决定是否停止”。测试失败并不一定说明 Agent 工作失败；第一次稳定复现
预期故障，反而说明任务边界已经从自然语言变成了可观测事实。真正危险的是没有运行验证就提前
结束。

### 动作空间越强，边界越要下沉

`read`、`grep`、`glob` 扩展观察空间，`write`、`edit`、`bash` 扩展动作空间。动作空间越强，单靠
模型自律越不够。即使 system prompt 写着“不要删除重要文件”，一次提示注入、误解或拼写错误仍
可能产生破坏性命令。

因此可靠系统需要多层、不同失效方式的边界：

| 防线 | 它在回答什么 | 典型实现 |
| --- | --- | --- |
| Tool schema | 参数形状是否明确 | JSON Schema、清晰命名、必填字段 |
| Pre-execution policy | 这个动作在生效前是否允许 | Rule approval、`before_tool_call`、人工审批 |
| Execution environment | 动作实际能触达哪些资源 | 工作目录、最小权限凭证、容器或 OS 沙箱 |
| Post-action observation | 工具到底做了什么 | ToolResult、文件 diff、退出码 |
| Independent verifier | 结果是否满足完成条件 | 测试、lint、类型检查、CI |
| Recovery | 出错后能否回退 | 临时工作区、快照、Git 分支 |

这些防线不能互相冒充。工作目录不是沙箱，黑名单不是 shell 语义证明，测试通过也不能证明修改
过程没有越权。

### 最小修改是一种可验证性设计

改动越小，读者越容易审查，失败时越容易定位，回退范围也越清晰。“把减号改成加号”比“重写
整个计算模块”提供了更强的因果证据：同一测试从失败变为通过，且唯一变化与故障直接相关。

最小修改不是要求永远只改一行，而是要求每次变更的范围能由证据解释。若必须重构多个模块，就应
先拆分设计、增加保护性测试，再逐步移动边界。

## Runtime/Senza 架构映射

### 工具、环境和策略各司其职

| 职责 | Senza 入口 | Runtime 实现 | 关键语义 |
| --- | --- | --- | --- |
| 文件与命令动作 | `create_fs_tools_plugin()` | `FsToolsPlugin` | 构建期注册 `read/write/edit/bash/grep/glob` 六个工具 |
| 真实执行后端 | `create_os_env(working_dir)` + `.env(...)` | `OsEnv` 实现 `ExecutionEnv` | 相对路径以工作目录解析，文件和 shell 操作落到真实宿主机 |
| 通用规则审批 | `senza.rules.chain()` + `approval_hook()` | `RuleBasedApprovalHook` | 在 `before_tool_call` 做 allow/deny，deny 时 callback 不执行 |
| 默认安全策略 | `senza.strategy.safety_defaults()` | `SafetyDefaultsPlugin` | `bash` 黑名单，以及 `read/write/edit` 的路径检查 |
| 循环安全 | `senza.strategy.loop_safety()` | 多个循环/失败守卫 Hook | 限制重复、失败级联和过多轮次，不判断代码业务正确性 |
| 结果验证 | 项目已有测试/CI，通过 Tool 执行 | 外部编译器、测试框架 | 结果作为 observation 回到下一轮，独立于模型口头结论 |

`FsToolsPlugin` 只是提供动作接口。若没有 `.env(...)`，builder 使用 `UnsupportedEnv`，依赖文件系统
或 shell 的工具会报错。若传入 `create_os_env(...)`，它们就会访问真实主机，而不是自动进入容器。

### 一次工具调用经过的关键边界

```text
模型产生 tool call
      │
      ▼
BeforeToolCall composite
  ├─ Rules：按业务 allow / deny
  └─ SafetyDefaults：按工具名检查命令或路径
      │ Allow
      ▼
Tool 使用 ExecutionEnv 执行真实动作
      │
      ▼
ToolResult / AfterToolCall → Trajectory → 下一轮模型判断
```

deny 的价值在于它发生在动作生效之前。模型仍会在轨迹中看到结构化失败，可以改用更小范围的动作
或向人请求批准；被拒绝的 Tool callback 不应被调用。

### `read` 与 `edit` 的快照耦合

Senza 创建文件工具 Plugin 时会共享一个 `FileSnapshotStore`。`read` 输出带内容 tag，`edit`
可以拒绝与内存快照不一致的 tag；通过同一 Plugin 执行的 `write` 会使已知快照失效，成功的
`edit` 则刷新快照。这能发现“调用方拿错 tag”或“共享 store 已知已失效”的情况。

它目前不是针对任意外部并发修改的文件系统 CAS：命中快照后，`edit` 使用缓存行生成新内容，
不会先重新读取并哈希磁盘文件。另一个编辑器或进程在 `read` 与 `edit` 之间改动文件时，旧快照
仍可能覆盖新内容。共享仓库上的强并发保护需要隔离 worktree、提交前重新读取，或由后端提供
基于当前内容摘要的 compare-and-swap。

## 一条完整执行故事：修复 `calculator.add`

### 1. 把任务放进可回退工作区

Academy 不直接修改 fixture，而是把小项目复制到临时目录。这样失败实验不会污染教材源码，进程结束
后临时目录也会清理。生产项目中对应的做法可以是独立 Git 分支、工作树、容器卷或快照。

### 2. 先运行测试，建立基线

`calculator_spec.py` 断言 `add(2, 3) == 5`。第一次执行得到非零退出码，因为实现返回
`left - right`。此时我们得到三条信息：故障可复现、验证命令可用、期望值明确。

若第一遍测试已经通过，就不能机械地继续修改；应先确认用户描述是否过时、是否还有缺失用例，或
测试是否跑在错误目录。

### 3. 缩小观察范围

Agent 只需要阅读实现和对应测试，不必把整个仓库装入上下文。真实 Senza 场景可以先用 `glob` 找
文件、`grep` 找符号，再用 `read` 获取必要片段。工具结果进入 Trajectory，模型据此定位到唯一的
减号。

### 4. 在执行前经过策略判断

正常的 scoped edit 进入 `before_tool_call`，业务 Rule 和安全 Hook 均允许后才执行。若候选动作是
`rm -rf /`，策略应在执行前返回 deny，底层 shell 根本不获得控制权。

Lab 的 recorded 模式为了无 Provider、跨平台和零风险，使用 `evaluate_command()` 做一个确定性教学
判断，并且函数无论 allow 还是 deny 都不会执行命令。这证明的是“决策先于执行”的因果顺序，不是
真实 SafetyDefaults Hook 已被调度。真实装配由 14、15 号 live 示例承担。

### 5. 做一行修改

教学场景把唯一的 `return left - right` 替换为 `return left + right`。替换前先断言目标行恰好出现
一次，避免把“找不到”和“出现多次”静默当成成功。真实 `edit` 工具的 old/new 或锚点语义也服务于
同一目标：让编辑位置可验证。

### 6. 运行同一测试，形成结果证据

修改后再次执行 `calculator_spec.py -q`，退出码变为 0。因为工作目录、测试和唯一代码变化都可控，
这组 before/after 证据支持“这个修改修复了已知回归”。交付时应报告测试命令和结果，而不是只说
“我检查过了”。

### 7. 仍然保留边界声明

单个用例通过不证明所有输入都正确，更不证明整个仓库没有回归。若这是生产修改，还要根据风险运行
更广的测试、lint 或 CI，并审查 diff。验证范围本身也是交付信息。

## 源码导读

1. [`runtime-tools/src/lib.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime-tools/src/lib.rs)
   是六个文件工具的 Plugin 聚合入口，可看到共享 snapshot store 和注册清单。
2. Senza 的 [`src/lib.rs`](../../../src/lib.rs) 暴露 `create_os_env()` 与
   `create_fs_tools_plugin()`；Runtime 的
   [`env.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime-sandbox-os/src/env.rs)
   直接调用真实文件系统和宿主 shell。
3. [`pyrules.rs`](../../../src/runtime/pyrules.rs) 把 Python RuleChain 变成
   `BeforeToolCallHook`。结合
   [`14_rules_approval.py`](../../../live-tests/examples/14_rules_approval.py)观察“尝试调用”和“callback
   真正执行”的区别。
4. [`pysafety.rs`](../../../src/strategy/pysafety.rs) 是 Python Plugin 工厂；具体分发位于
   [`safety/mod.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-strategy/src/safety/mod.rs)：只有工具名为
   `bash`、`read`、`write`、`edit` 时进入相应检查。
5. [`safety/command.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-strategy/src/safety/command.rs)
   明确写出了默认命令检测规则和已知限制；
   [`safety/path.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-strategy/src/safety/path.rs)
   定义了静态 `..` 检查和可选的 canonicalize 检查。继续沿调用点核对会发现：标准 Senza run
   当前没有把 `ExecutionEnv` 放入该 Hook 查询的 Run extension，因而通常只执行词法检查；即使
   手工注入，当前 OS env 的 `file_info()` 也返回拼接路径而非解析 symlink 后的 canonical path。
6. [`sandbox.rs`](https://github.com/oh-my-harness/llm-harness-runtime/blob/c1a82733593b6f1fb5ace2c805de83b4e8f3e3f9/crates/llm-harness-runtime-sandbox-os/src/sandbox.rs)
   直接将 `OsEnvSandbox` 描述为“without security isolation”，这是不能把 OS env 宣传成强沙箱的
   最直接证据。

源码阅读时不要只看类名里的 `Safety` 或 `Sandbox`。真正的安全边界由它检查哪些工具名、解析哪些
shell 语法、访问什么主机资源来决定。

## 配套实验

在 Senza 仓库根目录运行 [Lab 05](../../../academy/labs/05_coding_guardrails/README.md)：

```powershell
python academy/labs/05_coding_guardrails/demo.py
python -m pytest academy/labs/05_coding_guardrails/test_demo.py -q
```

请不要只看“最后通过”，而要记录四项证据：

1. 修改前测试退出码非 0；
2. 唯一变更是 `return left - right` → `return left + right`；
3. 修改后同一测试退出码为 0；
4. 危险命令的决定是 `deny`，且 `executed` 为 `False`。

随后阅读
[`coding_scenario.py`](../../../academy/labs/05_coding_guardrails/coding_scenario.py)，确认 fixture 被复制到
临时目录，危险命令没有传给 `subprocess`。再按环境运行真实 Senza 链路：

```powershell
python academy/labs/05_coding_guardrails/demo.py --mode live --live-example fs
python academy/labs/05_coding_guardrails/demo.py --mode live --live-example approval
python academy/labs/05_coding_guardrails/demo.py --mode live --live-example safety
```

三个入口分别委托
[`22_fs_tools.py`](../../../live-tests/examples/22_fs_tools.py)、
[`14_rules_approval.py`](../../../live-tests/examples/14_rules_approval.py)与
[`15_safety_injection.py`](../../../live-tests/examples/15_safety_injection.py)。live 模式需要真实 Provider；
缺少密钥时应按项目约定跳过，不能用 recorded 结果替代 Hook dispatch 证据。

## 常见误解与能力边界

### 误解 1：`create_os_env(working_dir)` 会把 Agent 困在该目录

不会。它用该目录解析相对路径，但后端仍是宿主机真实文件系统和 shell；绝对路径、shell 子进程、
网络和凭证的可见范围取决于宿主环境。它适合受控开发和测试，不是容器、microVM 或强 OS 沙箱。

### 误解 2：SafetyDefaults 能理解完整 shell 语义

不能。当前实现是原始正则预扫加有限的子命令切分，不展开变量，也明确记录了 `find ... -exec rm`
等已知盲区。它是有价值的一层默认防线，不是允许在高风险主机上任意执行模型命令的安全证明。

### 误解 3：安装 SafetyDefaults 后所有工具自动受保护

Hook 按工具名和参数字段分发。自定义工具若叫 `run_command` 而不是 `bash`，或路径参数不叫 `path`，
不会自动获得相同检查。新 Tool 必须显式加入业务 Rule、权限系统或独立执行边界。

### 误解 4：路径检查等于文件系统隔离

不是。标准 Senza 当前对 `read/write/edit` 主要执行词法路径检查，例如拒绝越过根目录的 `..` 和
不允许的绝对路径；它不能可靠阻止工作区内 symlink 或 Windows junction 指向外部。Runtime 虽定义
可选 canonicalize check，但当前 Senza/OS env 默认链路没有形成可证明的真实路径解析闭环。
`bash` 还有独立的命令规则，更不能用文件 Tool 的路径检查推导 shell 被限制在工作区。真正隔离
应由容器、microVM、受限文件后端或操作系统权限提供。

### 误解 5：recorded 中拒绝了 `rm -rf /`，所以真实 Plugin 已验证

recorded 的 `evaluate_command()` 是 Academy 教学函数，而且刻意永不执行任何候选命令。真实
SafetyDefaults/Rule Hook 是否生效，要看 live example、callback 计数和 Runtime 测试。

### 误解 6：一个测试通过就可以宣布整个任务完成

它只证明该用例在当前环境通过。交付应同时说明运行了哪些测试、哪些没有运行、是否有未审查 diff
以及环境限制。更广的风险需要更广的 verifier。

### 误解 7：Guardrail 越严格越好

过度拒绝同样是失败。策略测试必须同时包含“危险动作确实被拒绝”和“合法动作仍能完成”两类用例，
否则 Agent 可能安全但不可用。

## 本章小结

可靠 Coding Agent 的核心不是一次生成正确代码，而是把可观察环境、最小动作、执行前策略和独立
验证连成闭环。Senza 的 FsToolsPlugin 提供动作空间，ExecutionEnv 决定动作落到哪里，Rule 与
Safety Hook 在动作生效前治理，测试和 ToolResult 则把事实送回 Agent Core。真正的安全还需要最小
权限、隔离、审计和可回退工作区，不能由一个名称漂亮的默认 Plugin 代替。

## 复习题

1. 为什么第一次失败测试是修复证据的一部分？
2. `FsToolsPlugin` 注册哪六个工具？为什么仍然需要 `ExecutionEnv`？
3. Tool call 被 deny 后，模型、Tool callback 和外部环境分别会看到什么？
4. `working_dir`、SafetyDefaults 和强 OS 沙箱的边界分别是什么？
5. 为什么同一测试的 before/after 对比比“模型解释修改正确”更有说服力？
6. 若新增 `deploy_service` 工具，你会在哪些层增加约束和验证？
7. 如何同时测试 Guardrail 的漏放风险与误拒绝风险？

## 延伸阅读

- 理论：[《动手学 AI Agent》第 5 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter5.md)
- 实验：[Lab 05 README](../../../academy/labs/05_coding_guardrails/README.md)与
  [`expected_trace.json`](../../../academy/labs/05_coding_guardrails/expected_trace.json)
- 真实文件工具：[Senza FS tools 示例](../../../live-tests/examples/22_fs_tools.py)
- 真实审批与安全：[Rules approval](../../../live-tests/examples/14_rules_approval.py)、
  [Safety defaults](../../../live-tests/examples/15_safety_injection.py)
- 下一章：[Workflow、按步恢复与 Human in the Loop](06-workflow-recovery-hitl.md)
