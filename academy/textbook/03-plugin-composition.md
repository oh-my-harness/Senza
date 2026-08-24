# 第 3 章：Plugin 装配——把经验变成可复用的构建期能力包

> 成熟度：**stable**。Runtime 的 Rust `Plugin` 协议、Senza `create_plugin()`、Agent scope 与
> Workflow step scope 均有当前源码支撑。配套 DB Safety recorded 实验真实执行纯 Python guard，
> 但只有 live example 才证明 Plugin build 与 Runtime Hook dispatch。

## 本章回答的问题

一个 Agent 已经有了 Tool 和 Hook 后，为什么还需要 Plugin？已经验证过的安全规则怎样跨 Agent 和
Workflow step 复用？Plugin 能否随意组合，所谓“前置依赖”究竟是别的 Plugin、额外 Python 包，
还是外部服务？如果某项能力需要 Core 没定义过的数据或生命周期位置，又该放在哪里？

本章给出的核心答案是：**Plugin 是构建期能力包**。它把一组符合 Runtime 协议的贡献交给 Builder，
由 Builder 在构造 Harness 或 step runner 时安装。它不训练模型，不拥有 Agent Core，也不是 built
Harness 上可以任意热插拔的模块。

## 学习目标与先修知识

完成本章后，你应当能够：

1. 解释 Plugin、Tool、Hook、Builder 四者的关系；
2. 说明 Rust Plugin 与 Python `create_plugin()` 的能力差异；
3. 判断两个 Plugin 是否可组合，并识别顺序、命名和后端依赖；
4. 区分 Agent scope 与 Workflow step scope；
5. 用 DB Safety Plugin 把确定性策略装到工具执行前；
6. 判断“新需求应放进 Tool/Hook/外部后端，还是需要修改 Core”。

先修知识：完成[第 1 章](01-react-tool-calling.md)和[第 2 章](02-hook-lifecycle.md)，特别是
Tool callback 的环境边界、14 个固定 Hook 类型及其组合语义。

## 理论直觉：把经验固化在模型之外

[《动手学 AI Agent》第 1 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)把 Agent 行为的更新分为
任务内上下文适应、跨任务外部产物更新和模型参数更新。把确定性约束写进程序和 Harness，属于可
审计、可修订、可回滚的外部产物：它不要求重新训练模型，却能在每次构建时稳定生效。

假设团队发现三个数据库风险：禁止非 SELECT、无界查询必须加 LIMIT、被拒调用不得进入 executor。
如果规则只写在 system prompt 中，模型可能忘记或绕过；如果每个 Agent 手工复制 guard，规则会
漂移；如果直接把规则写死进 Agent Core，Core 又会被具体业务污染。

Plugin 提供中间层：

```text
              db-safety Plugin（可版本化的外部产物）
                  ├── run_query Tool
                  └── before_tool_call Hook
                              │
               HarnessBuilder.install / .plugin
                              │  构建期累积
                     Agent Core 固定协议
                              │
                         真实 DB 后端
```

这条结构让“机制”和“策略”各归其位：Core 只保证 Tool 与 Hook 的执行契约；Plugin 表达可复用策略；
数据库客户端、凭证、网络和数据仍属于外部依赖。

## Runtime/Senza 架构映射

### Runtime Rust Plugin：四类贡献

Runtime 的 `Plugin` trait 可以贡献：

| 贡献 | 作用 |
| --- | --- |
| tools | 扩展模型可选择的观察/动作接口 |
| hooks | 在 14 个固定生命周期边界提供策略 |
| skills | 提供按需加载的操作知识或流程说明 |
| templates | 提供可复用 Prompt 模板 |

四个注册方法都有空的默认实现，所以一个 Plugin 可以只贡献其中一类，也可以同时贡献多类。Plugin
名称主要用于标识和诊断；真正影响运行的是它注册到 Builder 的贡献。

### Senza Python Plugin：当前只开放两类贡献

Senza 的 `create_plugin(name, tools=None, hooks=None)` 当前只接受 **tools 与 hooks**。实现位于
[`Senza/src/lib.rs`](../../src/lib.rs)和
[`Senza/src/core/pyplugin.rs`](../../src/core/pyplugin.rs)。Python `PyPlugin` 会先按 HookKind
分类，Builder 安装时再把它们追加到相应 `HarnessHooks` 向量。

