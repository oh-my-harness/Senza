//! Python callable 包装为 `Tool` trait 实现。
//!
//! 验证风险点：`Py<PyAny>` 持有 Python callable、`spawn_blocking` +
//! `Python::attach` + `call1` 调用 Python 函数、`ToolResult` 从 Python
//! dict 解析的完整路径。

use std::sync::Arc;

use futures::future::BoxFuture;
use llm_harness_types::{
    DataBlock, Tool, ToolContext, ToolExecutionMode, ToolFailure, ToolProgress, ToolResult,
};
#[cfg(feature = "test-utils")]
use llm_harness_types::{RunContext, RunRequest};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde_json::Value;
use tokio_util::sync::CancellationToken;

use crate::shared::value_conv::{pyobject_to_value, value_to_pyobject};
use llm_harness_types::{BinarySource, ContentBlock, ImageSource};

/// Python callable 包装为 `Tool` trait。
pub struct PyTool {
    name: String,
    description: String,
    schema: Value,
    callback: Arc<Py<PyAny>>,
    is_async: bool,
    report_duration: bool,
}

impl PyTool {
    pub fn new(
        name: String,
        description: String,
        schema: Value,
        callback: Py<PyAny>,
        report_duration: bool,
    ) -> Self {
        let is_async = Python::attach(|py| {
            let inspect = pyo3::types::PyModule::import(py, "inspect")?;
            let is_coro: bool = inspect
                .call_method1("iscoroutinefunction", (callback.bind(py),))?
                .extract()?;
            Ok::<_, PyErr>(is_coro)
        })
        .unwrap_or_else(|e| {
            tracing::debug!("failed to detect async callback, assuming sync: {e}");
            false
        });
        Self {
            name,
            description,
            schema,
            callback: Arc::new(callback),
            is_async,
            report_duration,
        }
    }
}

impl Tool for PyTool {
    fn name(&self) -> &str {
        &self.name
    }

    fn description(&self) -> &str {
        &self.description
    }

    fn report_duration(&self) -> bool {
        self.report_duration
    }

    fn execute<'a>(
        &'a self,
        args: Value,
        ctx: &'a ToolContext,
    ) -> BoxFuture<'a, Result<ToolResult, ToolFailure>> {
        let callback = Arc::clone(&self.callback);
        let is_async = self.is_async;
        let abort = ctx.abort.clone();
        let update_tx = ctx.update_tx.clone();
        Box::pin(async move {
            let result = tokio::task::spawn_blocking(move || {
                Python::attach(|py| {
                    let cb = callback.bind(py);
                    let py_args = value_to_pyobject(py, &args)?;
                    let py_ctx = PyToolContext::new(abort.clone(), update_tx.clone());

                    if is_async {
                        // async: schedule the coroutine on the user's main
                        // event loop when possible (issue #13), falling
                        // back to asyncio.run().
                        let coro = cb.call1((py_args, py_ctx))?;
                        let raw = crate::core::pyloop::run_coro(py, &coro)?;
                        parse_tool_result(&raw)
                    } else {
                        // sync: 直接调用
                        let raw = cb.call1((py_args, py_ctx))?;
                        parse_tool_result(&raw)
                    }
                })
            })
            .await
            .map_err(|e| ToolFailure::new("execution_error", format!("callback join failed: {e}")))?
            .map_err(|e: PyErr| ToolFailure::new("execution_error", e.to_string()))?;
            Ok(result)
        })
    }

    fn parameters_schema(&self) -> &Value {
        &self.schema
    }

    fn execution_mode(&self) -> ToolExecutionMode {
        ToolExecutionMode::Parallel
    }
}

/// 用户附件：包装 `ContentBlock::Image` 或 `ContentBlock::Document`。
///
/// 由 Python 侧构造函数（`image_url` / `image_base64` / `document_url` /
/// `document_file`）创建，对用户不透明。`prompt(attachments=[...])` 与
/// 工具回调返回值中消费。
#[pyclass(name = "Attachment")]
pub struct PyAttachment {
    block: ContentBlock,
}

impl PyAttachment {
    pub(crate) fn block(&self) -> &ContentBlock {
        &self.block
    }
}

/// Media block shape a flat dict stub describes.
#[derive(Clone, Copy)]
enum MediaKind {
    Image,
    Document,
}

/// Locator that a block uses to find its bytes.
enum BlockSource {
    Url(String),
    Base64(String),
}

/// Hint attached to every shape error so the caller can repair the return
/// value without reading the Rust source (the message is fed back to the LLM
/// as the tool result).
const NESTED_SHAPE_ERROR: &str = "nested content block shape is not accepted; use a flat image/document block \
({\"type\": \"image\", \"url\"|\"data\": ...}, \
{\"type\": \"document\", \"media_type\": <mime>, \"data\"|\"url\": ...}) or a senza.Attachment";

const SUPPORTED_BLOCK_TYPES: &str =
    "text, image, image_url, image_base64, document, document_url, document_base64";

