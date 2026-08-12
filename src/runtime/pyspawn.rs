//! Sub-agent spawn infrastructure — Python-facing `enable_spawn()` wiring.
//!
//! Mirrors the runtime's `WorkflowEngine` spawn assembly:
//! 1. `MessageBus` via `message_bus_pair()`.
//! 2. `HarnessSubAgentSpawner` (model, client, session_dir, bus, NoopPlugin).
//! 3. `AsyncSpawnHook` via `async_spawn_pair(bus)`.
//! 4. Five tools: `SpawnAgentTool`, `MessageSubagentTool`, `AwaitSubagentReplyTool`,
//!    `QuerySubagentTool`, `AbortSubagentTool`.
//! 5. Builder: tools + `after_turn_hook(async_hook)` + `convert_to_llm(...)`.
//! 6. Post-build: `set_idle_watcher`, `set_async_spawn_hook`, `set_abort_cascade_hook`.

use std::path::Path;
use std::sync::Arc;

use llm_harness_agent::{AgentHarness, Plugin};
use llm_harness_loop::convert::DefaultConvertToLlm;
use llm_harness_runtime::builder::HarnessBuilder;
use llm_harness_runtime::spawn::delivery::{
    AsyncSpawnHook, IdleWatcher, SubAgentMessageConverter, async_spawn_pair,
};
use llm_harness_runtime::spawn::message_bus::{MAIN_AGENT_ID, message_bus_pair};
use llm_harness_runtime::spawn::spawner::{HarnessSubAgentSpawner, JsonlSessionFactory};
use llm_harness_runtime::spawn::tools::{
    AbortSubagentTool, AwaitSubagentReplyTool, MessageSubagentTool, QuerySubagentTool,
    SpawnAgentTool,
};
use llm_harness_runtime_sandbox_os::OsEnvFactory;
use llm_harness_types::Tool;

/// Post-build spawn wiring state. Held across `build()` and applied
/// to the constructed `AgentHarness`.
pub(crate) struct SpawnWiring {
    bus: Arc<llm_harness_runtime::spawn::message_bus::MessageBus>,
    async_hook: Arc<AsyncSpawnHook>,
}

impl SpawnWiring {
    /// Apply post-build hooks: `set_idle_watcher`, `set_async_spawn_hook`,
    /// `set_abort_cascade_hook`. Must be called after `build()` returns the harness.
    pub(crate) fn post_build(&self, harness: &Arc<AgentHarness>) {
        let watcher = IdleWatcher::new(self.bus.clone(), {
            let h = Arc::downgrade(harness);
            Arc::new(move || {
                let h = h.clone();
                Box::pin(async move {
                    if let Some(h) = h.upgrade() {
                        let _ = h.continue_run().await;
                    }
                })
            })
        });
        harness.set_idle_watcher(Arc::new(watcher));
        harness.set_async_spawn_hook(self.async_hook.clone());
        harness.set_abort_cascade_hook(self.bus.clone());
    }
}

/// A no-op plugin for sub-agents — prevents recursive spawning.
struct NoopPlugin;

impl Plugin for NoopPlugin {
    fn name(&self) -> &str {
        "senza-noop-spawn"
    }
}

/// Wire spawn infrastructure into the builder and return post-build wiring state.
///
/// - Adds `SpawnAgentTool`, `MessageSubagentTool`, `AwaitSubagentReplyTool`,
///   `QuerySubagentTool`, `AbortSubagentTool` to the builder.
/// - Sets `after_turn_hook(async_hook)` and `convert_to_llm(DefaultConvertToLlm + SubAgentMessageConverter)`.
/// - Returns `(modified_builder, SpawnWiring)` for post-build hook application.
pub(crate) fn wire_spawn(
    mut builder: HarnessBuilder,
    cfg: crate::core::pybuilder::SpawnConfig,
) -> (HarnessBuilder, Option<SpawnWiring>) {
    // 1. Message bus.
    let bus = message_bus_pair();

    // 2. Spawner.
    let spawner = HarnessSubAgentSpawner::new(
        cfg.model,
        cfg.client,
        cfg.session_dir,
        bus.clone(),
        |_cwd: &Path, _bus, _agent_id: &str| Box::new(NoopPlugin) as Box<dyn Plugin>,
    )
    .env_factory(Arc::new(OsEnvFactory))
    .session_factory(Arc::new(JsonlSessionFactory));
    let spawner = Arc::new(spawner);

    // 3. Async spawn hook.
    let async_hook = async_spawn_pair(bus.clone());

    // 4. Register tools + after_turn_hook + convert_to_llm.
    builder = builder
        .tool(Arc::new(SpawnAgentTool::new(spawner.clone())) as Arc<dyn Tool>)
        .tool(Arc::new(MessageSubagentTool::new(bus.clone(), MAIN_AGENT_ID)) as Arc<dyn Tool>)
        .tool(Arc::new(AwaitSubagentReplyTool::new(bus.clone(), MAIN_AGENT_ID)) as Arc<dyn Tool>)
        .tool(Arc::new(QuerySubagentTool::new(bus.clone())) as Arc<dyn Tool>)
        .tool(Arc::new(AbortSubagentTool::new(bus.clone())) as Arc<dyn Tool>)
        .after_turn_hook(async_hook.clone())
        .convert_to_llm(Some(Arc::new(
            DefaultConvertToLlm::new().with_custom_converter(Arc::new(SubAgentMessageConverter)),
        )));

    (builder, Some(SpawnWiring { bus, async_hook }))
}