这不意味着 Runtime Plugin 只有两种能力。Rust 内置 Plugin 仍可实现 skills/templates；只是
Python `create_plugin()` 这条公开构造路径没有让调用者直接传入这两项。文档和应用代码必须把
“底层协议能力”与“当前 Python 工厂参数”分开表述。

### Builder：构建期收集与校验

Runtime `HarnessBuilder` 的
`install()` 依次调用四个 `register_*` 方法，把贡献追加到 Builder。Senza
[`HarnessBuilder.plugin()`](../../src/core/pybuilder.rs)只是对这条 Rust 安装路径的 Python
封装。

因此 Plugin 的生命周期是：

```text
定义 Plugin → 交给 Builder → 累积贡献 → build 校验 → 形成 Harness
```

一旦 Harness 已构建并开始运行，当前公开 API 不把 Plugin 当作任意增删的热模块。要改变装配，
应重新构建 Harness 或在更高层创建新的 step runner。

## Plugin 可以随意组合吗

简短答案是：**可以组合，但不可以无条件、无顺序、无冲突地组合。** 判断兼容性至少要看四组
契约。

### 1. Hook 组合契约

Plugin A 与 B 可以向同一 Hook 槽位贡献实现，但结果遵循第 2 章的 Composite 语义。例如两个
`after_tool_call` 可以链式处理；两个 `before_tool_call` 会在首个 Modify/Deny 处短路。安装顺序
就是注册顺序，因此也是行为的一部分。

### 2. Tool 名称契约

`install()` 本身只追加，不去重。正式 `build()` / `build_with_session()` 会检查 Tool 名：重复名或
框架保留名导致构建错误，不采用“后注册覆盖前注册”，也不会把冲突留到 dispatch 时随机选择。

这意味着独立团队开发 Plugin 时，应把 Tool 名当作共享命名空间，并把冲突测试放在组合验收中。
Plugin 自身的 `name` 重复当前不会阻止安装，但会使诊断混乱，也应保持唯一。

### 3. Skill 与 template 契约

Rust Plugin 安装时会保留贡献的 skill/template，Harness 构建阶段按名称去重并采用先注册者优先。
Plugin 安装路径不会像目录加载路径那样发出重复名称警告。因此“构建成功”不代表后注册的同名
内容已经生效；这也是顺序必须被文档化的原因。

### 4. 运行依赖契约

两个 Plugin 即使名称与 Hook 均不冲突，也可能依赖不同身份、Store、Environment 或外部 SDK。
Builder 不会自动下载包、启动数据库或推断租户上下文。接口能组合，只说明 Runtime 可以连接这些
对象，不说明所需基础设施已经存在。

## “前置依赖”到底指什么

Runtime `Plugin` trait 没有统一的依赖声明、拓扑排序或自动注入容器。源码文档明确要求 Plugin
自行说明依赖，并由调用方负责注册顺序。因此“前置依赖”是一个工程总称，可能包含以下四类。

| 依赖类型 | 例子 | 谁来提供 | 是否一定是另一个 Plugin |
| --- | --- | --- | --- |
| 构造依赖 | Provider client、`ExecutionEnv`、Store、Authorizer | 应用在 Builder 或 Plugin factory 中传入 | 否 |
| 上下文依赖 | tenant/principal、RunRequest extension、当前项目状态 | 应用入口或上游 Hook | 否；也可能由 Plugin 注入 |
| 后端基础设施 | 数据库、搜索索引、凭证、Python/Rust SDK | 部署环境与应用 | 否 |
| 能力/顺序依赖 | 认证 Hook 必须早于业务 Tool policy，结果过滤先于来源标签 | Plugin 装配者 | 可能是另一个 Plugin |

“需要某个包”只是其中一种情况。包可能已经是 Senza 的编译依赖，也可能需要应用额外安装；是否
存在不能只从 Plugin 名字判断，应查看该 Plugin 的构造函数、callback 捕获对象和部署说明。

### 如果 Plugin 需要 Harness 没定义过的元素

先判断它属于哪一类：

1. **新的外部能力**：把数据库客户端、HTTP client 或 Store 放在 Tool/Hook 实现内部，由 Plugin
   在构造时持有；Core 只通过已有 trait 调用，不必理解后端具体类型。
2. **新的每次 run 数据**：若已有 Hook ctx 或 `RunContext` extension 能表达，可由应用在请求入口
   注入，Rust Hook 按约定读取。Python callback 当前只能看到 Senza 明确转换到 dict 的字段，不能
   假设任意 Rust extension 自动暴露。