/// Build the `ContentBlock` for a media block from already-validated parts.
///
/// This is the single construction path shared by the `Attachment`
/// constructor and by flat dict content blocks, so both accept exactly the
/// same media-type rules: images default to `image/png` for inline data,
/// documents always require an explicit non-empty `media_type`.
fn build_media_block(
    kind: MediaKind,
    source: BlockSource,
    name: Option<String>,
    media_type: Option<String>,
) -> Result<ContentBlock, String> {
    match kind {
        MediaKind::Image => match source {
            BlockSource::Url(url) => {
                if media_type.is_some() {
                    return Err(
                        "image URL blocks do not accept 'media_type'; only inline 'data' images carry one"
                            .to_string(),
                    );
                }
                Ok(ContentBlock::Image {
                    source: ImageSource::Url { url },
                })
            }
            BlockSource::Base64(data) => {
                let media_type = media_type.unwrap_or_else(|| "image/png".to_string());
                if media_type.trim().is_empty() {
                    return Err(
                        "image content block 'media_type' must be a non-empty MIME type"
                            .to_string(),
                    );
                }
                Ok(ContentBlock::Image {
                    source: ImageSource::Base64 { media_type, data },
                })
            }
        },
        MediaKind::Document => {
            let media_type = media_type.ok_or_else(|| {
                "document content block requires an explicit 'media_type' (e.g. \"application/pdf\"); it is never inferred"
                    .to_string()
            })?;
            if media_type.trim().is_empty() {
                return Err(
                    "document content block 'media_type' must be a non-empty MIME type".to_string(),
                );
            }
            let data = match source {
                BlockSource::Url(url) => BinarySource::Url { url },
                BlockSource::Base64(data) => BinarySource::Base64 { data },
            };
            Ok(ContentBlock::Document {
                name,
                media_type,
                data,
            })
        }
    }
}

/// 从 Python 构造函数参数构造 `ContentBlock`（纯转换，可单测）。
///
/// `image_url` / `document_url` 的 `data` 参数是 URL；`image_base64` /
/// `document_base64` 的 `data` 参数是 base64 字符串。
pub(crate) fn attachment_to_content_block(
    kind: &str,
    data: &str,
    name: Option<String>,
    media_type: Option<String>,
) -> Result<ContentBlock, String> {
    match kind {
        "image_url" => build_media_block(
            MediaKind::Image,
            BlockSource::Url(data.to_string()),
            None,
            media_type,
        ),
        "image_base64" => build_media_block(
            MediaKind::Image,
            BlockSource::Base64(data.to_string()),
            None,
            media_type,
        ),
        "document_url" => build_media_block(
            MediaKind::Document,
            BlockSource::Url(data.to_string()),
            name,
            media_type,
        ),
        "document_base64" => build_media_block(
            MediaKind::Document,
            BlockSource::Base64(data.to_string()),
            name,
            media_type,
        ),
        other => Err(format!("unknown attachment kind: {other}")),
    }
}

/// `ContentBlock` → `DataBlock`（工具结果桥接用）。
pub(crate) fn content_block_to_data_block(cb: &ContentBlock) -> Option<DataBlock> {
    match cb {
        ContentBlock::Image { source } => Some(DataBlock::Image {
            source: source.clone(),
        }),
        ContentBlock::Document {
            name,
            media_type,
            data,
        } => Some(DataBlock::Document {
            name: name.clone(),
            media_type: media_type.clone(),
            data: data.clone(),
        }),
        ContentBlock::Text { text } => Some(DataBlock::Text {
            text: text.clone(),
            mime_type: None,
        }),
        _ => None,
    }
}

fn value_error(message: impl Into<String>) -> PyErr {
    pyo3::exceptions::PyValueError::new_err(message.into())
}

fn py_type_name(value: &Bound<'_, PyAny>) -> String {
    value
        .get_type()
        .name()
        .map(|name| name.to_string())
        .unwrap_or_else(|_| "unknown".to_string())
}

/// Read a flat string field.
///
/// Absent → `Ok(None)`. An explicit `None` is rejected rather than treated as
/// absent (silently falling through to a different shape would hide bugs).
/// A dict/list value is reported as a nested shape; any other non-`str` value
/// is reported with its Python type.
fn string_field(item_dict: &Bound<'_, PyDict>, label: &str, key: &str) -> PyResult<Option<String>> {
    let Some(value) = item_dict.get_item(key)? else {
        return Ok(None);
    };
    if value.is_none() {
        return Err(value_error(format!(
            "{label} '{key}' must be a string; explicit None is not accepted (omit the key instead)"
        )));
    }
    if value.cast::<PyDict>().is_ok() || value.cast::<PyList>().is_ok() {
        return Err(value_error(format!(
            "{NESTED_SHAPE_ERROR} (found nested '{key}' field)"
        )));
    }
    value.extract::<String>().map(Some).map_err(|_| {
        value_error(format!(
            "{label} '{key}' must be a string, got {}",
            py_type_name(&value)
        ))
    })
}

fn required_string(item_dict: &Bound<'_, PyDict>, label: &str, key: &str) -> PyResult<String> {
    string_field(item_dict, label, key)?
        .ok_or_else(|| value_error(format!("{label} requires '{key}'")))
}

