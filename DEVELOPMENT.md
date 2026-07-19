# Senza 开发指南

本文档面向 Senza 仓库的开发者，描述本地开发、测试、升级 runtime pin 的完整流程。

## 前置要求

- Rust toolchain（stable），含 `rustfmt` + `clippy` 组件
- Python 3.12+（脚本自动探测可链接 libpython 的解释器；见下文 Python 环境）
- 对 `llm-harness-runtime` 仓库的读取权限（git 依赖需要 GitHub 认证）

`maturin`、`pytest` 由 `dev_setup.sh` 自动装进 venv，无需预装。

## 仓库结构

Senza 仓库同时包含 Rust 源码（PyO3 绑定层）和 Python 打包文件：

- `Cargo.toml` / `src/` / `build.rs` — Rust PyO3 crate（从 runtime 仓库迁移而来）
- `tests/` — Rust 集成测试（`*.rs`）+ Python 测试（`*.py`）
- `senza-pkg/senza/` — Python 包（`.pyi` stub + `py.typed`）
- `senza-pkg/runtime.lock` — pin 的 runtime commit SHA
- `pyproject.toml` — maturin 构建配置（含 `[tool.maturin] features`）
- `scripts/` — 构建、测试、校验脚本（见下文脚本清单）

Rust 源码通过 git 依赖引用闭源 `llm-harness-runtime` 仓库的 crate。`Cargo.toml` 中的 `rev = "PLACEHOLDER"` 在构建时由 `build_wheel.sh` / `cargo_checks.sh` 从 `runtime.lock` 注入实际 SHA，构建完成后恢复 `PLACEHOLDER`——工作树永远不残留实际 SHA。

### Feature 模型

两层 feature，不要混用：

| 层 | 文件 | 内容 | 谁传 |
|---|---|---|---|
| pyo3 feature | `pyproject.toml [tool.maturin] features` | `pyo3/extension-module`、`pyo3/abi3-py39`、`pyo3/experimental-inspect` | maturin 自动读，**不要**在 `--features` 里重复 |
| Cargo feature | `Cargo.toml [features]` | `extension-module`（别名，等价 `pyo3/extension-module`）、`test-utils` | `build_wheel.sh --test-utils` 传 `test-utils` |

`Cargo.toml` 的 `default = []`（故意不含 `extension-module`），这样 `cargo test` 能链接 libpython；maturin 构建时通过 pyproject 启用 `pyo3/extension-module`。

### Cargo.lock 策略

`Cargo.lock` **提交到 git**（不在 `.gitignore` 里）。Senza 产出 wheel（最终产物，不是被其他 Rust crate 消费的库），提交 lock 保证本地开发、CI、多平台发布矩阵的构建可复现——runtime crate 及其间接依赖的精确版本都被锁定。升级 runtime pin 后跑一次 `./scripts/dev_setup.sh` 会更新 `Cargo.lock`，随 pin 升级一起提交。

## Python 环境

所有脚本统一使用仓库内 `.venv/` 虚拟环境——没有就创建，创建不了就报错。`scripts/_venv.sh` 是所有 shell 脚本共享的 venv 助手，负责：

- 探测可链接 libpython 的基础 Python（Homebrew `python@3.12`、python.org installer 等），跳过 Xcode 自带的 `Python3.framework`（其 `LIBDIR` 在磁盘上不存在，无法链接 `cargo test`）。
- `.venv/` 不存在时自动创建并升级 pip。
- `.venv/` 存在但不可链接时报错，提示删除重建。

```bash
./scripts/dev_setup.sh
```

完成后激活 venv 即可使用：

```bash
source .venv/bin/activate
python scripts/check_stubs.py
python -m pytest tests/ -v
```

`check_stubs.py` 即使不激活 venv 直接用系统 `python3` 调用，也会自动 re-exec 到 `.venv/bin/python`。

如果自动探测到的基础 Python 不是你想要的，用 `BASE_PYTHON` 环境变量显式指定（该解释器必须带可链接的 libpython）：

```bash
BASE_PYTHON=/path/to/your/python ./scripts/dev_setup.sh
```

`VENV=/path/to/venv` 可覆盖 venv 路径。`_venv.sh` 导出 `PYTHON` 和 `PYO3_PYTHON` 指向 venv 解释器，供 `build_wheel.sh`（maturin 构建）和 `cargo_checks.sh`（`cargo test` 链接）使用。

## 脚本清单

所有 shell 脚本 `source scripts/_venv.sh` 并调用 `ensure_venv`，统一使用仓库 `.venv/`。Python 脚本 `check_stubs.py` 自引导到 venv。

| 脚本 | 作用 | 典型用法 |
|---|---|---|
| `scripts/_venv.sh` | 共享 venv 助手（探测可链接 Python、创建 venv、导出 `PYTHON`/`PYO3_PYTHON`） | 被 source，不单独跑 |
| `scripts/dev_setup.sh` | 一键：创建 venv → 装 maturin/pytest → 构建 wheel（`--test-utils`）→ 装进 venv | 首次开发环境搭建 |
| `scripts/build_wheel.sh` | 构建 wheel（注入 SHA、maturin build、恢复 SHA）。`--test-utils` 加 test-utils feature | `./scripts/build_wheel.sh --test-utils` |
| `scripts/cargo_checks.sh` | Rust + Python 全量检查：fmt → clippy → cargo test → pytest | `./scripts/cargo_checks.sh`（跑全部 4 stage） |
| `scripts/check_stubs.py` | 校验 `.pyi` stub 与已安装 wheel 的 `__text_signature__` 一致 | `./scripts/check_stubs.py`（任何解释器调用都自动 re-exec 到 venv） |

