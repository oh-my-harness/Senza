use std::sync::{Arc, Mutex};

use futures::future::BoxFuture;
use llm_harness_runtime_knowledge::{KnowledgeError, KnowledgeRef, KnowledgeRequestContext};
use llm_harness_runtime_memory::{
    MemoryConsistency, MemoryDeleteReceipt, MemoryMutationGate, MemoryMutationGateError,
    MemoryMutationRequest, MemoryStore, MemoryStoreDescriptor, MemoryVisibility, MemoryWrite,
    MemoryWritePolicy, MemoryWriteReceipt, SecureMemoryWritePolicy, SecureMemoryWritePolicyConfig,
};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use tokio_util::sync::CancellationToken;

use crate::core::pyplugin::PyPluginWrapper;
use crate::knowledge::pylocalsource::PyKnowledgeSource;

// ── InMemoryStore (Senza-side impl; runtime does not provide one) ───────

pub struct InMemoryStore {
    descriptor: MemoryStoreDescriptor,
    entries: Mutex<Vec<(KnowledgeRef, Vec<u8>)>>,
}

impl InMemoryStore {
    pub fn new(read_source_id: String) -> Self {
        Self {
            descriptor: MemoryStoreDescriptor {
                read_source_id,
                consistency: MemoryConsistency::Immediate,
            },
            entries: Mutex::new(Vec::new()),
        }
    }
}

impl MemoryStore for InMemoryStore {
    fn descriptor(&self) -> &MemoryStoreDescriptor {
        &self.descriptor
    }

    fn upsert<'a>(
        &'a self,
        _ctx: KnowledgeRequestContext<'a>,
        write: MemoryWrite,
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<MemoryWriteReceipt, KnowledgeError>> {
        Box::pin(async move {
            let item_id = format!("mem-{}", write.idempotency_key);
            let revision =
                llm_harness_runtime_knowledge_local::content_revision(write.content.as_bytes());
            let reference = KnowledgeRef {
                source_id: self.descriptor.read_source_id.clone(),
                item_id,
                revision: Some(revision),
            };
            let mut entries = self.entries.lock().unwrap();
            // Upsert: replace existing entry with same item_id, or append
            if let Some(pos) = entries.iter().position(|(r, _)| r.item_id == reference.item_id) {
                entries[pos] = (reference.clone(), write.content.into_bytes());
            } else {
                entries.push((reference.clone(), write.content.into_bytes()));
            }
            Ok(MemoryWriteReceipt {
                reference,
                visibility: MemoryVisibility::Visible,
            })
        })
    }

    fn delete<'a>(
        &'a self,
        _ctx: KnowledgeRequestContext<'a>,
        reference: KnowledgeRef,
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<MemoryDeleteReceipt, KnowledgeError>> {
        Box::pin(async move {
            self.entries
                .lock()
                .unwrap()
                .retain(|(r, _)| r != &reference);
            Ok(MemoryDeleteReceipt {
                reference,
                visibility: MemoryVisibility::Visible,
            })
        })
    }
}

// ── AllowAllGate (permissive mutation gate) ─────────────────────────────

pub struct AllowAllGate;

impl MemoryMutationGate for AllowAllGate {
    fn authorize<'a>(
        &'a self,
        _ctx: KnowledgeRequestContext<'a>,
        _request: MemoryMutationRequest,
        _abort: CancellationToken,
    ) -> BoxFuture<'a, Result<(), MemoryMutationGateError>> {
        Box::pin(async { Ok(()) })
    }
}

// ── Opaque Python wrappers ──────────────────────────────────────────────

/// Opaque memory store handle (from create_in_memory_store).
#[pyclass(name = "MemoryStore")]
pub struct PyMemoryStore {
    pub store: Arc<dyn MemoryStore>,
}

/// Opaque memory write policy handle (from create_secure_write_policy).
#[pyclass(name = "MemoryWritePolicy")]
pub struct PyMemoryWritePolicy {
    pub policy: Arc<dyn MemoryWritePolicy>,
}

/// Opaque memory mutation gate handle (from create_allow_all_gate).
#[pyclass(name = "MemoryMutationGate")]
pub struct PyMemoryMutationGate {
    pub gate: Arc<dyn MemoryMutationGate>,
}

// ── Factory functions ───────────────────────────────────────────────────