/// Document `name` is optional and may legitimately be `None`.
fn optional_name(item_dict: &Bound<'_, PyDict>, label: &str) -> PyResult<Option<String>> {
    match item_dict.get_item("name")? {
        None => Ok(None),
        Some(value) if value.is_none() => Ok(None),
        Some(value) => value.extract::<String>().map(Some).map_err(|_| {
            value_error(format!(
                "{label} 'name' must be a string, got {}",
                py_type_name(&value)
            ))
        }),
    }
}

/// A constructor-style kind (`image_url`, `document_base64`, ...) accepts only
/// its own locator key; pointing it at the other one is a permanent mistake,
/// not a fallback.
fn reject_field(
    item_dict: &Bound<'_, PyDict>,
    label: &str,
    key: &str,
    guidance: &str,
) -> PyResult<()> {
    if item_dict.get_item(key)?.is_some() {
        return Err(value_error(format!(
            "{label} does not accept '{key}'; {guidance}"
        )));
    }
    Ok(())
}

/// Reject nested DataBlock / OpenAI wire shapes before kind dispatch so the
/// error names the actual problem instead of "missing 'data' or 'url'".
fn reject_nested_shape(item_dict: &Bound<'_, PyDict>) -> PyResult<()> {
    const NESTED_KEYS: [&str; 6] = [
        "source",
        "image_url",
        "input_image",
        "input_file",
        "file",
        "image",
    ];
    for key in NESTED_KEYS {
        if let Some(value) = item_dict.get_item(key)?
            && (value.cast::<PyDict>().is_ok() || value.cast::<PyList>().is_ok())
        {
            return Err(value_error(format!(
                "{NESTED_SHAPE_ERROR} (found nested '{key}' field)"
            )));
        }
    }
    Ok(())
}

fn decode_constructor_style(
    item_dict: &Bound<'_, PyDict>,
    block_type: &str,
    kind: MediaKind,
    base64_data: bool,
) -> PyResult<ContentBlock> {
    let label = format!("{block_type} content block");
    let media_type = string_field(item_dict, &label, "media_type")?;
    let name = optional_name(item_dict, &label)?;
    let source = if base64_data {
        BlockSource::Base64(required_string(item_dict, &label, "data")?)
    } else {
        BlockSource::Url(required_string(item_dict, &label, "url")?)
    };
    build_media_block(kind, source, name, media_type).map_err(value_error)
}

/// Parse one flat dict-shaped content block into a `ContentBlock`.
///
/// Accepted `type` values (all keys are flat strings, never nested dicts):
/// - `text`: `text`
/// - `image`: `data` (base64; `media_type` optional, defaults to `image/png`)
///   **or** `url` (exactly one)
/// - `image_url`: `url`
/// - `image_base64`: `data` (base64; `media_type` optional, defaults to
///   `image/png`)
/// - `document`: `data` (base64) **or** `url`, plus an explicit `media_type`
/// - `document_url`: `url` plus an explicit `media_type`
/// - `document_base64`: `data` (base64) plus an explicit `media_type`
///
/// `name` is optional for documents. Explicit `None` is rejected instead of
/// being treated as an absent key, an empty/whitespace-only `media_type` is
/// invalid, and `document*` never infers `media_type`. Nested DataBlock
/// shapes, OpenAI wire shapes and unknown `type` values raise `ValueError`
/// with a repair hint.
pub(crate) fn dict_content_block(item_dict: &Bound<'_, PyDict>) -> PyResult<ContentBlock> {
    reject_nested_shape(item_dict)?;
    let block_type = required_string(item_dict, "content block", "type")?;
    match block_type.as_str() {
        "text" => Ok(ContentBlock::Text {
            text: required_string(item_dict, "text content block", "text")?,
        }),
        "image" => {
            let label = "image content block";
            let url = string_field(item_dict, label, "url")?;
            let data = string_field(item_dict, label, "data")?;
            let media_type = string_field(item_dict, label, "media_type")?;
            let source = match (url, data) {
                (Some(_), Some(_)) => {
                    return Err(value_error(
                        "image content block must specify exactly one of 'data' (base64) or 'url', not both",
                    ));
                }
                (Some(url), None) => BlockSource::Url(url),
                (None, Some(data)) => BlockSource::Base64(data),
                (None, None) => {
                    return Err(value_error(format!(
                        "image content block requires 'data' (base64) or 'url'; supported flat types: {SUPPORTED_BLOCK_TYPES}"
                    )));
                }
            };
            build_media_block(MediaKind::Image, source, None, media_type).map_err(value_error)
        }
        "image_url" => {
            let label = "image_url content block";
            reject_field(
                item_dict,
                label,
                "data",
                "use {\"type\": \"image_base64\", \"data\": ...} or {\"type\": \"image\", \"data\": ...} for inline bytes",
            )?;
            reject_field(
                item_dict,
                label,
                "media_type",
                "URL images carry no media type",
            )?;
            let url = required_string(item_dict, label, "url")?;
            build_media_block(MediaKind::Image, BlockSource::Url(url), None, None)
                .map_err(value_error)
        }
        "image_base64" => {
            let label = "image_base64 content block";
            reject_field(
                item_dict,
                label,
                "url",
                "use {\"type\": \"image_url\", \"url\": ...} or {\"type\": \"image\", \"url\": ...} for URL images",
            )?;
            let data = required_string(item_dict, label, "data")?;
            let media_type = string_field(item_dict, label, "media_type")?;
            build_media_block(
                MediaKind::Image,
                BlockSource::Base64(data),
                None,
                media_type,
            )
            .map_err(value_error)
        }
        "document" => {
            let label = "document content block";
            let url = string_field(item_dict, label, "url")?;
            let data = string_field(item_dict, label, "data")?;
            let media_type = string_field(item_dict, label, "media_type")?;
            let name = optional_name(item_dict, label)?;
            if media_type.is_none() {
                return Err(value_error(
                    "document content block requires an explicit 'media_type' (e.g. \"application/pdf\"); it is never inferred",
                ));
            }
            let source = match (url, data) {
                (Some(_), Some(_)) => {
                    return Err(value_error(
                        "document content block must specify exactly one of 'data' (base64) or 'url', not both",
                    ));
                }
                (Some(url), None) => BlockSource::Url(url),
                (None, Some(data)) => BlockSource::Base64(data),
                (None, None) => {
                    return Err(value_error(
                        "document content block requires 'data' (base64) or 'url' alongside 'media_type'",
                    ));
                }
            };
            build_media_block(MediaKind::Document, source, name, media_type).map_err(value_error)
        }
        "document_url" => {
            let label = "document_url content block";
            reject_field(
                item_dict,
                label,
                "data",
                "use {\"type\": \"document_base64\", \"data\": ..., \"media_type\": ...} for inline bytes",
            )?;
            decode_constructor_style(item_dict, "document_url", MediaKind::Document, false)
        }
        "document_base64" => {
            let label = "document_base64 content block";
            reject_field(
                item_dict,
                label,
                "url",
                "use {\"type\": \"document_url\", \"url\": ..., \"media_type\": ...} for URL documents",
            )?;
            decode_constructor_style(item_dict, "document_base64", MediaKind::Document, true)
        }
        other => Err(value_error(format!(
            "unsupported content block type: {other:?}; supported flat types: {SUPPORTED_BLOCK_TYPES} — or return a bare str / senza.Attachment"
        ))),
    }
}

