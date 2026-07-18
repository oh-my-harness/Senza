//! Rust 集成测试：PyJudge 和 PyExecutor 在真实 WorkflowEngine 中端到端运行。
//!
//! 需要 Python 解释器，用 `cargo test --test workflow_integration -- --ignored` 运行。
//! 前置：`maturin develop` 或设置 PYTHONPATH。

use std::sync::Arc;

use llm_harness_loop::test_utils::{MockLlmClient, MockResponse, NoOpEnv};
use llm_harness_runtime::spawn::spawner::{EnvFactory, JsonlSessionFactory};
use llm_harness_runtime::workflow::engine::{WorkflowEngine, WorkflowEngineConfig};
use llm_harness_runtime::workflow::judge::StepTransitionJudge;
use llm_harness_runtime::workflow::model::{Edge, Step, Workflow};
use llm_harness_types::{AgentError, ExecutionEnv};
use senza::pyworkflow::{PyExecutor, PyJudge};

// ── 测试用 EnvFactory ───────────────────────────────────────────────────────

struct NoopEnvFactory;
impl EnvFactory for NoopEnvFactory {
    fn create(&self, _cwd: &std::path::Path) -> Result<Arc<dyn ExecutionEnv>, AgentError> {
        Ok(Arc::new(NoOpEnv))
    }
}

// ── 辅助函数 ─────────────────────────────────────────────────────────────────

fn make_config(
    client: Arc<dyn llm_harness_loop::LlmClient>,
    dir: &std::path::Path,
) -> WorkflowEngineConfig {
    WorkflowEngineConfig {
        client,
        model: "mock-model".into(),
        env_factory: Arc::new(NoopEnvFactory),
        session_factory: Arc::new(JsonlSessionFactory),
        session_base_dir: dir.join("sessions"),
        customize_builder: None,
    }
}

// ── 测试 1：PyJudge 在两步 workflow 中路由 ───────────────────────────────────

/// 验证 PyJudge 能在 WorkflowEngine 中驱动步骤转换。
/// Python judge 返回 "to:step2"，引擎应执行 step1 → step2 → 完成。
#[tokio::test]
#[ignore = "requires Python interpreter — run with --ignored"]
async fn python_judge_routes_between_steps() {
    let dir = tempfile::TempDir::new().unwrap();

    let client = Arc::new(MockLlmClient::new(vec![
        MockResponse::text("step1 done"),
        MockResponse::text("step2 done"),
    ]));

    // Python judge: step1 → step2, step2 → abort("done")
    let judge = pyo3::Python::attach(|py| {
        let cb = py
            .eval(
                c"lambda ctx: \"to:step2\" if ctx[\"step_id\"] == \"step1\" else \"abort:done\"",
                None,
                None,
            )
            .unwrap()
            .unbind();
        Arc::new(PyJudge::new(cb)) as Arc<dyn StepTransitionJudge>
    });

    let workflow = Workflow {
        entry_step: "step1".into(),
        steps: vec![
            Step::llm("step1", "Step 1", "do step 1", vec![]),
            Step::llm("step2", "Step 2", "do step 2", vec![]),
        ],
        // validate_workflow 要求非 entry 步骤必须有 incoming edge
        edges: vec![Edge {
            from: "step1".into(),
            to: "step2".into(),
            condition: None,
        }],
    };

    let config = make_config(client, dir.path());
    let engine = WorkflowEngine::new(workflow, config, judge).unwrap();
    let result = engine.run().await;

    assert!(result.is_ok(), "workflow failed: {:?}", result.err());
    let result = result.unwrap();
    assert_eq!(result.turns, 2, "should have completed 2 steps");
}

// ── 测试 2：PyExecutor 作为非 LLM 步骤执行器 ────────────────────────────────

/// 验证 PyExecutor 能在 WorkflowEngine 中执行非 LLM 步骤。
/// Executor 步骤返回 structured 数据，judge 据此路由。
#[tokio::test]
#[ignore = "requires Python interpreter — run with --ignored"]
async fn python_executor_runs_as_step() {
    let dir = tempfile::TempDir::new().unwrap();

    let client = Arc::new(MockLlmClient::new(vec![MockResponse::text(
        "llm step done",
    )]));

    // Python executor: 返回固定结果
    let executor = Arc::new(pyo3::Python::attach(|py| {
        let cb = py
            .eval(
                c"lambda ctx: {\"output\": \"exec_result\", \"structured\": {\"status\": \"ok\"}}",
                None,
                None,
            )
            .unwrap()
            .unbind();
        PyExecutor::new(cb)
    }));

    // Python judge: llm step → to:exec1, executor step → abort("done")
    let judge = pyo3::Python::attach(|py| {
        let cb = py
            .eval(
                c"lambda ctx: \"to:exec1\" if ctx[\"step_id\"] == \"llm1\" else \"abort:done\"",
                None,
                None,
            )
            .unwrap()
            .unbind();
        Arc::new(PyJudge::new(cb)) as Arc<dyn StepTransitionJudge>
    });

    let workflow = Workflow {
        entry_step: "llm1".into(),
        steps: vec![
            Step::llm("llm1", "LLM Step", "do llm step", vec![]),
            Step::executor("exec1", "Exec Step", "py_executor", None),
        ],
        edges: vec![Edge {
            from: "llm1".into(),
            to: "exec1".into(),
            condition: None,
        }],
    };

    let config = make_config(client, dir.path());
    let engine = WorkflowEngine::new(workflow, config, judge)
        .unwrap()
        .with_executor("py_executor", executor);

    let result = engine.run().await;

    assert!(result.is_ok(), "workflow failed: {:?}", result.err());
    let result = result.unwrap();
    assert_eq!(
        result.turns, 2,
        "should have completed 2 steps (llm + executor)"
    );
}

// ── 测试 3：PyJudge 返回 retry ────────────────────────────────────────────────

/// 验证 PyJudge 返回 "retry" 时引擎重试当前步。
#[tokio::test]
#[ignore = "requires Python interpreter — run with --ignored"]
async fn python_judge_retry_transition() {
    let dir = tempfile::TempDir::new().unwrap();

    // step1 第一次执行 → judge 返回 retry → step1 第二次执行 → judge 返回 abort
    let client = Arc::new(MockLlmClient::new(vec![
        MockResponse::text("attempt1"),
        MockResponse::text("attempt2"),
    ]));

    // 用 eval 创建一个带闭包计数的 lambda：
    // 通过 list iterator 模拟计数器，第一次调用返回 "retry"，之后返回 "abort:done"
    let judge = pyo3::Python::attach(|py| {
        // 先 exec 创建模块级变量，再 eval 取出 judge 函数
        py.run(
            cr#"
_counter = [0]
def _judge(ctx):
    n = _counter[0]
    _counter[0] += 1
    if n == 0:
        return "retry"
    return "abort:done"
"#,
            None,
            None,
        )
        .unwrap();
        let cb = py.eval(c"_judge", None, None).unwrap().unbind();
        Arc::new(PyJudge::new(cb)) as Arc<dyn StepTransitionJudge>
    });

    let workflow = Workflow {
        entry_step: "s1".into(),
        steps: vec![Step::llm("s1", "Step 1", "do step 1", vec![])],
        edges: vec![],
    };

    let config = make_config(client, dir.path());
    let engine = WorkflowEngine::new(workflow, config, judge).unwrap();
    let result = engine.run().await;

    assert!(result.is_ok(), "workflow failed: {:?}", result.err());
}
