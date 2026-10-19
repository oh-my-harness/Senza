# V0.1.1 的 Senza SDK 构建

V0 的完整入口见 [Studio 快速开始](https://github.com/oh-my-harness/senza-studio/blob/review/senza-studio-v011-20261019-658ae4bb/docs/v0-quickstart.md)。
该链接指向 Studio 当前审查分支；其中固定提交和验证边界以审查记录为准。

核对基线：Senza `f10efec71cb3e8d7311e6226edbcd8ebe75ef587`，
`senza-pkg/runtime.lock` 为 `dcb15db9e42e3a66ddc98792b7de116e8de7ed57`。
它适配 V0.1.1 沙箱的 trust_profile/host_binds，并包含 TurnStart/Compaction 事件支持。
Studio 的 `senza-sdk.lock` 同时记录 SDK 1.4.0 和此 Senza 提交；PyPI 1.3.0 安装不是这条交付路径。

Ubuntu/WSL 首次不能假定 `scripts/build_wheel.sh` 自动装好所有构建工具：

```bash
# 从 Senza 仓库根运行，已有 Python 3.12、uv、Rust/Cargo、编译器、Perl。
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python 'maturin>=1.7,<2'
VENV="$PWD/.venv" ./scripts/build_wheel.sh
uv pip install --python .venv/bin/python dist/senza_sdk-*.whl
```

`_venv.sh` 默认只探测若干 macOS Python 路径。Ubuntu 可像上面预建虚拟环境，
或指定实际存在的 `BASE_PYTHON=/usr/bin/python3.12`，并保证该环境已有 maturin。
该变量不会自动补装构建工具。Studio 快速开始选择共用 Studio 虚拟环境，以免额外创建第二个环境。

不要直接以可编辑模式安装 Senza：Cargo.toml 里的 PLACEHOLDER 必须由 build_wheel.sh 从 runtime.lock 注入，
脚本退出时恢复 Cargo.toml。构建前后检查 Git 状态，Cargo.lock 可能由 Cargo 更新；不要提交未知依赖漂移。
Studio 已有 `.venv` 时 dev.sh 会跳过 SDK 重建，因此更换 Senza 提交后必须重新构建并安装 wheel 安装包。

当前机器已有 SDK 1.4.0 的导入已验证；这不证明从 Python 3.12 空环境重新构建通过。
完整 wheel 安装包历史证据与本次验证范围见 Studio 的 `docs/v0-doc-audit-20261019.md`。

当前 Senza PR #44 审查基线为 `0eb27a410375b1b7c321be842347ca0b7380cc14`，
保留的 Runtime 固定版本为 `154eccadce161951ddac92f1e64867a6b8073c05`。
上面的 `f10efec`／`dcb15db` 是本机原验证基线，不表示候选分支已重新验收；
本次仅追加文档，不更改依赖锁定文件。
