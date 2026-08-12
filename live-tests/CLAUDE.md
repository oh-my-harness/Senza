# Senza 真实 LLM 集成测试 (live-tests)

镜像 `llm-harness-runtime/crates/llm-harness-live-tests` 的惯例。

## 核心原则

**这些测试的目的之一是发现 Senza（PyO3 绑定层）的 bug 和功能不足。**

当测试失败时，**绝对禁止**直接对待测逻辑无脑 `pytest.mark.skip` / `# ignore` 后继续。
这是想当然地认为问题出在外部（大模型、端点），而不是绑定层代码。这种思维定式会导致
真正的 bug 被掩盖。

### 失败时处理流程

1. **深入调查** — 用 `curl` 直接打 API 看 LLM 原始返回，对比 Senza 事件（`prompt_and_collect`
   返回的 dict）差异，定位在哪一层（provider adapter / loop / harness / workflow）。
2. **确认是绑定层 bug** — 修 Senza 代码（`src/` 或 `senza-pkg/senza/__init__.py`），不 ignore。
3. **确认是功能不足** — 在测试注释中说明缺什么功能，保留测试，标记期望失败或报告。
4. **只有确认是环境问题且无法通过代码修复时** — 才允许 skip，且注释中写明完整调查过程。

### 常见误区

- **"DeepSeek-V4-Flash 不够聪明"** — 错。如果 OMP harness 能正常工作，Senza 绑定的同一
  端点也应该正常。先查绑定层。
- **"base_url 拼错了"** — 优先从本机 OMP 配置（`~/.omp/agent/models.yml`）核对该端点
  的确切 baseUrl / 模型名 / `openai-completions` API。
- **"reasoning 模式下 tool call 不工作"** — 查 `parse_reasoning_content` 是否开启
  （Senza `providers.openai` 默认 `True`），查 `ThinkingScheme` 配置。
- **"测试失败但不知道原因，先 skip 以后再看"** — 禁止。每次 skip 都必须有调查记录。

## Provider 配置

默认：`OPENAI_API_KEY`（缺省载入 `~/.omp_llm_env`）+ `OPENAI_API_BASE`
（默认 `http://api.hyper-op.com/v1`）+ `SENZA_LIVE_MODEL`（默认 `DeepSeek-V4-Flash`）。
等价 `senza.providers.openai(api_key=..., base_url=...)` + `HarnessBuilder("DeepSeek-V4-Flash")`。

## 运行

```bash
# 无 key：真实测试全部 SKIP，离线构造冒烟通过（验证 API 签名）
python -m pytest live-tests/ -q

# 带 key：跑当前 OMP DeepSeek
source ~/.omp_llm_env && python -m pytest live-tests/ -v --timeout=180
```

## 关键设计

- `base.py` — 共享助手：`provider_or_skip`、`make_harness`、`run_prompt`、`with_timeout`、
  事件断言（`assert_tool_called`/`assert_settled`/`assert_no_error`）、分级超时。
- 每个层文件含一个**不 skip 的离线构造冒烟**（`test_*_constructs_offline`，`sk-test` provider）：
  无 key 也能验证该层每个 API 调用的签名正确。
- 弱内容断言（非空 / 含关键词 / 工具被调用），不依赖 LLM 输出的具体文本。
- 分层：agent / loop / tools / runtime / strategy，镜像 runtime live-tests。
