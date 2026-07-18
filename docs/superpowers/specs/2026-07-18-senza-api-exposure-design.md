# Senza API 暴露补齐设计

> 日期：2026-07-18
> 主题：runtime 仓库 API 暴露给 Python 的 gap 分析与补齐方案
> 范围：Senza PyO3 SDK（`src/*.rs`）补齐缺失的 Rust→Python 绑定

---

## 1. 背景

Senza 是 oh-my-harness runtime 的 Python SDK，基于 PyO3 把 Rust runtime crate 的能力暴露给 Python。当前已覆盖 `AgentHarness`（37 方法）、`WorkflowEngine`（27 方法）、`HarnessBuilder`（13 方法）、11 种 hook、Tool/Plugin/Provider/Judge/Executor、event channel。

但 runtime 仓库的 `HarnessBuilder` 有 25+ 个 setter，Senza 只暴露了 13 个；此外还有 Budget 控制、Rules 审批、Skills 加载、Pricing 注入等子系统完全未暴露。本文档分析缺口并给出补齐方案。

## 2. 目标

- 补齐 `HarnessBuilder` 缺失的 setter，使 Python 侧与 Rust builder 对齐
- 暴露 Budget 控制、Pricing、Rules 审批、Skills 加载子系统
- **不暴露**平台层（Sandbox/MCP/Audit/Trace/ResourceProvider/PromptSource）——后续有需要再议
- **不暴露**轻量 `Agent` 类（test-utils only，定位是 mock）
- **不暴露** `ConvertToLlmHook`（Python 侧已有 `TransformContextHook` 覆盖等价场景）

### 判断原则

按 Rust builder 对齐：Rust `HarnessBuilder` 上已有的 setter，Senza 缺的都补上；其余独立子系统按"能否通过 builder 端到端用起来"决定。不追求 Pythonic DSL 封装，保持与 Rust API 一一对应。

## 3. 覆盖现状

### 已覆盖

| Senza | Rust | 状态 |
|-------|------|------|
| `HarnessBuilder` 13 方法 | `HarnessBuilder` 25+ setter | 缺 12 个 setter |
| `AgentHarness` 37 方法 | `AgentHarness` ~40 方法 | 基本对齐 |
| `WorkflowEngine` 27 方法 | `WorkflowEngine` ~20 方法 | 已超集（Python 侧加了便利方法） |
| 11 hooks | 11 hook traits | 完整 |
| Tool/Plugin/Provider/Judge/Executor | 对应 trait | 完整 |
| `create_event_channel` | `WaitForExternalEventTool` | 完整 |

## 4. 缺口与暴露设计

### G1: Budget 控制

**Rust 来源**：`builder.budget(limit: f64, exceeded_hook: Option<Arc<dyn BudgetExceededHook>>)` + `BudgetControlAdapter`（impl `ShouldStopHook`）+ `BudgetExceededHook` trait。

**暴露**：

```python
# builder 方法
HarnessBuilder.budget(limit: float, exceeded_hook: Optional[BudgetExceededHook] = None) -> HarnessBuilder

# hook 工厂
create_budget_exceeded_hook(callback: Callable[[dict, float], bool]) -> BudgetExceededHook
```

- `callback(cost: dict, limit: float) -> bool`：`True` 继续，`False` 停止。`cost` dict 对应 `CostAggregate`（`total_cost`、`by_model` 等）。
- `exceeded_hook=None` → surveillance 模式，只统计不停。
- 支持 `async def` callback。

**Pythonic 程度**：裸绑定。`callback` 签名与 Rust trait 对齐，`CostAggregate` 转 dict 复用现有 `value_conv`。

### G2: PricingProvider

**Rust 来源**：`builder.pricing(Arc<dyn PricingProvider>)` + `PricingProvider::price_for(&self, model: &str, provider: &str) -> Option<TokenPrice>`。

**暴露**：

```python
# builder 方法
HarnessBuilder.pricing(provider: PricingProvider) -> HarnessBuilder

# 从 dict 构造（静态定价表，覆盖 90% 用例）
create_pricing_provider(table: dict[str, dict]) -> PricingProvider

# 从 callback 构造（动态定价）
create_pricing_provider_callback(callback: Callable[[str, str], Optional[dict]]) -> PricingProvider
```

`table` 格式：

```python
{
    "gpt-4o": {
        "input_per_mtok": 2.5,
        "output_per_mtok": 10.0,
        "cache_read_per_mtok": 1.25,
        "cache_write_per_mtok": 2.5,
    },
}
```

