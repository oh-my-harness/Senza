"""Smoke tests for compaction_model builder method (G5)."""
import senza as lh


def _make_provider():
    return lh.create_openai_provider(api_key="test-key")


def test_compaction_model_chains():
    """compaction_model() chains and returns self."""
    builder = lh.HarnessBuilder("gpt-4o").provider("gpt-*", _make_provider())
    result = builder.compaction_model("gpt-4o-mini", context_window=128000, max_tokens=16384)
    assert result is builder


def test_compaction_model_then_build():
    """builder with compaction_model set can build successfully."""
    harness = (
        lh.HarnessBuilder("gpt-4o")
        .provider("gpt-*", _make_provider())
        .compaction_model("gpt-4o", context_window=128000, max_tokens=16384)
        .build()
    )
    assert harness is not None
