import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

from academy.common import load_trace


LAB_DIR = Path(__file__).resolve().parent
if str(LAB_DIR) not in sys.path:
    sys.path.insert(0, str(LAB_DIR))


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, LAB_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RETRIEVAL = _load_module("senza_academy_lab07_retrieval", "retrieval.py")
DEMO = _load_module("senza_academy_lab07_demo", "demo.py")


def test_fixture_index_has_three_senza_documents():
    documents = RETRIEVAL.load_fixture_documents()

    assert [document.doc_id for document in documents] == [
        "agent_core.md",
        "knowledge_bm25.md",
        "memory_recall.md",
    ]


def test_bm25_ranks_knowledge_and_memory_evidence_first():
    index = RETRIEVAL.BM25Index(RETRIEVAL.load_fixture_documents())

    knowledge_hits = index.search("local_source BM25 knowledge_search knowledge_read")
    memory_hits = index.search("MemoryStore Mutex Vec persistence projector recall")

    assert knowledge_hits[0].document.doc_id == "knowledge_bm25.md"
    assert memory_hits[0].document.doc_id == "memory_recall.md"
    assert [hit.score for hit in knowledge_hits] == sorted(
        (hit.score for hit in knowledge_hits), reverse=True
    )
    assert [hit.score for hit in memory_hits] == sorted(
        (hit.score for hit in memory_hits), reverse=True
    )


def test_cli_defaults_to_offline_evidence_and_delegates_live_rag():
    args = DEMO.build_parser().parse_args([])

    assert args.mode == "recorded"
    assert DEMO.LIVE_EXAMPLES == {
        "rag": "36_rag_qa.py",
        "infra": "23_infra_integration.py",
    }
    completed = subprocess.run(
        [sys.executable, str(LAB_DIR / "demo.py"), "--top-k", "1"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Offline BM25 evidence" in completed.stdout
    assert "1. knowledge_bm25.md" in completed.stdout
    assert "1. memory_recall.md" in completed.stdout


def test_trace_separates_knowledge_from_memory_and_stays_preview():
    trace = load_trace(LAB_DIR / "expected_trace.json")

    assert trace["maturity"] == "preview"
    assert {event["kind"] for event in trace["events"]} >= {"knowledge", "memory"}
    assert trace["live_examples"][0] == "36_rag_qa.py"


def test_boundary_text_rejects_fake_memory_and_recall_e2e():
    trace = load_trace(LAB_DIR / "expected_trace.json")
    readme = (LAB_DIR / "README.md").read_text(encoding="utf-8")
    boundary_text = "\n".join(trace["boundaries"])

    for required in (
        "Mutex<Vec>",
        "不持久化",
        "不会自动同步到 local_source",
        "projector/index population",
        "不声称 Memory 或 Recall 端到端成功",
    ):
        assert required in boundary_text

    assert "Senza 的 `local_source` 对本地文本和 Markdown 使用 BM25" in readme
    assert "gate=None" in readme and "AllowAllGate" in readme
    assert "只能证明对象可装配，不能证明它能召回过去会话" in readme
    assert "36_rag_qa.py" in readme


def test_lab_python_has_no_direct_senza_dependency():
    for filename in ("demo.py", "retrieval.py", "test_demo.py"):
        source = (LAB_DIR / filename).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=filename)
        imported_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_roots.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert "senza" not in imported_roots