## 本地开发流程

### 首次搭建

```bash
./scripts/dev_setup.sh
source .venv/bin/activate
```

`dev_setup.sh` 会创建 `.venv/`（探测 Homebrew/python.org Python，跳过 Xcode 自带 Python）、装 maturin+pytest、构建带 `test-utils` 的 wheel、`pip install` 到 venv。

### 日常开发循环

```bash
# 改了 Rust/Python 代码后，一键跑全量检查（fmt + clippy + cargo test + pytest）
./scripts/cargo_checks.sh

# 只跑测试（不跑 fmt/clippy）
./scripts/cargo_checks.sh test pytest

# 重新构建并安装 wheel（改了 Rust 代码后需要）
./scripts/dev_setup.sh

# 校验 stub（改了 .pyi 或签名后）
./scripts/check_stubs.py
```

`cargo_checks.sh` 的 4 个 stage：

| Stage | 命令 | 测什么 |
|---|---|---|
| `fmt` | `cargo fmt --check` | Rust 代码格式 |
| `clippy` | `cargo clippy --all-targets -- -D warnings` | Rust lint |
| `test` | `cargo test --all -- --ignored` | 5 个 Rust 集成测试（PyJudge/PyExecutor/async tool，需嵌入式 Python） |
| `pytest` | `pytest tests/ -q` | 225 个 Python 测试（API、stubs、issue 回归、workflow engine） |

### 运行示例

```bash
export OPENAI_API_KEY=sk-...
python examples/agent/01_basic_prompt.py
python examples/runtime/01_linear_workflow.py
```

## 发布版本

1. 确认 `senza-pkg/runtime.lock` 是目标 runtime SHA
2. 更新 `Cargo.toml` 的 `version` 和 `senza-pkg/senza/__init__.pyi` 的 `__version__`
3. 本地跑全量检查：
   ```bash
   ./scripts/cargo_checks.sh
   ```
4. 提交并打 tag：
   ```bash
   git tag v0.4.2
   git push origin v0.4.2
   ```
5. CI 自动触发：构建多平台 wheel → 发布 GitHub Release → 发布 PyPI

## 升级 runtime pin

```bash
echo -n "<新SHA>" > senza-pkg/runtime.lock
./scripts/dev_setup.sh          # 构建并安装新 wheel
./scripts/check_stubs.py        # 校验 stub
```

如果有 stub drift，手动更新 `senza-pkg/senza/__init__.pyi`：

- 对齐参数名和默认值到 runtime 的 `__text_signature__`
- 保持 docstring、分组注释、类型注解的手工风格
- 同步检查 README.md 和 skills/ 中的签名是否漂移

## 用本地 runtime 改动测试

默认情况下，runtime crate 通过 git 依赖从 GitHub 拉取。如果需要用本地 runtime 仓库的改动测试，在 `Cargo.toml` 末尾添加 `[patch]` 段：

```toml
[patch."https://github.com/oh-my-harness/llm-harness-runtime"]
llm-harness-types   = { path = "/path/to/llm-harness-runtime/crates/llm-harness-types" }
llm-harness-loop    = { path = "/path/to/llm-harness-runtime/crates/llm-harness-loop" }
llm-harness-agent   = { path = "/path/to/llm-harness-runtime/crates/llm-harness-agent" }
llm-harness-runtime = { path = "/path/to/llm-harness-runtime/crates/llm-harness-runtime" }
```

注意：`[patch]` 不要提交到 git，仅用于本地测试。

## 下游项目本地开发 Senza

下游项目（如 eda-studio）依赖 `senza-sdk`，想本地改 Senza 源码时，用下游项目的 `scripts/install-senza-dev.sh`（该脚本 source Senza 的 `_venv.sh`，复用同一套 venv 契约）：

```bash
# 在下游项目目录（../Senza 是 Senza checkout）
./scripts/install-senza-dev.sh     # maturin develop --release，editable 安装
./scripts/uninstall-senza-dev.sh   # 卸载，回到 PyPI 版本
```

## CI 行为

CI（`.github/workflows/build-wheel.yml`）在 push tag `v*` 或手动触发时运行，矩阵构建 linux/mac/windows wheel：

1. 注入 `runtime.lock` 的 SHA 到 `Cargo.toml`
2. `cargo fmt --check` + `cargo clippy -- -D warnings`（门禁）
3. `maturin build --release`（用 `RUNTIME_PAT` 认证拉取私有 runtime crate）
4. 安装 wheel + 验证 import
5. `scripts/check_stubs.py` 校验 stub
6. tag push 时：发布 GitHub Release + 上传 PyPI

CI **不跑** `cargo test` 和 `pytest`（需要 linkable libpython + venv，多平台配置复杂）——这些在本地 `cargo_checks.sh` 跑。CI 不接受 runtime rev 覆盖。
