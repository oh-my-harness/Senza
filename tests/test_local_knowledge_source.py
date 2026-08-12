import senza
import tempfile
import os


def test_local_knowledge_source_creates():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test markdown file
        with open(os.path.join(tmpdir, "test.md"), "w") as f:
            f.write("# Test\nThis is a test document.\n")
        source = senza.knowledge.local_source(
            path=tmpdir,
            source_id="test-docs",
            name="Test Documents",
        )
        assert source is not None


def test_local_knowledge_source_with_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "doc1.md"), "w") as f:
            f.write("# Doc 1\nContent here.\n")
        source = senza.knowledge.local_source(
            path=tmpdir,
            source_id="my-docs",
            name="My Docs",
            description="A collection of documents",
            domains=["general"],
            max_document_bytes=1048576,
        )
        assert source is not None