3. **新的上下文内容**：可用 `before_run` 或 `transform_context` 在现有边界注入，但要遵守数据权限
   与上下文预算。
4. **全新的生命周期时机或控制流**：这不是普通 Plugin 可以自行发明的。必须修改 Runtime trait、
   `HarnessHooks`、Core 调用点、Composite 语义和测试，然后再由 Senza 暴露。

判断原则是：能封装在现有 Tool/Hook 协议后的业务对象，不必进入 Core；只有稳定、跨场景且现有
边界无法表达的生命周期能力，才值得扩展 Core。

## 两种挂载作用域

### Agent scope

`HarnessBuilder.plugin(plugin)` 将 Plugin 贡献装到这个 Builder，构造出的 Agent 在其 run 中共享
这些 Tool/Hook。适合整个 Agent 都需要的能力，例如统一数据库安全、审计或文件工具。

### Workflow step scope

`WorkflowEngine.with_step_plugin(step_id, plugin)` 只为指定 step 的 Harness 安装 Plugin。Senza
适配位于 [`pyworkflow.rs`](../../src/runtime/pyworkflow.rs)，底层 Runtime 在执行该 step 时创建
Builder、调用 Plugin factory 并安装贡献。其他 step 不会因为这次注册自动获得相同 Tool/Hook。

step scope 的价值是最小权限：查询 step 可以拥有 `run_query`，总结 step 只处理已有结果，不必
继续暴露数据库动作。它改变的是**能力作用域**，不是 Hook 的生命周期位置；`before_tool_call`
仍然是 Core 定义的同一个固定槽位。

还要注意，Workflow step 运行时会构建自己的 Harness，但这不自动保证 Plugin 内部状态隔离。
底层会调用 step factory；Senza 适配器会克隆传入 Plugin 的 `Arc`，因此 callback 闭包捕获的可变
对象可能跨同一 step 的多次执行共享。Harness 作用域、Plugin 对象生命周期和数据库事务边界是
三件不同的事，应由应用显式设计。

## 一条完整执行故事：DB Safety Plugin

下面用配套实验的三条 SQL 讲清构建、组合和执行边界。

### 1. 定义真实动作与确定性策略

`run_query` Tool callback 代表数据库 executor。`db_guard` 则是纯策略函数，只关注工具名和结构化
参数：

- 有界 SELECT：Allow；
- 无界 SELECT：Modify，把 SQL 改为 `... LIMIT 100`；
- 非 SELECT：Deny，返回可给模型观察的脱敏失败。

策略使用结构化参数，而不是检查模型最后生成的自然语言。这样门禁位于真实动作之前，不会因为
模型“承诺只读”就放行危险 SQL。

### 2. 把 guard 包装到固定 Hook

Senza 用 `senza.hooks.before_tool_call(query_guard)` 创建 Hook。这个 Hook 只能在 Core 的
`before_tool_call` 槽位运行；它不能选择“数据库驱动内部执行到第三行时”插入。

### 3. 创建 Plugin 并安装

`create_plugin(name="db-safety", tools=[query_tool], hooks=[guard_hook])` 将 Tool 和 Hook 打包。
应用可以选择 `.plugin(...)` 作为 Agent scope，也可以 `.with_step_plugin("query", ...)` 限定为
Workflow 的查询 step。Builder 在构建时展开贡献并检查 Tool 名冲突。

### 4. Model 提出有界 SELECT

Core 匹配到 `run_query`，Tool 包装层先调用 guard。返回 Allow 后，executor 收到原始 SQL。Hook
本身不执行数据库查询，它只决定是否把控制权交给 callback。

### 5. Model 提出无界 SELECT

guard 返回 Modify 和新参数。Runtime 使用修改后的参数执行 Tool，因此 executor 只看到带
`LIMIT 100` 的 SQL。原始请求仍可保留在审计上下文中，但不能把“模型提出了什么”和“后端实际
执行了什么”混为一谈。

### 6. Model 提出 DROP

guard 返回 Deny。Runtime 生成结构化 ToolFailure 给模型作为 Observation，executor 不运行。
模型可以据此解释拒绝原因或选择其他安全动作。

### 7. 纵深防御仍然需要后端

教学 guard 用正则表达式，可能被注释、嵌套语句、方言差异等绕过。生产系统还必须使用只读数据库
凭证、事务权限、真正的 SQL parser、超时和结果行数限制。Plugin 是策略载体，不是对后端安全的
替代。

## 源码导读：Plugin 从 Python 到 Builder

### 1. Rust 协议

