import senza
import tempfile
import os


def test_audit_plugin_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        sink_path = os.path.join(tmpdir, "audit.jsonl")
        plugin = senza.strategy.audit(sink_path)
        assert plugin is not None


def test_audit_plugin_with_trace_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        sink_path = os.path.join(tmpdir, "audit.jsonl")
        plugin = senza.strategy.audit(sink_path, trace_id="trace-123", task_id="task-456")
        assert plugin is not None


def test_audit_plugin_in_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        sink_path = os.path.join(tmpdir, "audit.jsonl")
        provider = senza.providers.openai(api_key="sk-test")
        plugin = senza.strategy.audit(sink_path)
        harness = (
            senza.HarnessBuilder("gpt-4o")
            .provider("*", provider)
            .plugin(plugin)
            .build()
        )
        assert harness is not None
