# Senza 真实 LLM 集成测试套件 — 设计

> 日期：2026-08-12 · 分支：test · 状态：approved

## 背景

Senza 的系统测试（`tests/`）基于 mock（`MockLlmClient` / test-utils），不碰真实 LLM。
`examples/` 里的真实 LLM 示例对 API 的覆盖不完整，且 strategy/knowledge 类示例只构造
harness、从不驱动一个真实回合（全部 `phase: idle` 即退出）。

runtime 仓库已有成熟的真实 LLM 测试惯例 `crates/llm-harness-live-tests/`
（独立 crate、`live-llm` feature、`skip_if_none!`、按层组织、弱内容断言、分级超时、
CLAUDE.md 铁律：失败先调查、禁止无脑 ignore）。本设计在 Senza（PyO3 Python SDK）上
**忠实镜像同一套模式**，并默认打当前 OMP 使用的 DeepSeek 端点。

## 目标

为 Senza 建一套按架构层组织的、可本地运行的**真实 LLM 集成测试**：

1. 覆盖现有 `examples/` 未驱动的 API 盲区（尤其 strategy + knowledge 需被真实回合驱动）
2. 无 API key 时优雅 skip（任何人本地可跑，不影响默认测试套件）
3. 每个层文件带一个离线构造冒烟，无 key 也能验证 API 调用签名
4. 默认打 OMP DeepSeek 端点，可通过 env 覆盖

## 非目标

- 不串 CI（本期不做，目录结构预留）
- 不重写 runtime 的 live-tests（那是 Rust crate，Senza 是 Python SDK）
- 不追求 LLM 输出断言的具体内容（弱断言）

## 已确认决策（用户拍板）

| 维度 | 决策 |
|------|------|
| 层覆盖 | 全量镜像 runtime（agent / loop / tools / runtime / strategy 五层） |
| 位置 | 独立 `live-tests/` 目录，不进 `tests/`，不进默认 pytest |
| CI | 暂不串（目录预留） |
| Provider | 默认 OMP DeepSeek（openai-completions，`http://api.hyper-op.com/v1`，`DeepSeek-V4-Flash`） |
| Dedup | 只删纯构造 demo：`examples/strategy/*.py`(12) + `examples/knowledge/*.py`(3) |
| 验证 | 构建后**全量实跑** DeepSeek-V4-Flash |

## 架构

```
live-tests/
  base.py          # 助手：provider_from_env / provider_or_skip、make_harness、run_prompt、
                   #   with_timeout、事件断言、分级超时、~/.omp_llm_env 兜底
  conftest.py      # live_provider fixture（无 key -> pytest.skip）
  CLAUDE.md        # 哲学（镜像 runtime 铁律）
  README.md        # 运行方式
  test_agent_layer.py    # basic / async streaming / tool calling / hooks / dynamic-config /
                         #   skills_model / session_branch / compaction + 离线构造冒烟
  test_loop_layer.py     # tool_dispatch / multi_turn / provider_error + 离线构造冒烟
  test_tools_layer.py    # fs_tools / grep_glob / knowledge_memory / session_recall + 离线构造冒烟
  test_runtime_layer.py  # builder_workflow / recovery / executor / composite_judge /
                         #   tracing_audit / sandbox + 离线构造冒烟
  test_strategy_layer.py # safety / injection / loop_safety / status_panel / memory_defense /
                         #   source_tag / notify / context_compact + 离线构造冒烟
```

每个层文件含两类测试：
- **真实 LLM 测试**：`provider_or_skip()` 开头，无 key 时 `pytest.skip`，有 key 时驱动真实回合。
- **离线构造冒烟**（1 个/层，不 skip）：用 `providers.openai(api_key="sk-test")` 构造该层所有
  harness / engine / plugin 对象并断言非 None —— 无 key 也能捕捉 API 签名错误。这补上
  「无 key 无法验证 API 用法」的盲区。

## Provider 配置（base.py）

默认链（优先级由高到低）：
1. env：`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`、`OPENAI_API_BASE`、`SENZA_LIVE_MODEL`
2. 兜底：无 key 时载入 `~/.omp_llm_env`（`export OPENAI_API_KEY/BASE/MODEL`）

默认值（OMP DeepSeek）：
- base_url = `http://api.hyper-op.com/v1`
- model = `DeepSeek-V4-Flash`
- 构造 provider：`senza.providers.openai(api_key=..., base_url=...)`
  （Senza 默认 `parse_reasoning_content=True + tolerant_keepalive=True`，DeepSeek reasoning 必需）

分级超时（ms）：SMOKE=30_000，SINGLE_TURN=60_000，MULTI_TURN=120_000。

## 事件断言基础

`prompt_and_collect` / `stream_prompt` 返回 event dict，字段（已核对 `src/shared/event_stream.rs`）：
- 终态：`settled` / `aborted` / `error`
- tool：`tool_call_start`（含 `tool_name`）、`tool_call_end`、`tool_execution_start`（含 `tool_name`）
- 文本：`text_delta`（含 `text`）

base.py 提供 `assert_tool_called(events, name)`、`assert_settled(events)`、`assert_no_error(events)`
等弱断言。

## Dedup

删除以下纯构造 demo（新 live-tests 会真实驱动其场景）：
- `examples/strategy/*.py` — 12 个（全部 0 次真实回合）
- `examples/knowledge/*.py` — 3 个（全部 0 次真实回合）

保留：`examples/agent/*`、`examples/runtime/*`、`examples/infra/*`（文档展示价值）。

删除后需同步：`README.md` 的 examples 计数与描述、`docs/api-reference.md` 若引用、
`SENZA_DESIGN.md` 缺口表若计数。实际删除由实现计划逐条核对引用后执行。

## 验证

1. **离线**：无 key 运行 `pytest live-tests/` → 全部真实测试 skip、构造冒烟通过（0 error）。
2. **真实全量**：带 key 运行 `pytest live-tests/` → 全部真实 LLM 测试对 DeepSeek-V4-Flash 通过。
3. 确认默认 `pytest tests/`（437 个）不受影响（live-tests/ 不在其路径内）。

## 风险

- 真实 LLM 测试天然 flaky / 有成本：用弱断言、合理超时、必要时允许单测隔离重跑。
- `~/.omp_llm_env` 是 OMP 会话产物：仅作为无 key 时的兜底，不把真实 key 写进仓库。
- 删除 examples 会影响 README/设计文档计数：按引用逐条更新。
