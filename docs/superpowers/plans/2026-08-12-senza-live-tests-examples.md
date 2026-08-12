# Plan: 整合示例 → `live-tests/examples/`，删除仓库根 `examples/`

- Date: 2026-08-12
- Branch: `test`
- 前置计划: [`2026-08-12-senza-live-tests.md`](2026-08-12-senza-live-tests.md)（5 层测试套件已落地）
- 上游参照: `llm-harness-runtime/.../llm-harness-live-tests/examples/*.rs`（23 个）
- 来源：仓库根 `examples/`（当前 32 个 Python 示例）

## 背景 / 目标

运行时的 live-tests crate 由 `tests/`（5 层）+ `examples/`（23 个可运行的文档）组成。
Senza 侧已镜像 `tests/`。现把示例统一收拢到一个家：**`live-tests/examples/`**，并**整体废弃
仓库根 `examples/` 目录**。

最终态：
- `live-tests/examples/` = 唯一示例归宿，含两部分：
  1. **23 个运行时同名镜像**（`NN_<snake>.py`，01–23）——承接仓库根中 15 个重复场景；
  2. **17 个仓库根专属示例**（无运行时 1:1 承接）——移植进来。
- 仓库根 `examples/` **整目录删除**（32 个文件全部被吸收：15 进 23 镜像覆盖、17 独立移植）。
- `docs/`、README 中所有指向仓库根 `examples/` 的引用随迁更新。

### 示例的本质（转译自运行时 CLAUDE.md）

- 「可运行的文档」：人类直接跑、肉眼观察，**弱断言**（打印 + 极少 assert）。
- 独立 `main()` 程序：构造真实 provider → 搭 harness/engine → 驱动真实 LLM → 打印输出与 token 用量。
- 无 key 时打印 SKIP 并 exit 0，不崩溃——对齐测试侧「无 key 跳过」语义。

## 决策

- **默认端点/模型**：复用 `live-tests/base.py` —— OMP DeepSeek
  （`http://api.hyper-op.com/v1` + `DeepSeek-V4-Flash`），key 缺省 `~/.omp_llm_env`。
- **共享助手**：`live-tests/examples/_common.py`（已建）：
  - sys.path 引导使 `base` 可导入；
  - 重导出 `base` 超时常量 / `make_harness` / `run_prompt` / `text_of` / `with_timeout`；
  - `require_provider()`（无 key 打印 SKIP 并 exit 0）+ `make_example_harness(customize)`。
- **移植规范**：仓库根被移植的 17 个示例改为走 `_common.py`（`from _common import ...`）——
  统一 provider 发现、SKIP 语义、打印输出与用量；逻辑/功能照搬，不自造新 API。
- **命名**：
  - 运行时镜像：`01_prompt_streaming.py` … `23_infra_integration.py`（与运行时 1:1）。
  - 仓库根移植（无运行时序号冲突，语义命名）：`30_multi_provider.py` 起的
    `30…43` 段，避免与 01–23 撞号；见清单。
- **并发**：23 个运行时镜像中 01 由主 agent 手写为规范化模板，其余 22 个 + 17 个移植
  派**并行子代理**；子代理各自读：对应 `.rs`/被移植 `.py` + `_common.py`/`base.py` +
  `senza-pkg/senza/__init__.pyi` + Senza 既有 `examples/` 作参照；**写前二读确认签名，不臆造**。
- **验证**：no-key 全量 → 每个打印 SKIP 且 exit 0、无 traceback；`ruff check live-tests/` 干净；
  全量真实跑对 DeepSeek（成本已豁免）。**不 push**，仅提交本地。

## 来源归并（32 个仓库根示例 → 去处）

**A. 15 个与运行时 1:1 重复 → 由 23 个镜像承接（不单独移植）：**
`agent/{02_tool_calling,03_streaming,04_dynamic_config,06_hooks,07_rules,08_budget_pricing,
09_skills,12_session_branch,17_grep_glob,18_compaction_prompt}.py`
`infra/{01_audit_jsonl,02_tracing,03_sandbox}.py`
`runtime/{01_linear_workflow,04_crash_recovery}.py`

**B. 17 个无运行时 1:1 → 移植进 `live-tests/examples/`（编号 30+）：**

| 新文件（live-tests/examples/） | 来源（仓库根） |
|---|---|
| 30_basic_prompt.py | agent/01_basic_prompt.py |
| 31_multi_provider.py | agent/05_multi_provider.py |
| 32_plugins.py | agent/10_plugins.py |
| 33_steering.py | agent/11_steering.py |
| 34_anthropic_standalone.py | agent/13_anthropic_standalone.py |
| 35_code_review.py | agent/14_code_review.py |
| 36_rag_qa.py | agent/15_rag_qa.py |
| 37_mcp_blender.py | agent/16_mcp_blender.py |
| 38_conditional_routing.py | runtime/02_conditional_routing.py |
| 39_executor_steps.py | runtime/03_executor_steps.py |
| 40_pause_cancel.py | runtime/05_pause_cancel.py |
| 41_human_in_the_loop.py | runtime/06_human_in_the_loop.py |
| 42_shell_executor.py | runtime/07_shell_executor.py |
| 43_http_executor.py | runtime/08_http_executor.py |
| 44_composite_judge.py | runtime/09_composite_judge.py |
| 45_hooks_retries.py | runtime/10_hooks_retries.py |
| 46_data_analysis.py | runtime/11_data_analysis.py |