Runtime Plugin 协议定义 `name()` 与四个 `register_*` 方法，并明确记录安装顺序与冲突处理。
协议没有 `start()` 或 `hot_reload()`，也没有自动依赖解析。

### 2. Runtime 安装

Runtime Builder 的 `install()` 按 tools、hooks、skills、templates 次序调用 Plugin，但每类贡献
内部仍按 Plugin 注册顺序追加。`resolve_and_build()` 在返回 Harness 选项前调用 Tool 名冲突检查。
这解释了为什么冲突是构建错误，而不是模型真正调用时才暴露。

### 3. Python 工厂与适配

[`Senza/src/lib.rs`](../../src/lib.rs)的 `create_plugin()`只接收 Tool wrapper 和 Hook wrapper。
[`pyplugin.rs`](../../src/core/pyplugin.rs)把 HookKind 分发到 12 个向量，并实现 Runtime Plugin 的
`register_tools()` / `register_hooks()`。

[`pybuilder.rs`](../../src/core/pybuilder.rs)的 `.plugin()`调用底层 `install()`；`.build()` 消费
Builder 后构造 Harness。`HarnessBuilder(pending)` 变成 consumed 之后，不存在对同一 Builder
继续热安装的正常路径。

### 4. Workflow step scope

[`Senza/src/runtime/pyworkflow.rs`](../../src/runtime/pyworkflow.rs)用 `PyPluginAdapter` 把 Python
Plugin 交给底层 step Plugin factory。Runtime 只在命中当前 `step.id()` 的 factory 时安装 Plugin，
然后再构造该 step 的 Harness。这是作用域隔离的源码依据。

### 5. Python `before_tool_call` 决策

[`pyhooks.rs`](../../src/core/pyhooks.rs)把 Python 的 `"allow"`、Modify dict 和 Deny dict 解析
成 Runtime 决策。callback 抛错或线程 join 失败时，该适配器 fail-closed 为 Deny。这个默认有助于
安全，但业务仍应记录和告警 Hook 自身故障，避免把策略错误误判为正常拒绝。

## 配套实验

实验位于 [`academy/labs/03_plugin_db_safety`](../../academy/labs/03_plugin_db_safety/)。

### 第一步：运行无 Provider 的真实 guard

```powershell
python academy/labs/03_plugin_db_safety/demo.py
```

recorded runner 会真正调用 `db_guard()`，依次得到 Allow、Modify、Deny，并用模拟 executor 记录
有效 SQL。检查输出应满足：executor 收到两条查询；第二条带 `LIMIT 100`；DROP 不在执行列表中。

这里“真实”的范围只到纯 Python 策略和模拟 executor。脚本没有导入 Senza，也没有构建 Plugin 或
Harness，因此不能据此宣称 Runtime 已分派 Hook。

### 第二步：运行离线验收

```powershell
python -m pytest academy/labs/03_plugin_db_safety/test_demo.py -q
```

测试直接断言三种返回形状、修改后的 SQL、拒绝项未执行，以及 README 对构建期、两种作用域和
Python 能力边界的描述。若你修改 guard，应同时为“该改变的 SQL”和“不该改变的 SQL”补测试。

### 第三步：运行 live Plugin 链路

```powershell
python academy/labs/03_plugin_db_safety/demo.py --mode live
```

live 模式委托
[`live-tests/examples/32_plugins.py`](../../live-tests/examples/32_plugins.py)。它演示：

- Python `create_plugin()` 打包同步/异步 Tool 与 Hook；
- `HarnessBuilder.plugin()` 的 Agent scope；
- `WorkflowEngine.with_step_plugin()` 的 step scope；
- 无界查询被修改、DROP 在 executor 前被拒绝。

模型是否严格按提示发起一次调用仍可能受 Provider 行为影响，所以请同时查看 `guard_decisions` 和
`executed_queries`，不要只读最终自然语言。

### 第四步：做一次组合审查

为 DB Safety 再设计一个“审计 Plugin”，在 `before_tool_call` 记录请求。然后回答：

1. 审计 Plugin 应装在 DB Safety 前还是后，才能记录被 Modify/Deny 的原始请求？
2. 若它返回 Allow，是否影响安全决策？
3. 若它意外返回 Modify，后面的 DB Safety 是否还会执行？
4. 两个 Plugin 若都贡献 `run_query`，错误在 install 还是 build 暴露？

这个练习比简单地“再加一个 Plugin”更接近生产组合审查。

