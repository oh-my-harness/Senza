# Senza Live LLM Tests

按架构层（agent / loop / tools / runtime / strategy）组织的真实 LLM 集成测试，
镜像 `llm-harness-runtime` 的 `live-tests`。默认打当前 OMP 的 DeepSeek 端点
（`http://api.hyper-op.com/v1` + `DeepSeek-V4-Flash`）。

## 运行

```bash
# 无 key —— 真实测试全部 SKIP，离线构造冒烟 (test_*_constructs_offline) 通过
python -m pytest live-tests/ -q

# 带 key —— 真实 LLM 全量跑（当前 OMP DeepSeek）
source ~/.omp_llm_env && python -m pytest live-tests/ -v --timeout=180

# 指定 provider / 模型（env 覆盖）
OPENAI_API_BASE=http://... SENZA_LIVE_MODEL=gpt-4o OPENAI_API_KEY=sk-... \
  python -m pytest live-tests/ -v
```

## Provider 发现

1. `OPENAI_API_KEY`（或 `ANTHROPIC_API_KEY`）env
2. 无 key 时载入 `~/.omp_llm_env`（OMP 会话的 LLM env）
3. 模型：`SENZA_LIVE_MODEL` 显式覆盖；OpenAI-compatible 默认 `DeepSeek-V4-Flash`，
   Anthropic-only 默认 `ANTHROPIC_MODEL` 或 `claude-sonnet-4-20250514`
4. base：`OPENAI_API_BASE`（默认 `http://api.hyper-op.com/v1`）

无任何 key 时所有真实测试 `pytest.skip`，不失败。

## 分层

- `test_agent_layer.py` — basic / async streaming / tool / hooks / config / skills / branch / compaction
- `test_loop_layer.py` — tool dispatch / multi-turn / provider error
- `test_tools_layer.py` — fs tools / grep-glob / knowledge RAG / memory 与 recall 装配契约
- `test_runtime_layer.py` — builder workflow / persistence-replay / executors / composite judge /
  audit hooks / OS env
- `test_strategy_layer.py` — safety / injection / loop-safety / status-panel / memory-defense / source-tag / notify / context-compact

每个层文件含一个不依赖 key 的 `test_*_constructs_offline`，用于无 key 时验证 API 签名。

设计见 `docs/superpowers/specs/2026-08-12-senza-live-tests-design.md`。

## 可运行示例

[`examples/`](examples/) 当前保存 40 个 live/API 示例脚本（23 个运行时同名镜像
`01`–`23` + 17 个原仓库根示例 `30`–`46`）。非隔离 Provider 场景无 key 时由统一入口
结构化跳过；可逐个跑，也能与 `llm-harness-runtime` 同名示例在同一 Provider 端点对照。

在 Academy/live-tests 合并方案中，这个目录将逐步成为 **legacy adapter 与 source pool**，
不再承担“所有示例唯一归宿”的语义。P1 已实现 Catalog、Runner 和 Academy manifest bridge，
但 native scenario adapters、统一 result envelope 和 strict verifier 尚未实现；当前
`run` 仍启动 catalog 指向的 legacy script，直接脚本路径继续兼容：

```bash
# 已实现的 P1 统一入口
python -m examples list
python -m examples describe agent.tool_calling
python -m examples doctor agent.tool_calling
python -m examples run agent.tool_calling
python -m examples course 01 --mode recorded
python -m examples course 01 --mode live

# 当前入口，继续有效
python live-tests/examples/02_tool_calling.py
python -m pytest live-tests/test_agent_layer.py -v
```

`live-tests/` 会继续承担严格行为验证；统一 runner 不会把 layer tests 降级成弱断言 demo。
P1 已为 Academy 提供 `course --mode recorded|live`；它仍没有 `show`、`verify` 或通用的
`run --mode` 子命令。
写规范见 [`examples/_AUTHORING.md`](examples/_AUTHORING.md)，目录说明见
[`examples/README.md`](examples/README.md)，统一设计见
[场景统一计划](../docs/academy/2026-08-21-live-tests-academy-scenario-unification-plan.md)。
