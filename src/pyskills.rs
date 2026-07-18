//! Skills 加载的 Python 包装。
//!
//! 暴露：
//! - `Skill` pyclass（opaque，持有 `llm_harness_agent::Skill`）
//! - `load_skills(path) -> list[Skill]` 工厂函数

use std::path::{Path, PathBuf};
use std::sync::Arc;

use futures::future::BoxFuture;
use llm_harness_agent::Skill;
use llm_harness_types::{
    DiagnosticLevel, EnvError, ExecutionEnv, FileInfo, ShellOptions, ShellOutput,
};
use pyo3::prelude::*;
use tokio_util::sync::CancellationToken;

use crate::pyagent::runtime;

/// Skill handle（通过 `load_skills()` 创建，不可变）。
#[pyclass(name = "Skill")]
pub struct PySkill {
    pub(crate) skill: Skill,
}

impl PySkill {
    /// 从已有 `Skill` 构造 `PySkill`（供 builder 内部路径使用）。
    pub fn from_skill(skill: Skill) -> Self {
        Self { skill }
    }
}

#[pymethods]
impl PySkill {
    /// Skill 名称（frontmatter `name` 字段）。
    #[getter]
    fn name(&self) -> &str {
        &self.skill.name
    }

    /// 可选 UI 标签；缺失时回退到 `name`。
    #[getter]
    fn label(&self) -> Option<&str> {
        self.skill.label.as_deref()
    }

    /// 简短描述（展示给 LLM）。
    #[getter]
    fn description(&self) -> &str {
        &self.skill.description
    }

    /// 源 `SKILL.md` 文件的绝对路径。
    #[getter]
    fn source(&self) -> String {
        self.skill.source.to_string_lossy().into_owned()
    }

    /// Skill 根目录（`source` 的父目录）。
    #[getter]
    fn base_dir(&self) -> String {
        self.skill.base_dir.to_string_lossy().into_owned()
    }

    /// 为 `true` 时 skill 不出现在系统提示中，须显式调用。
    #[getter]
    fn disable_model_invocation(&self) -> bool {
        self.skill.disable_model_invocation
    }

    fn __repr__(&self) -> String {
        format!("Skill({:?})", self.skill.name)
    }
}

/// 本地文件系统 `ExecutionEnv` 实现——仅用于 Skills 加载。
///
/// `read_text_file` 和 `list_dir` 执行真实 `std::fs` I/O；其余 shell/exec
/// 相关方法返回 `EnvError::Other`，与 `UnsupportedEnv` 行为一致。
/// 这样避免引入整个 `llm-harness-runtime-sandbox-os` crate。
struct LocalFsEnv {
    working_dir: PathBuf,
}

impl LocalFsEnv {
    fn new(working_dir: impl Into<PathBuf>) -> Self {
        Self {
            working_dir: working_dir.into(),
        }
    }

    fn unsupported<'a, T: Send + 'a>() -> BoxFuture<'a, Result<T, EnvError>> {
        Box::pin(async {
            Err(EnvError::Other(
                "execution environment is not available".into(),
            ))
        })
    }
}

impl ExecutionEnv for LocalFsEnv {
    fn working_dir(&self) -> &Path {
        &self.working_dir
    }

    fn read_text_file<'a>(
        &'a self,
        path: &'a Path,
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<String, EnvError>> {
        Box::pin(async move {
            let bytes = std::fs::read(path)?;
            match String::from_utf8(bytes) {
                Ok(s) => Ok(s),
                Err(_) => Err(EnvError::InvalidUtf8(path.to_path_buf())),
            }
        })
    }