## 常见误解与能力边界

### 误解一：Plugin 是运行时插件系统

当前 Plugin 是构建期协议。它把贡献安装到 Builder，再构造 Harness。名字叫 Plugin 不代表支持
动态卸载、热更新、独立进程隔离或版本解析。

### 误解二：Plugin 可以创造任意 Hook 位置

Plugin 只能把实现注册到 Core 已定义的 14 个槽位。它可以贡献多个 Hook，却不能要求 Core 在任意
源码行回调。如果没有合适槽位，要么把行为封装在 Tool/后端内部，要么正式扩展 Runtime 契约。

### 误解三：前置依赖一定是另一个 Plugin

前置依赖可能是 Provider、Store、Environment、身份上下文、SDK 包或外部服务。另一个 Plugin
只是其中一种。Runtime 当前不会自动检测、安装或排序这些依赖。

### 误解四：后安装会覆盖重名 Tool

不会。正式 Harness build 拒绝重复和保留 Tool 名。依赖覆盖行为会使应用无法构建，应显式改名、
协调共享 Tool，或重新划分能力边界。

### 误解五：Python Plugin 与 Rust Plugin 完全等价

Python `create_plugin()` 当前只开放 tools/hooks；Rust trait 还能贡献 skills/templates。Senza 也能
包装某些 Rust 内置 Plugin，但这不等于 Python 工厂突然获得四个参数。

### 误解六：一个正则 Hook 就能保护数据库

Hook 能在 Harness 边界阻断明显危险调用，但生产安全必须依靠数据库最小权限、网络隔离、事务与
语法级校验形成纵深防御。若数据库凭证本身可以删除所有表，单层正则不是可靠安全边界。

### 能力边界

- Plugin 安装顺序由调用者负责，Runtime 不做依赖拓扑排序或兼容性求解；
- Hook 组合结果遵循各自 Composite 语义，并非所有贡献都会执行到底；
- Tool 冲突在 build 路径检查；Plugin 名重复当前不会自动拒绝；
- Agent scope 与 step scope 控制作用范围，不改变 Hook 类型和 Core 调用位置；
- Python callback 需要的外部包、客户端、凭证和服务由应用/部署环境提供；
- recorded DB guard 不证明 Senza 构建、Provider 决策或 Hook dispatch，live 与 Runtime 测试才提供
  对应证据；
- 本章 DB guard 是教学策略，不是生产 SQL parser。

## 小结

Plugin 让团队把已验证的 Tool、Hook 及 Rust 侧的 Skill/Template 组合成可复用外部产物。它之所以
容易添加，不是因为能侵入任意位置，而是因为 Builder、14 个 Hook 与 Tool trait 提供了稳定协议。
组合是否安全取决于 Hook 代数、注册顺序、名称空间、作用域和外部依赖；“能装上”只是兼容性的
第一步。

## 复习题

1. Plugin 与 Hook 的区别是什么？一个 Plugin 可以不包含 Hook 吗？
2. Rust Plugin 与 Python `create_plugin()` 分别能贡献哪些能力？
3. 两个 Plugin 都注册同名 Tool 时，为什么选择构建时报错而不是后注册覆盖？
4. 举例说明四种前置依赖，并指出其中哪些可能由另一个 Plugin 提供。
5. `HarnessBuilder.plugin()` 与 `WorkflowEngine.with_step_plugin()` 的核心差异是什么？
6. DB Safety 的 Modify 为什么必须发生在 executor 之前？Deny 结果为什么仍要返回模型？
7. 如果新需求是“每次 Tool callback 内部数据库事务提交前检查行数”，应优先放在 Hook、Tool/后端，
   还是新增 Core Hook？请说明判断依据。
8. 一个审计 Hook 必须看见所有原始调用，而安全 Hook 可能短路。你会怎样设计它们的组合与测试？

## 延伸阅读

- 理论坐标：[《动手学 AI Agent》第 1 章](https://github.com/bojieli/ai-agent-book/blob/1d2e04ee733dde245af2eb718cfc92d2d0542b7e/book/chapter1.md)中的外部产物、
  Harness 工程与安全边界；
- Academy 实验：[`Lab 03 README`](../../academy/labs/03_plugin_db_safety/README.md)；
- Python live 示例：[`32_plugins.py`](../../live-tests/examples/32_plugins.py)；
- 架构总览：[Academy 架构导读](../architecture.md)；
- 能力边界汇总：[Academy 能力边界](../capability-boundaries.md)。