- `create_pricing_provider(table)` 内部实现 `PricingProvider` trait，`price_for` 做 dict lookup。
- `create_pricing_provider_callback(cb)` 给动态定价场景。`cb(model, provider)` 返回 dict 或 `None`。
- 设置后 `builder` 自动注入 `CostAccumulatorHook`，`harness.usage()["total_cost"]` 才有值。

**Pythonic 程度**：裸绑定 + dict 构造便利函数。不暴露 `TokenPrice` 为 `#[pyclass]`——dict 足够。

### G3: Rules 审批系统

**Rust 来源**：`RuleChain` + `RuleChainBuilder` + `RuleBasedApprovalHook`（impl `BeforeToolCallHook`）+ 4 个 Predicate（`Contains`/`NumberRangeField`/`RegexField`/`RateLimit`）+ `Rule`/`Decision`。

**暴露**：

```python
# Predicate 构造函数
create_contains_predicate(allowed: list[str]) -> Predicate
create_regex_field_predicate(arg_path: str, pattern: str) -> Predicate
create_number_range_predicate(arg_path: str, min: float, max: float) -> Predicate
create_rate_limit_predicate(max: int, window_seconds: float) -> Predicate

# RuleChain builder
create_rule_chain() -> RuleChainBuilder
RuleChainBuilder.rule(tool_name: str, predicate: Predicate, on_match: str) -> RuleChainBuilder
RuleChainBuilder.fallback(decision: str) -> RuleChainBuilder
RuleChainBuilder.build() -> RuleChain

# Hook 工厂
create_rule_approval_hook(chain: RuleChain) -> Hook
```

- `on_match` / `decision` 用字符串 `"allow"` / `"deny"`（对应 Rust `Decision` enum）。
- `tool_name` 支持 `"*"` 通配（Rust 已有语义）。
- `RuleBasedApprovalHook` impl `BeforeToolCallHook`，产出的 `Hook` 走 `builder.hooks([hook])` 通路（G6 补 `hooks()` 方法）。注意：`should_stop_hook()` 接的是 `ShouldStopHook`，类型不匹配，不能用于注册 `BeforeToolCallHook`。

**Pythonic 程度**：裸绑定 + builder 链式。`Predicate`/`RuleChain`/`RuleChainBuilder` 都是 opaque `#[pyclass]`（无方法暴露，只作 handle 传递）。

### G4: Skills 加载

**Rust 来源**：`Skill` struct + `load_skills(path)` 函数 + `builder.skills` 字段。

**暴露**：

```python
# 从目录加载
load_skills(path: str) -> list[Skill]

# builder 方法
HarnessBuilder.skill(skill: Skill) -> HarnessBuilder
HarnessBuilder.skills(skills: list[Skill]) -> HarnessBuilder
```

- `load_skills(path)` 扫描目录下的 `SKILL.md` 文件，返回 `list[Skill]`。
- 设置 skill 后 `build()` 自动注册 `SkillReadTool`（Rust 侧 `inject_skill_read_tool` 已有逻辑）。
- `Skill` 为 opaque handle，加载即不可变。

### G5: Compaction model

**Rust 来源**：`builder.compaction_model(model: impl Into<String>, model_info: ModelInfo)`。

**暴露**：

```python
HarnessBuilder.compaction_model(
    model: str,
    context_window: int,
    max_tokens: int,
) -> HarnessBuilder
```

- 把 `ModelInfo` 拆成两个参数，不暴露 `ModelInfo` pyclass。

### G6: 其余 builder setter

| Rust 方法 | Python 方法 | 参数映射 |
|-----------|-------------|----------|
| `should_stop_hook(hook)` | `should_stop_hook(hook: Hook)` | 直接传 `Hook` handle |
| `hooks(hooks)` | `hooks(hooks_list: list[Hook])` | list of Hook handles |
| `retry(config)` | `retry(max_retries: int, base_delay_ms: int)` | `RetryConfig` 拆参 |
| `model_info(info)` | `model_info(context_window: int, max_tokens: int)` | 展平 |
| `final_answer_mode(mode)` | `final_answer_mode(mode: str)` | `"heuristic"` / `"tool"` |
| `convert_to_llm(converter)` | ❌ 不暴露 | Python 侧 `TransformContextHook` 已覆盖 |
| `stream_options(opts)` | `stream_options(timeout_ms: Optional[int], max_retries: Optional[int])` | `StreamOptions` 拆参（其余字段需 provider adapter 支持，暂不暴露） |
| `queue_capacity(cap)` | `queue_capacity(capacity: Optional[int])` | 直接传 |
| `disable_skill_read_tool()` | `disable_skill_read_tool()` | 无参 |

## 5. 文件改动