    fn read_text_lines<'a>(
        &'a self,
        path: &'a Path,
        max_lines: Option<usize>,
        abort: CancellationToken,
    ) -> BoxFuture<'a, Result<Vec<String>, EnvError>> {
        Box::pin(async move {
            let content = self.read_text_file(path, abort).await?;
            let lines: Vec<String> = content.lines().map(|s| s.to_string()).collect();
            match max_lines {
                Some(n) => Ok(lines.into_iter().take(n).collect()),
                None => Ok(lines),
            }
        })
    }

    fn read_binary_file<'a>(
        &'a self,
        path: &'a Path,
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<Vec<u8>, EnvError>> {
        Box::pin(async move { Ok(std::fs::read(path)?) })
    }

    fn write_file<'a>(
        &'a self,
        path: &'a Path,
        content: &'a [u8],
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<(), EnvError>> {
        Box::pin(async move { Ok(std::fs::write(path, content)?) })
    }

    fn append_file<'a>(
        &'a self,
        path: &'a Path,
        content: &'a [u8],
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<(), EnvError>> {
        use std::io::Write;
        Box::pin(async move {
            let mut f = std::fs::OpenOptions::new().create(true).append(true).open(path)?;
            f.write_all(content)?;
            Ok(())
        })
    }

    fn file_info<'a>(
        &'a self,
        path: &'a Path,
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<FileInfo, EnvError>> {
        Box::pin(async move {
            let md = std::fs::metadata(path)?;
            let modified = md
                .modified()
                .map(|t| {
                    let dur = t
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default();
                    chrono::DateTime::<chrono::Utc>::from_timestamp(
                        dur.as_secs() as i64,
                        dur.subsec_nanos(),
                    )
                    .unwrap_or_else(|| chrono::Utc::now())
                })
                .unwrap_or_else(|_| chrono::Utc::now());
            Ok(FileInfo {
                path: path.to_path_buf(),
                is_dir: md.is_dir(),
                size: if md.is_file() { md.len() } else { 0 },
                modified,
            })
        })
    }

    fn list_dir<'a>(
        &'a self,
        path: &'a Path,
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<Vec<FileInfo>, EnvError>> {
        Box::pin(async move {
            let mut out = Vec::new();
            for entry in std::fs::read_dir(path)? {
                let entry = entry?;
                let md = entry.metadata()?;
                let modified = md
                    .modified()
                    .map(|t| {
                        let dur = t
                            .duration_since(std::time::UNIX_EPOCH)
                            .unwrap_or_default();
                        chrono::DateTime::<chrono::Utc>::from_timestamp(
                            dur.as_secs() as i64,
                            dur.subsec_nanos(),
                        )
                        .unwrap_or_else(|| chrono::Utc::now())
                    })
                    .unwrap_or_else(|_| chrono::Utc::now());
                out.push(FileInfo {
                    path: entry.path(),
                    is_dir: md.is_dir(),
                    size: if md.is_file() { md.len() } else { 0 },
                    modified,
                });
            }
            Ok(out)
        })
    }

    fn exists<'a>(
        &'a self,
        path: &'a Path,
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<bool, EnvError>> {
        Box::pin(async move { Ok(path.exists()) })
    }

    fn create_dir<'a>(
        &'a self,
        path: &'a Path,
        recursive: bool,
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<(), EnvError>> {
        Box::pin(async move {
            if recursive {
                std::fs::create_dir_all(path)?;
            } else {
                std::fs::create_dir(path)?;
            }
            Ok(())
        })
    }

    fn remove<'a>(
        &'a self,
        path: &'a Path,
        recursive: bool,
        _force: bool,
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<(), EnvError>> {
        Box::pin(async move {
            if recursive {
                std::fs::remove_dir_all(path)?;
            } else {
                if path.is_dir() {
                    std::fs::remove_dir(path)?;
                } else {
                    std::fs::remove_file(path)?;
                }
            }
            Ok(())
        })
    }

    fn create_temp_dir<'a>(&'a self, _prefix: &'a str) -> BoxFuture<'a, Result<PathBuf, EnvError>> {
        Self::unsupported()
    }

    fn execute_shell<'a>(
        &'a self,
        _cmd: &'a str,
        _opts: ShellOptions<'a>,
    ) -> BoxFuture<'a, Result<ShellOutput, EnvError>> {
        Self::unsupported()
    }

    fn cleanup<'a>(&'a self) -> BoxFuture<'a, Result<(), EnvError>> {
        Box::pin(async { Ok(()) })
    }
}

/// 从目录扫描 `SKILL.md` 文件，返回 `list[Skill]`。
///
/// `path` 下每个含 `SKILL.md` 的直接子目录被视作一个 skill。
/// 加载失败的单个文件不会中断整体扫描；诊断信息通过 `warnings.warn`
/// 发出，仅返回成功加载的 skill。
#[pyfunction]
#[pyo3(text_signature = "(path)")]
pub fn load_skills<'py>(
    py: Python<'py>,
    path: &str,
) -> PyResult<Bound<'py, pyo3::types::PyList>> {
    let dir = PathBuf::from(path);
    let env: Arc<dyn ExecutionEnv> = Arc::new(LocalFsEnv::new(path));
    let rt = runtime(py);
    // load_skills 是 async 且涉及文件 I/O，释放 GIL 更安全。
    let (skills, diags) = py.detach(move || {
        rt.block_on(async move { llm_harness_agent::load_skills(env.as_ref(), &[dir]).await })
    });

    // 将 SkillDiagnostic 作为 Python warning 发出，便于用户发现格式错误的 SKILL.md。
    if !diags.is_empty() {
        let warnings_mod = pyo3::types::PyModule::import(py, "warnings")?;
        for d in &diags {
            let level = match d.level {
                DiagnosticLevel::Warn => "warning",
                DiagnosticLevel::Error => "error",
            };
            let msg = format!(
                "skills: [{}] {}: {}",
                level,
                d.source.display(),
                d.message
            );
            warnings_mod.call_method1("warn", (msg,))?;
        }
    }

    let list = pyo3::types::PyList::empty(py);
    for skill in skills {
        let py_skill = Py::new(py, PySkill::from_skill(skill))?;
        list.append(py_skill)?;
    }
    Ok(list)
}