#[pymethods]
impl PyAttachment {
    #[new]
    #[pyo3(signature = (kind, data, name, media_type))]
    fn new(
        kind: &str,
        data: &str,
        name: Option<String>,
        media_type: Option<String>,
    ) -> PyResult<Self> {
        attachment_to_content_block(kind, data, name, media_type)
            .map(|block| Self { block })
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    fn __repr__(&self) -> String {
        match &self.block {
            ContentBlock::Image { source } => match source {
                ImageSource::Url { url } => format!("Attachment(image_url={url})"),
                ImageSource::Base64 { media_type, .. } => {
                    format!("Attachment(image_base64, {media_type})")
                }
            },
            ContentBlock::Document { name, .. } => {
                format!(
                    "Attachment(document, {})",
                    name.as_deref().unwrap_or("<unnamed>")
                )
            }
            _ => "Attachment(?)".to_string(),
        }
    }
}

#[cfg(test)]
mod attachment_tests {
    use super::{PyToolContext, attachment_to_content_block, dict_content_block};
    use crate::core::pytool::{ContentBlock, ImageSource};
    use llm_harness_types::{BinarySource, DataBlock};
    use pyo3::types::{PyAny, PyDict};
    use pyo3::{Bound, Python};
    use tokio_util::sync::CancellationToken;