（basic_prompt 即便近似 01_streaming，作为最简入门示例保留。）

## 任务

### Phase 0 — 共享模板硬化
- [ ] 复核 `_common.py` lint 干净、可导入；验证 require_provider 的 SKIP 路径。

### Phase 1 — 规范化模板（主 agent 手写）
- [ ] 手写 `examples/01_prompt_streaming.py`（对照运行时 `01_prompt_streaming.rs`）。
- [ ] 验证：无 key → SKIP exit 0；带 key → 真实流式输出 + 用量非空；ruff 干净。
- [ ] 写 `examples/README.md`（清单 + 运行方式 + 无 key 行为 + 与各层测试/来源映射）。

### Phase 2 — 并行移植（22 个镜像 + 17 个移植）
- [ ] 依据映射派子代理，全部落到 `live-tests/examples/`，统一走 `_common.py` 约定。
- 运行时镜像动作：02–23（01 已手写）。
- 仓库根移植动作：30–46（B 表 17 个）。

### Phase 3 — 验证
- [ ] `find` 核对全部文件存在（23 镜像 + 17 移植 + _common + README）。
- [ ] `ruff check live-tests/` 干净。
- [ ] no-key 全量：`HOME=/tmp/emptyhome … for f in examples/*.py` → 各自 SKIP 且 exit 0，无 traceback。
- [ ] 全量真实跑：`source ~/.omp_llm_env && for f in examples/*.py; do python "$f"; done` 对 DeepSeek 逐一通过。

### Phase 4 — 删除仓库根 examples/ + 收尾
- [ ] `git rm -r examples/`（A、B 两组 + 已删的 strategy/knowledge 空目录一并清理）。
- [ ] 搜 `examples/` 引用：README.md、docs/api-reference.md、SENZA_DESIGN.md、skills、
      各 plan/spec → 重定向到 `live-tests/examples/`。
- [ ] `live-tests/README.md` 增补 examples 小节。
- [ ] 确认 `pytest tests/` 仍 437 passed（迁移不触碰 tests/）。
- [ ] 提交（逻辑 commit：模板+镜像、移植、删除 examples/、doc 更新）。

## 映射表（运行时示例 → Senza API）

| 运行时 | 主题 | Senza 主要 API |
|---|---|---|
| 01 | streaming | `providers.openai` / `stream_prompt` / `extract_text` / `usage()` |
| 02 | 工具调用 | `create_tool(name,desc,schema,callable)` / `.tools([...])` |
| 03 | 动态配置+多轮 | `.set_system_prompt` / `.set_thinking_level` / 多轮 `prompt` |
| 04 | session 分支 | `read_active_path` / `fork_branch` / `navigate_tree` / Jsonl store |
| 05 | compaction | `set_compaction_*` / 手动 compact / context_window 800 |
| 06 | skills+model | `.set_model` / load skills / 真实模型往返 |
| 07 | hooks | `senza.hooks.*` / `.hooks([...])` |
| 08 | workflow | `WorkflowEngine(wf, provider, model, judge)` / `.with_executor` / `.run()` |
| 09 | 恢复 | `WorkflowEngine.with_task_store(dir)` / `.restore(...)` / `.state()` |
| 10 | sandbox | `senza.infra.seatbelt_sandbox` / `create_os_env` |
| 11 | 子代理 | `senza.spawn_*` / sub-agent API |
| 12 | 审计 | `senza.infra.JsonlAuditSink` / trace export |
| 13 | 预算 | `senza.create_budget_sink` / pricing / usage() 成本 |
| 14 | 审批 | `senza.strategy.rules_approval` / approval hook |
| 15 | 安全 | `senza.strategy.safety_defaults` / `injection_filter` |
| 16 | 状态面板 | `senza.strategy.status_panel` |
| 17 | 来源 | `senza.strategy.source_tag` / `project_instruction` |
| 18 | 循环安全 | `senza.strategy.loop_safety` |
| 19 | 内存防御 | `senza.strategy.memory_defense` / `tool_output_guard` |
| 20 | notify | `senza.strategy.notify` |
| 21 | 压缩 | `senza.strategy.context_aware_compact_prompt` |
| 22 | fs 工具 | `create_fs_tools_plugin`（bash/read/write/edit/grep/glob）|
| 23 | infra | knowledge plugin + memory + session recall + event stream |

> 各示例精确签名以 `senza-pkg/senza/__init__.pyi` 与运行时对应 `.rs`/被移植 `.py` 为准；
> 子代理写前必须二读确认，不得臆造未验证的 API。
