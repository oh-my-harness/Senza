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
3. 模型：`SENZA_LIVE_MODEL`（默认 `DeepSeek-V4-Flash`）
4. base：`OPENAI_API_BASE`（默认 `http://api.hyper-op.com/v1`）

无任何 key 时所有真实测试 `pytest.skip`，不失败。

## 分层

- `test_agent_layer.py` — basic / async streaming / tool / hooks / config / skills / branch / compaction
- `test_loop_layer.py` — tool dispatch / multi-turn / provider error
- `test_tools_layer.py` — fs tools / grep-glob / knowledge RAG / session recall
- `test_runtime_layer.py` — builder workflow / recovery / executors / composite judge / audit-trace / sandbox
- `test_strategy_layer.py` — safety / injection / loop-safety / status-panel / memory-defense / source-tag / notify / context-compact

每个层文件含一个不依赖 key 的 `test_*_constructs_offline`，用于无 key 时验证 API 签名。

设计见 `docs/superpowers/specs/2026-08-12-senza-live-tests-design.md`。

## 可运行示例

全部可运行示例统一在 [`examples/`](examples/)（23 个运行时同名镜像 `01`–`23` + 17 个
仓库根迁入示例 `30`–`46`）。仓库根 `examples/` 目录已废弃删除。每个示例驱动真实 LLM，
无 key 时打印 SKIP 并 exit 0。可逐个跑，也能与 `llm-harness-runtime` 同名示例在同一
DeepSeek 端点 1:1 对照（写规范见 `examples/_AUTHORING.md`，目录说明见 `examples/README.md`）。