    fn eval_json<'py>(py: Python<'py>, json: &str) -> Bound<'py, PyAny> {
        py.eval(std::ffi::CString::new(json).unwrap().as_c_str(), None, None)
            .unwrap()
    }

    fn parse_block(json: &str) -> Result<ContentBlock, String> {
        Python::attach(|py| {
            let value = eval_json(py, json);
            let dict = value.cast::<PyDict>().unwrap();
            dict_content_block(dict).map_err(|e| e.to_string())
        })
    }

    fn parse_block_err(json: &str) -> String {
        match parse_block(json) {
            Ok(block) => panic!("expected an error for {json}, got {block:?}"),
            Err(message) => message,
        }
    }

    fn assert_rejects(json: &str, needles: &[&str]) {
        let message = parse_block_err(json);
        for needle in needles {
            assert!(
                message.contains(needle),
                "error for {json} does not contain {needle:?}: {message}"
            );
        }
    }

    fn base64_image(block: &ContentBlock) -> (&str, &str) {
        match block {
            ContentBlock::Image {
                source: ImageSource::Base64 { media_type, data },
            } => (media_type, data),
            other => panic!("expected base64 image, got {other:?}"),
        }
    }

    fn url_image(block: &ContentBlock) -> &str {
        match block {
            ContentBlock::Image {
                source: ImageSource::Url { url },
            } => url,
            other => panic!("expected URL image, got {other:?}"),
        }
    }

    // ── accepted shapes ─────────────────────────────────────────────

    #[test]
    fn accepts_text_block() {
        match parse_block(r#"{"type": "text", "text": "hello"}"#).unwrap() {
            ContentBlock::Text { text } => assert_eq!(text, "hello"),
            other => panic!("expected text, got {other:?}"),
        }
    }

    #[test]
    fn accepts_qevos_image_data_block() {
        let block = parse_block(r#"{"type": "image", "media_type": "image/jpeg", "data": "AAAA"}"#)
            .unwrap();
        assert_eq!(base64_image(&block), ("image/jpeg", "AAAA"));
    }

    #[test]
    fn accepts_image_data_without_media_type_defaults_png() {
        let block = parse_block(r#"{"type": "image", "data": "AAAA"}"#).unwrap();
        assert_eq!(base64_image(&block), ("image/png", "AAAA"));
    }

    #[test]
    fn accepts_image_url_forms() {
        for shape in [
            r#"{"type": "image", "url": "https://x/y.png"}"#,
            r#"{"type": "image_url", "url": "https://x/y.png"}"#,
        ] {
            let block = parse_block(shape).unwrap();
            assert_eq!(url_image(&block), "https://x/y.png", "shape: {shape}");
        }
    }

    #[test]
    fn accepts_image_base64_shorthand() {
        let block = parse_block(r#"{"type": "image_base64", "data": "AAAA"}"#).unwrap();
        assert_eq!(base64_image(&block), ("image/png", "AAAA"));
        let block =
            parse_block(r#"{"type": "image_base64", "media_type": "image/webp", "data": "AAAA"}"#)
                .unwrap();
        assert_eq!(base64_image(&block), ("image/webp", "AAAA"));
    }

    #[test]
    fn accepts_document_data_block() {
        let block = parse_block(
            r#"{"type": "document", "name": "d.pdf", "media_type": "application/pdf", "data": "AAAA"}"#,
        )
        .unwrap();
        match block {
            ContentBlock::Document {
                name,
                media_type,
                data: BinarySource::Base64 { data },
            } => {
                assert_eq!(name.as_deref(), Some("d.pdf"));
                assert_eq!(media_type, "application/pdf");
                assert_eq!(data, "AAAA");
            }
            other => panic!("expected inline document, got {other:?}"),
        }
    }

    #[test]
    fn accepts_document_url_forms() {
        for shape in [
            r#"{"type": "document", "media_type": "application/pdf", "url": "https://x/d.pdf"}"#,
            r#"{"type": "document_url", "media_type": "application/pdf", "url": "https://x/d.pdf"}"#,
        ] {
            let block = parse_block(shape).unwrap();
            match block {
                ContentBlock::Document {
                    media_type,
                    data: BinarySource::Url { url },
                    ..
                } => {
                    assert_eq!(media_type, "application/pdf");
                    assert_eq!(url, "https://x/d.pdf");
                }
                other => panic!("expected URL document for {shape}, got {other:?}"),
            }
        }
    }

    #[test]
    fn accepts_document_base64_shorthand() {
        let block = parse_block(
            r#"{"type": "document_base64", "name": "d.pdf", "media_type": "application/pdf", "data": "AAAA"}"#,
        )
        .unwrap();
        assert!(matches!(
            block,
            ContentBlock::Document {
                data: BinarySource::Base64 { .. },
                ..
            }
        ));
    }

    // ── rejected shapes ─────────────────────────────────────────────

    #[test]
    fn rejects_nested_anthropic_image_source() {
        assert_rejects(
            r#"{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}}"#,
            &["nested content block shape is not accepted", "Attachment"],
        );
    }

    #[test]
    fn rejects_nested_datablock_document_data() {
        assert_rejects(
            r#"{"type": "document", "media_type": "application/pdf", "data": {"type": "base64", "data": "AAAA"}}"#,
            &["nested content block shape is not accepted"],
        );
    }

    #[test]
    fn rejects_openai_wire_image_url() {
        assert_rejects(
            r#"{"type": "image_url", "image_url": {"url": "https://x/y.png"}}"#,
            &["nested content block shape is not accepted", "image_url"],
        );
    }

    #[test]
    fn rejects_wrong_key_for_constructor_kinds() {
        assert_rejects(
            r#"{"type": "document_url", "media_type": "application/pdf", "data": "AAAA"}"#,
            &["does not accept 'data'", "document_base64"],
        );
        assert_rejects(
            r#"{"type": "document_base64", "media_type": "application/pdf", "url": "https://x/d.pdf"}"#,
            &["does not accept 'url'", "document_url"],
        );
        assert_rejects(
            r#"{"type": "image_base64", "url": "https://x/y.png"}"#,
            &["does not accept 'url'", "image_url"],
        );
        assert_rejects(
            r#"{"type": "image_url", "data": "AAAA"}"#,
            &["does not accept 'data'", "image_base64"],
        );
    }

    #[test]
    fn rejects_explicit_none_as_missing() {
        assert_rejects(
            r#"{"type": "image_base64", "data": None}"#,
            &["explicit None is not accepted"],
        );
        assert_rejects(
            r#"{"type": "image", "url": None}"#,
            &["explicit None is not accepted"],
        );
        assert_rejects(
            r#"{"type": "image", "data": "AAAA", "media_type": None}"#,
            &["explicit None is not accepted"],
        );
        assert_rejects(r#"{"type": None}"#, &["explicit None is not accepted"]);
    }

    #[test]
    fn rejects_non_string_fields() {
        assert_rejects(
            r#"{"type": "image", "data": 42}"#,
            &["'data' must be a string, got int"],
        );
        assert_rejects(
            r#"{"type": "image", "url": 42}"#,
            &["'url' must be a string, got int"],
        );
        assert_rejects(
            r#"{"type": "image", "data": "AAAA", "media_type": 42}"#,
            &["'media_type' must be a string, got int"],
        );
        assert_rejects(r#"{"type": 42}"#, &["'type' must be a string, got int"]);
    }

    #[test]
    fn document_requires_explicit_media_type() {
        for shape in [
            r#"{"type": "document", "data": "AAAA"}"#,
            r#"{"type": "document_url", "url": "https://x/d.pdf"}"#,
            r#"{"type": "document_base64", "data": "AAAA"}"#,
        ] {
            assert_rejects(shape, &["requires an explicit 'media_type'"]);
        }
    }

    #[test]
    fn empty_media_type_is_invalid() {
        assert_rejects(
            r#"{"type": "document", "media_type": "  ", "data": "AAAA"}"#,
            &["non-empty MIME type"],
        );
        assert_rejects(
            r#"{"type": "image", "media_type": "", "data": "AAAA"}"#,
            &["non-empty MIME type"],
        );
        assert_rejects(
            r#"{"type": "image_base64", "media_type": "", "data": "AAAA"}"#,
            &["non-empty MIME type"],
        );
    }

    #[test]
    fn rejects_both_data_and_url() {
        assert_rejects(
            r#"{"type": "image", "data": "AAAA", "url": "https://x/y.png"}"#,
            &["exactly one of 'data'"],
        );
        assert_rejects(
            r#"{"type": "document", "media_type": "application/pdf", "data": "AAAA", "url": "https://x/d.pdf"}"#,
            &["exactly one of 'data'"],
        );
    }

    #[test]
    fn rejects_media_type_on_url_image() {
        assert_rejects(
            r#"{"type": "image", "url": "https://x/y.png", "media_type": "image/png"}"#,
            &["do not accept 'media_type'"],
        );
        assert_rejects(
            r#"{"type": "image_url", "url": "https://x/y.png", "media_type": "image/png"}"#,
            &["does not accept 'media_type'"],
        );
    }

    #[test]
    fn rejects_unknown_and_missing_type() {
        assert_rejects(
            r#"{"type": "audio", "data": "x"}"#,
            &["unsupported content block type", "Attachment"],
        );
        assert_rejects(r#"{"data": "x"}"#, &["requires 'type'"]);
        assert_rejects(
            r#"{"type": "image"}"#,
            &["requires 'data' (base64) or 'url'"],
        );
    }

    #[test]
    fn rejects_document_without_locator() {
        assert_rejects(
            r#"{"type": "document", "media_type": "application/pdf"}"#,
            &["requires 'data' (base64) or 'url'"],
        );
    }

    // ── Attachment constructor parity ───────────────────────────────

    #[test]
    fn image_url_block() {
        let b = attachment_to_content_block("image_url", "https://x/y.png", None, None).unwrap();
        assert_eq!(url_image(&b), "https://x/y.png");
    }

    #[test]
    fn image_base64_defaults_png() {
        let b = attachment_to_content_block("image_base64", "AAAA", None, None).unwrap();
        assert_eq!(base64_image(&b), ("image/png", "AAAA"));
    }

    #[test]
    fn image_base64_empty_media_type_errors() {
        assert!(
            attachment_to_content_block("image_base64", "AAAA", None, Some(String::new())).is_err()
        );
    }

    #[test]
    fn image_url_rejects_media_type() {
        assert!(
            attachment_to_content_block(
                "image_url",
                "https://x/y.png",
                None,
                Some("image/png".into())
            )
            .is_err()
        );
    }

    #[test]
    fn document_requires_media_type() {
        assert!(
            attachment_to_content_block("document_url", "https://x/d.pdf", None, None).is_err()
        );
        assert!(attachment_to_content_block("document_base64", "AAAA", None, None).is_err());
    }

    #[test]
    fn document_base64_ok() {
        let b = attachment_to_content_block(
            "document_base64",
            "AAAA",
            Some("d.pdf".into()),
            Some("application/pdf".into()),
        )
        .unwrap();
        assert!(matches!(
            b,
            ContentBlock::Document {
                data: BinarySource::Base64 { .. },
                ..
            }
        ));
    }

    #[test]
    fn unknown_kind_errors() {
        assert!(attachment_to_content_block("audio", "x", None, None).is_err());
    }

    // ── send_update shares the same decoder ─────────────────────────

    #[test]
    fn send_update_accepts_image_and_document_blocks() {
        Python::attach(|py| {
            let value = eval_json(
                py,
                r#"{
                    "content": [
                        {"type": "image", "data": "AAAA"},
                        {"type": "document", "media_type": "application/pdf", "url": "https://x/d.pdf"}
                    ]
                }"#,
            );
            let dict = value.cast::<PyDict>().unwrap();
            let (tx, mut rx) = tokio::sync::mpsc::channel(4);
            let ctx = PyToolContext::new(CancellationToken::new(), tx);
            ctx.send_update(dict.as_any()).unwrap();
            let progress = rx.try_recv().unwrap();
            assert_eq!(progress.content.len(), 2);
            assert!(matches!(
                &progress.content[0],
                DataBlock::Image {
                    source: ImageSource::Base64 { media_type, data }
                } if media_type == "image/png" && data == "AAAA"
            ));
            assert!(matches!(
                &progress.content[1],
                DataBlock::Document {
                    media_type,
                    data: BinarySource::Url { url },
                    ..
                } if media_type == "application/pdf" && url == "https://x/d.pdf"
            ));
        });
    }

    #[test]
    fn send_update_rejects_nested_shape() {
        Python::attach(|py| {
            let value = eval_json(
                py,
                r#"{"content": [{"type": "image_url", "image_url": {"url": "https://x/y.png"}}]}"#,
            );
            let dict = value.cast::<PyDict>().unwrap();
            let (tx, _rx) = tokio::sync::mpsc::channel(4);
            let ctx = PyToolContext::new(CancellationToken::new(), tx);
            let err = ctx.send_update(dict.as_any()).unwrap_err().to_string();
            assert!(
                err.contains("nested content block shape is not accepted"),
                "unexpected error: {err}"
            );
        });
    }
}

/// 解析 Python 返回值为 `ToolResult`。
///
/// 期望 dict 形如：
/// ```python
/// {"content": [{"type": "text", "text": "..."}], "details": ..., "terminate": False}
/// ```
///
/// 另接受 `Attachment`（裸值 / list 元素 / content 列表元素）。
fn parse_tool_result(obj: &Bound<'_, PyAny>) -> PyResult<ToolResult> {
    // Bare Attachment return → single image/document block.
    if let Ok(att) = obj.extract::<Bound<'_, PyAttachment>>() {
        return match content_block_to_data_block(att.borrow().block()) {
            Some(block) => Ok(ToolResult::full(vec![block], Value::Null, false)),
            None => Err(pyo3::exceptions::PyValueError::new_err(
                "attachment is not image/document",
            )),
        };
    }
    // Accept plain string as shorthand for {"content": [{"type": "text", "text": <str>}]}
    if let Ok(s) = obj.extract::<String>() {
        return Ok(ToolResult::full(
            vec![DataBlock::text(s)],
            Value::Null,
            false,
        ));
    }
    // Sequence return (list or tuple): elements may be Attachment or str (mixed).
    let as_list: Option<Bound<'_, PyList>> = match obj.cast::<PyList>() {
        Ok(l) => Some(l.clone()),
        Err(_) => obj
            .cast::<pyo3::types::PyTuple>()
            .ok()
            .map(|t| PyList::new(obj.py(), t.iter()).expect("tuple to list conversion")),
    };
    if let Some(list) = as_list {
        let mut blocks = Vec::with_capacity(list.len());
        for item in list {
            if let Ok(att) = item.extract::<Bound<'_, PyAttachment>>() {
                match content_block_to_data_block(att.borrow().block()) {
                    Some(block) => blocks.push(block),
                    None => {
                        return Err(pyo3::exceptions::PyValueError::new_err(
                            "attachment is not image/document",
                        ));
                    }
                }
            } else if let Ok(s) = item.extract::<String>() {
                blocks.push(DataBlock::text(s));
            } else {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "list return items must be Attachment or str",
                ));
            }
        }
        return Ok(ToolResult::full(blocks, Value::Null, false));
    }
    let dict = obj.cast::<PyDict>()?;

    // If dict has no "content" key, treat the entire dict as a text content
    // block (JSON-serialized). Extract terminate if present.
    if dict.get_item("content")?.is_none() {
        let json_val = pyobject_to_value(obj)?;
        let json_str = serde_json::to_string(&json_val)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let terminate = dict
            .get_item("terminate")?
            .and_then(|v| v.extract::<bool>().ok())
            .unwrap_or(false);
        return Ok(ToolResult::full(
            vec![DataBlock::text(json_str)],
            Value::Null,
            terminate,
        ));
    }

    // content: 可选，缺省或 None → 空列表
    let content_vec = match dict.get_item("content")? {
        Some(v) if !v.is_none() => {
            let content_list = v.cast::<PyList>()?;
            let mut blocks = Vec::with_capacity(content_list.len());
            for item in content_list {
                // Attachment items are allowed alongside dicts.
                if let Ok(att) = item.extract::<Bound<'_, PyAttachment>>() {
                    match content_block_to_data_block(att.borrow().block()) {
                        Some(block) => blocks.push(block),
                        None => {
                            return Err(pyo3::exceptions::PyValueError::new_err(
                                "attachment is not image/document",
                            ));
                        }
                    }
                    continue;
                }
                let item_dict = item.cast::<PyDict>()?;
                let cb = dict_content_block(item_dict)?;
                match content_block_to_data_block(&cb) {
                    Some(block) => blocks.push(block),
                    None => {
                        return Err(pyo3::exceptions::PyValueError::new_err(
                            "content block is not a valid image/document/text block",
                        ));
                    }
                }
            }
            blocks
        }
        _ => vec![],
    };

    // details: 可选，缺省或 None → Null
    let details = match dict.get_item("details")? {
        Some(v) if !v.is_none() => pyobject_to_value(&v)?,
        _ => Value::Null,
    };

    // terminate: 可选，缺省或 None → false
    let terminate = dict
        .get_item("terminate")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(false);

    Ok(ToolResult::full(content_vec, details, terminate))
}

