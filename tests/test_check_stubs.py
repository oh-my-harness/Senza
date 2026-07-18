"""Tests for check_stubs.py signature parsing and comparison."""
import sys
import textwrap
from pathlib import Path

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from check_stubs import FuncSig, parse_pyi_signatures


def test_parse_module_level_function():
    pyi = textwrap.dedent('''
        def create_tool(name: str, callback: Callable[..., Any]) -> Tool: ...
    ''')
    sigs = parse_pyi_signatures.from_string(pyi)
    assert "create_tool" in sigs
    assert sigs["create_tool"].params == ["name", "callback"]
    assert sigs["create_tool"].defaults == set()


def test_parse_function_with_defaults():
    pyi = textwrap.dedent('''
        def create_openai_provider(
            api_key: str,
            base_url: Optional[str] = ...,
            parse_reasoning_content: bool = ...,
        ) -> Provider: ...
    ''')
    sigs = parse_pyi_signatures.from_string(pyi)
    sig = sigs["create_openai_provider"]
    assert sig.params == ["api_key", "base_url", "parse_reasoning_content"]
    assert sig.defaults == {"base_url", "parse_reasoning_content"}


def test_parse_class_method():
    pyi = textwrap.dedent('''
        class HarnessBuilder:
            def provider(self, pattern: str, provider: Provider) -> HarnessBuilder: ...
            def build(self) -> AgentHarness: ...
    ''')
    sigs = parse_pyi_signatures.from_string(pyi)
    assert "HarnessBuilder.provider" in sigs
    assert sigs["HarnessBuilder.provider"].params == ["self", "pattern", "provider"]
    assert "HarnessBuilder.build" in sigs
    assert sigs["HarnessBuilder.build"].params == ["self"]


from check_stubs import compare_signatures, introspect_runtime_signatures, FuncSig


def test_compare_missing_in_pyi():
    """Function in runtime but not in .pyi → diff."""
    pyi_sigs = {"version": FuncSig(params=[], defaults=set())}
    rt_sigs = {
        "version": FuncSig(params=[], defaults=set()),
        "secret_new_fn": FuncSig(params=["x"], defaults=set()),
    }
    diffs = compare_signatures(pyi_sigs, rt_sigs)
    assert any("secret_new_fn" in d and "not in .pyi" in d for d in diffs)


def test_compare_missing_in_runtime():
    """Function in .pyi but not in runtime → diff."""
    pyi_sigs = {
        "version": FuncSig(params=[], defaults=set()),
        "ghost_fn": FuncSig(params=["x"], defaults=set()),
    }
    rt_sigs = {"version": FuncSig(params=[], defaults=set())}
    diffs = compare_signatures(pyi_sigs, rt_sigs)
    assert any("ghost_fn" in d and "not in runtime" in d for d in diffs)


def test_compare_param_mismatch():
    """Same function, different params → diff."""
    pyi_sigs = {"create_tool": FuncSig(params=["name", "callback"], defaults=set())}
    rt_sigs = {"create_tool": FuncSig(params=["name", "cb"], defaults=set())}
    diffs = compare_signatures(pyi_sigs, rt_sigs)
    assert any("create_tool" in d and "param" in d.lower() for d in diffs)


def test_compare_default_mismatch():
    """Param has default in runtime but not in .pyi → diff."""
    pyi_sigs = {"fn": FuncSig(params=["a", "b"], defaults=set())}
    rt_sigs = {"fn": FuncSig(params=["a", "b"], defaults={"b"})}
    diffs = compare_signatures(pyi_sigs, rt_sigs)
    assert any("fn" in d and "default" in d.lower() for d in diffs)


def test_compare_identical():
    """Identical signatures → no diff."""
    pyi_sigs = {"fn": FuncSig(params=["a", "b"], defaults={"b"})}
    rt_sigs = {"fn": FuncSig(params=["a", "b"], defaults={"b"})}
    assert compare_signatures(pyi_sigs, rt_sigs) == []


def test_compare_skips_dunder_body():
    """__init__ etc. only check existence, not signature."""
    pyi_sigs = {"Cls.__init__": FuncSig(params=["self", "model"], defaults=set())}
    rt_sigs = {"Cls.__init__": FuncSig(params=["self", "*args", "**kwargs"], defaults=set())}
    diffs = compare_signatures(pyi_sigs, rt_sigs)
    # Existence matches → no diff despite different params
    assert diffs == []


def test_compare_synthetic_init_not_in_pyi():
    """Runtime __init__ with synthetic *args/**kwargs can be absent from .pyi."""
    pyi_sigs = {}  # no __init__ in .pyi
    rt_sigs = {"Cls.__init__": FuncSig(params=["self", "*args", "**kwargs"], defaults=set())}
    diffs = compare_signatures(pyi_sigs, rt_sigs)
    assert diffs == []