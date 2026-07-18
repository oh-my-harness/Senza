# Senza 开发指南

本文档面向 Senza 仓库的开发者，描述本地开发、测试、升级 runtime pin 的完整流程。

## 前置要求

- Rust toolchain（stable）
- Python 3.9+
- maturin（`pip install "maturin>=1.7"`）
- pytest（`pip install pytest`）
- 对 `llm-harness-runtime` 仓库的读取权限（git 依赖需要 GitHub 认证）

## 仓库结构

Senza 仓库同时包含 Rust 源码（PyO3 绑定层）和 Python 打包文件：

- `Cargo.toml` / `src/` / `build.rs` — Rust PyO3 crate（从 runtime 仓库迁移而来）
- `tests/` — Rust 集成测试 + Python 测试
- `senza-pkg/senza/` — Python 包（`.pyi` stub + `py.typed`）
- `senza-pkg/runtime.lock` — pin 的 runtime commit SHA
- `pyproject.toml` — maturin 构建配置
- `scripts/` — 构建和校验脚本

Rust 源码通过 git 依赖引用闭源 `llm-harness-runtime` 仓库的 crate。`Cargo.toml` 中的 `rev = "PLACEHOLDER"` 在构建时由 `build_wheel.sh` 从 `runtime.lock` 注入实际 SHA。

## Python 环境

`dev_setup.sh` 会自动创建 `.venv/` 虚拟环境（用 `python3`），并安装 `maturin` + `pytest`，无需手动操作。

```bash
./scripts/dev_setup.sh
```

完成后激活 venv 即可使用：

```bash
source .venv/bin/activate
python scripts/check_stubs.py
python -m pytest tests/ -v
```

如果系统默认 `python3` 不是你想要的，用 `PYTHON` 环境变量指定基础解释器（`dev_setup.sh` 会用它创建 venv）：

```bash
PYTHON=/path/to/your/python ./scripts/dev_setup.sh
```

`PYTHON` 同时用于构建 wheel（`PYO3_PYTHON`）和安装 wheel（`pip install`）。

## 本地开发

### 构建 + 安装 wheel

```bash
./scripts/dev_setup.sh
```

脚本会：
1. 读 `senza-pkg/runtime.lock` 的 SHA
2. 注入到 `Cargo.toml`（替换 `PLACEHOLDER`）
3. `maturin build --release`（cargo 从 GitHub 拉取 runtime crate）
4. 恢复 `Cargo.toml`
5. `pip install --force-reinstall` 安装 wheel

### 校验 .pyi stubs

```bash
python scripts/check_stubs.py
```

比对 `senza-pkg/senza/__init__.pyi` 与已安装 wheel 的 `__text_signature__`。漂移时输出 diff 并 exit 1。

### 运行测试

```bash
# stub 校验测试
python -m pytest tests/test_check_stubs.py -v

# Python 集成测试（需先 dev_setup.sh 安装 wheel）
python -m pytest tests/ -v
```

### 运行示例

```bash
export OPENAI_API_KEY=sk-...
python examples/agent/01_basic_prompt.py
python examples/runtime/01_linear_workflow.py
```

## 升级 runtime pin

当需要同步 Senza 到 runtime 的新版本时：

1. 更新 pin 文件：
   ```bash
   echo -n "<新SHA>" > senza-pkg/runtime.lock
   ```

2. 构建并安装新 wheel：
   ```bash
   ./scripts/dev_setup.sh
   ```

3. 校验 stubs：
   ```bash
   python scripts/check_stubs.py
   ```

4. 如果有 drift，手动更新 `senza-pkg/senza/__init__.pyi`：
   - 对齐参数名和默认值到 runtime 的 `__text_signature__`
   - 保持 docstring、分组注释、类型注解的手工风格
   - 同步检查 README.md 和 skills/ 中的签名是否漂移

5. 提 PR，CI 自动用 pin 文件构建并校验，通过后合并。

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

## CI 行为

CI（`.github/workflows/build-wheel.yml`）：

1. 读取 `senza-pkg/runtime.lock` 中的 commit SHA
2. 注入到 `Cargo.toml`
3. `maturin build --release`（用 `RUNTIME_PAT` 认证拉取私有 runtime crate）
4. 安装并验证 import
5. 运行 `scripts/check_stubs.py` 校验 stubs
6. tag push（`v*`）时发布到 PyPI

CI 不接受 runtime rev 覆盖——临时测试请在本地用 `dev_setup.sh` 完成。