/// Python 侧的 tool context，暴露 `is_cancelled` 和 `send_update`。
#[pyclass(name = "ToolContext")]
pub struct PyToolContext {
    abort: CancellationToken,
    update_tx: tokio::sync::mpsc::Sender<ToolProgress>,
}

impl PyToolContext {
    pub fn new(
        abort: CancellationToken,
        update_tx: tokio::sync::mpsc::Sender<ToolProgress>,
    ) -> Self {
        Self { abort, update_tx }
    }
}

#[pymethods]
impl PyToolContext {
    /// 返回当前是否已收到取消信号。
    fn is_cancelled(&self) -> bool {
        self.abort.is_cancelled()
    }

    /// 推送一个部分结果（Python dict），解析后发送到 update channel。
    fn send_update(&self, result: &Bound<'_, PyAny>) -> PyResult<()> {
        let parsed = parse_tool_result(result)?;
        let progress = ToolProgress {
            content: parsed.model_content,
            details: parsed.details,
        };
        self.update_tx
            .try_send(progress)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    }
}

/// 持有 `PyTool` 的不透明 Python 包装，供 Python 侧引用已注册的 tool。
#[pyclass(name = "Tool")]
pub struct PyToolWrapper {
    pub tool: Arc<PyTool>,
}

#[pymethods]
impl PyToolWrapper {
    /// 返回 tool 的名称。
    #[getter]
    fn name(&self) -> &str {
        self.tool.name()
    }