/// Create a simple in-memory store backed by a `Mutex<Vec>`.
///
/// The `read_source_id` MUST match the `source_id` of the `KnowledgeSource`
/// that will be paired with this store in `create_memory_plugin`.
#[pyfunction]
pub fn create_in_memory_store<'py>(
    py: Python<'py>,
    read_source_id: &str,
) -> PyResult<Bound<'py, PyMemoryStore>> {
    let store: Arc<dyn MemoryStore> = Arc::new(InMemoryStore::new(read_source_id.to_string()));
    Py::new(py, PyMemoryStore { store }).map(|p| p.into_bound(py))
}

/// Create a secure memory write policy with HMAC-based idempotency.
///
/// Args:
///     config: Optional dict with "max_content_bytes" (int, default 16384)
///             and "max_ttl_seconds" (int, default 31536000).
#[pyfunction]
#[pyo3(signature = (config=None))]
pub fn create_secure_write_policy<'py>(
    py: Python<'py>,
    config: Option<&Bound<'_, PyDict>>,
) -> PyResult<Bound<'py, PyMemoryWritePolicy>> {
    let mut cfg = SecureMemoryWritePolicyConfig::default();
    if let Some(dict) = config {
        if let Some(v) = dict
            .get_item("max_content_bytes")?
            .and_then(|v| v.extract::<usize>().ok())
        {
            cfg.max_content_bytes = v;
        }
        if let Some(v) = dict
            .get_item("max_ttl_seconds")?
            .and_then(|v| v.extract::<u64>().ok())
        {
            cfg.max_ttl = std::time::Duration::from_secs(v);
        }
    }

    let secret: Vec<u8> = (0..32).map(|i| i as u8).collect();
    let policy = SecureMemoryWritePolicy::new(secret, cfg)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let policy: Arc<dyn MemoryWritePolicy> = Arc::new(policy);
    Py::new(py, PyMemoryWritePolicy { policy }).map(|p| p.into_bound(py))
}

/// Create a permissive mutation gate that always approves mutations.
///
/// This is the default gate used by `create_memory_plugin` when `gate` is
/// not provided. Use this explicitly only when you need a standalone handle.
#[pyfunction]
pub fn create_allow_all_gate<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyMemoryMutationGate>> {
    let gate: Arc<dyn MemoryMutationGate> = Arc::new(AllowAllGate);
    Py::new(py, PyMemoryMutationGate { gate }).map(|p| p.into_bound(py))
}

/// Create a MemoryPlugin that registers memory_write and memory_forget tools.
///
/// Args:
///     source: KnowledgeSource to read from (must have Search, Read, Revisioned).
///     store: MemoryStore to write to (from create_in_memory_store).
///     policy: MemoryWritePolicy to validate writes (from create_secure_write_policy).
///     gate: Optional MemoryMutationGate (defaults to AllowAllGate).
///
/// IMPORTANT: `source.descriptor().id` must equal `store.descriptor().read_source_id`.
/// Use the same string for `source_id` in `create_local_knowledge_source` and
/// `read_source_id` in `create_in_memory_store`.
#[pyfunction]
#[pyo3(signature = (source, store, policy, gate=None))]
pub fn create_memory_plugin<'py>(
    py: Python<'py>,
    source: &Bound<'_, PyKnowledgeSource>,
    store: &Bound<'_, PyMemoryStore>,
    policy: &Bound<'_, PyMemoryWritePolicy>,
    gate: Option<&Bound<'_, PyMemoryMutationGate>>,
) -> PyResult<Bound<'py, PyPluginWrapper>> {
    let src_arc = source.borrow().source.clone();
    let store_arc = store.borrow().store.clone();
    let policy_arc = policy.borrow().policy.clone();

    let gate: Arc<dyn MemoryMutationGate> = if let Some(g) = gate {
        g.borrow().gate.clone()
    } else {
        Arc::new(AllowAllGate)
    };

    let access_control = Arc::new(llm_harness_runtime_knowledge::KnowledgeAccessControl::new(
        Arc::new(llm_harness_runtime_knowledge::AllowAllAuthorizer),
    ));

    let service = llm_harness_runtime_memory::MemoryService::new(
        access_control,
        src_arc,
        store_arc,
        policy_arc,
        gate,
    )
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let plugin: Arc<dyn llm_harness_agent::Plugin> = Arc::new(
        llm_harness_runtime_memory::MemoryPlugin::new(Arc::new(service)),
    );
    Py::new(py, PyPluginWrapper::new(plugin)).map(|p| p.into_bound(py))
}
