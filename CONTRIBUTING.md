# 贡献指南

感谢你对 Senza 的兴趣！本文档说明如何参与开发。

## 开发环境

```bash
git clone https://github.com/oh-my-harness/Senza.git
cd Senza
./scripts/dev_setup.sh   # 创建 venv，安装 maturin + pytest
```

前置要求：
- Rust toolchain（stable），含 `rustfmt` + `clippy`
- Python 3.12+
- 对 `llm-harness-runtime` 仓库的读取权限（git 依赖）

详细环境说明见 [DEVELOPMENT.md](DEVELOPMENT.md)。

## 跑测试

```bash
# 一键跑 Rust fmt + clippy + cargo test + pytest
./scripts/cargo_checks.sh
```

也可以单独跑：

```bash
# 仅 Python 测试
pytest tests/

# 仅 Rust 检查
cargo fmt --check
cargo clippy -- -D warnings
cargo test
```

## PR 规范

1. Fork 仓库，从 `main` 拉分支
2. 分支命名：`feat/<简述>`、`fix/<简述>`、`docs/<简述>`
3. commit message 格式：`type(#issue): 简述`，如 `feat(#42): add deepseek provider`
4. 确保 `./scripts/cargo_checks.sh` 通过
5. PR 描述写清：改了什么、为什么改、如何测试

## Good First Issue

标有 `good first issue` 标签的 issue 是入门好选择，常见类型：

- 文档改进（错别字、示例补充、翻译）
- 新增 example（用现有 API 写新场景 demo）
- 补充 .pyi stub 类型标注
- 新增 provider 示例（OpenAI 兼容格式）

## 项目结构

```
src/                    # Rust PyO3 绑定层
senza-pkg/senza/        # Python 包（.pyi stub + py.typed）
tests/                  # Rust 集成测试 + Python 测试
examples/               # 示例代码（agent/ + runtime/）
skills/                 # 过程性知识（供 Codex 加载）
scripts/                # 构建、测试、校验脚本
docs/                   # 文档
```

## 贡献者

感谢所有贡献者（按首次 PR 时间排序）：

<!-- 贡献者名单通过 GitHub Action 自动更新 -->