    /// 返回 tool 的描述。
    #[getter]
    fn description(&self) -> &str {
        self.tool.description()
    }

    /// 同步驱动 tool.execute：在独立 tokio runtime 上运行 async future。
    ///
    /// 仅供测试/验证使用；真实场景由 agent loop 调用 `execute`。
    #[cfg(feature = "test-utils")]
    fn drive(&self, args: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = args.py();
        let args_val = crate::shared::value_conv::pyobject_to_value(args)?;
        let tool = self.tool.clone();
        // 在 Python 释放 GIL 后运行 tokio runtime，避免 GIL 与 runtime 死锁。
        // panic 隔离：Rust panic 转为 RustPanicError。
        crate::shared::pyerror::detach_catch_panic(py, move || {
            let rt = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .map_err(|e| {
                    pyo3::exceptions::PyRuntimeError::new_err(format!(
                        "failed to create runtime: {e}"
                    ))
                })?;
            rt.block_on(async move {
                let ctx = build_test_ctx();
                let result = tool
                    .execute(args_val, &ctx)
                    .await
                    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
                Python::attach(|py| toolresult_to_pyobject(py, &result))
            })
        })?
    }
}

/// 构造测试用 `ToolContext`（不依赖完整 agent loop）。
#[cfg(feature = "test-utils")]
fn build_test_ctx() -> ToolContext {
    use llm_harness_loop::test_utils::{NoOpEnv, test_assistant_message};
    ToolContext {
        run: Arc::new(RunContext::new(RunRequest::default())),
        env: Arc::new(NoOpEnv),
        abort: CancellationToken::new(),
        tool_use_id: "test".into(),
        turn_index: 0,
        assistant_message: Arc::new(test_assistant_message(vec![])),
        update_tx: tokio::sync::mpsc::channel(1).0,
    }
}

/// 将 `ToolResult` 转换为 Python dict。
#[cfg(feature = "test-utils")]
fn toolresult_to_pyobject(py: Python<'_>, result: &ToolResult) -> PyResult<Py<PyAny>> {
    let dict = PyDict::new(py);
    let content_list = PyList::empty(py);
    for block in &result.model_content {
        let block_json: Value = serde_json::to_value(block)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        content_list.append(value_to_pyobject(py, &block_json)?)?;
    }
    dict.set_item("content", content_list)?;
    dict.set_item("details", value_to_pyobject(py, &result.details)?)?;
    dict.set_item("terminate", result.terminate)?;
    Ok(dict.into_any().unbind())
}