| 文件 | 改动 |
|------|------|
| `src/pybuilder.rs` | 补 12 个方法：`budget`/`pricing`/`skill`/`skills`/`compaction_model`/`should_stop_hook`/`hooks`/`retry`/`model_info`/`final_answer_mode`/`stream_options`/`queue_capacity`/`disable_skill_read_tool` |
| `src/pybudget.rs`（新建） | `PyBudgetExceededHook` wrapper + `create_budget_exceeded_hook()` |
| `src/pypricing.rs`（新建） | `PyPricingProvider`（dict 表）+ `PyPricingProviderCallback`（callback）+ `create_pricing_provider()` / `create_pricing_provider_callback()` |
| `src/pyrules.rs`（新建） | `PyPredicate`/`PyRuleChain`/`PyRuleChainBuilder` wrapper + 4 个 predicate 工厂 + `create_rule_chain()` + `create_rule_approval_hook()` |
| `src/pyskills.rs`（新建） | `PySkill` opaque wrapper + `load_skills()` |
| `src/lib.rs` | 注册新增的 class + function |
| `senza-pkg/senza/__init__.pyi` | 补所有新签名 |
| `README.md` | API 速查表补新方法 |
| `SENZA_DESIGN.md` | 缺口表标记已补；§7 编排能力总览补行 |

## 6. 测试

每个缺口至少一个 Python 测试，放在 `tests/` 下：

| 测试文件 | 覆盖 | 验证点 |
|---------|------|--------|
| `tests/test_budget.py` | G1 | `builder.budget(5.0)` 构建成功；`create_budget_exceeded_hook(cb)` 回调被调用且 `True`/`False` 影响流程；surveillance 模式（`None`）不停止 |
| `tests/test_pricing.py` | G2 | `create_pricing_provider(table)` 设置后 `harness.usage()["total_cost"] > 0`；callback 版本返回 `None` 时不 crash |
| `tests/test_rules.py` | G3 | `Contains` predicate 放行/拒绝；`RegexField` 匹配；`RateLimit` 窗口内放行超限拒绝；`RuleChain` fallback 生效；hook 注册到 harness 后 tool call 被拦截 |
| `tests/test_skills.py` | G4 | `load_skills(tmp_path)` 加载 `SKILL.md`；`builder.skill(s)` 构建成功；`disable_skill_read_tool()` 后无 `SkillReadTool` |
| `tests/test_compaction_model.py` | G5 | `builder.compaction_model("gpt-4o-mini", 128000, 16384)` 构建成功 |
| `tests/test_builder_setters.py` | G6 | `retry`/`model_info`/`final_answer_mode`/`stream_options`/`queue_capacity`/`should_stop_hook`/`hooks`/`disable_skill_read_tool` 各一个构建冒烟测试 |

### 测试原则

- 用 `MockLlmClient`（test-utils feature）驱动，不依赖真实 LLM API。
- Budget/Pricing 测试需发一轮 prompt 让 `CostAccumulatorHook` 累积数据，用 mock provider 返回固定 response。
- Rules 测试用 mock tool 验证 `BeforeToolCallHook` 拦截链路。
- Skills 测试用 `tmp_path` 构造临时 `SKILL.md` 文件。
- 全部不联网，可离线运行。

## 7. stub 校验

新增的 `#[pyfunction]` 和 `#[pymethods]` 都要加 `#[pyo3(text_signature = "...")]`，更新 `senza-pkg/senza/__init__.pyi` 后跑 `python scripts/check_stubs.py` 确保零偏差。

## 8. 不做的事

- 不暴露平台层（Sandbox/MCP/Audit/Trace/ResourceProvider/PromptSource）。
- 不暴露轻量 `Agent` 类。
- 不暴露 `ConvertToLlmHook`。
- 不做 Pythonic DSL 封装层（如 `RuleChainBuilder.allow().deny()` 链式 DSL）——保持与 Rust API 对齐。
- 不改现有方法签名。

## 9. 优先级

| 缺口 | 优先级 | 依赖 |
|------|--------|------|
| G6 其余 setter（含 `should_stop_hook`/`hooks`） | P1 | 无 — G3 的 hook 注册通路依赖此 |
| G1 Budget | P1 | 无 — `budget()` 自带 `ShouldStopHook` 注入，不依赖 G6 |
| G2 Pricing | P1 | 无 |
| G3 Rules | P1 | G6（`hooks()` 方法） |
| G4 Skills | P2 | G6（`disable_skill_read_tool`） |
| G5 Compaction model | P2 | 无 |

建议实现顺序：G6 → G2 → G1 → G3 → G4 → G5（按依赖关系排序）。
