import json
import re
from pathlib import Path


ACADEMY_ROOT = Path(__file__).resolve().parents[1]
SENZA_ROOT = ACADEMY_ROOT.parent
TEXTBOOK_ROOT = SENZA_ROOT / "docs" / "academy" / "textbook"


def _manifest() -> dict:
    return json.loads((ACADEMY_ROOT / "course_manifest.json").read_text(encoding="utf-8"))


def test_manifest_maps_every_lab_to_a_textbook_chapter():
    chapters = [lab["textbook"] for lab in _manifest()["labs"]]
    assert len(chapters) == 10
    assert len(chapters) == len(set(chapters))
    assert all((TEXTBOOK_ROOT / chapter).is_file() for chapter in chapters)


def test_every_chapter_has_the_reader_contract():
    for lab in _manifest()["labs"]:
        path = TEXTBOOK_ROOT / lab["textbook"]
        text = path.read_text(encoding="utf-8")
        assert len(text) >= 4000, f"{path}: chapter is still an outline"
        assert "成熟度" in text, f"{path}: missing evidence maturity"
        assert "能力边界" in text, f"{path}: missing capability boundaries"
        assert "复习题" in text, f"{path}: missing review questions"
        assert lab["directory"] in text, f"{path}: missing its Academy lab link"
        assert text.count("```") % 2 == 0, f"{path}: unclosed fenced code block"
        assert not any(line.rstrip() != line for line in text.splitlines()), (
            f"{path}: trailing whitespace"
        )


def test_local_markdown_links_in_academy_docs_are_repo_self_contained():
    link_pattern = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
    failures = []
    paths = {
        *TEXTBOOK_ROOT.parent.rglob("*.md"),
        *ACADEMY_ROOT.rglob("*.md"),
        SENZA_ROOT / "README.md",
    }
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        for target in link_pattern.findall(text):
            target = target.split("#", 1)[0].strip()
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(SENZA_ROOT.resolve())
            except ValueError:
                failures.append(f"{path.name}: link escapes Senza repository: {target}")
                continue
            if not resolved.exists():
                failures.append(f"{path.name}: {target}")
    assert not failures, "broken or non-contained Academy links:\n" + "\n".join(failures)


def test_academy_sources_do_not_reference_local_sibling_checkouts():
    forbidden = (
        "../../../../repository/",
        "../../../../ai-agent-book/",
        "D:/GKXTwork/",
        "D:\\GKXTwork\\",
        "file://",
    )
    paths = {
        *TEXTBOOK_ROOT.parent.rglob("*.md"),
        *ACADEMY_ROOT.rglob("*.md"),
        *ACADEMY_ROOT.rglob("*.json"),
        SENZA_ROOT / "README.md",
    }
    failures = []
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in text:
                failures.append(f"{path}: contains {marker}")
    assert not failures, "workspace-only Academy references:\n" + "\n".join(failures)


def test_cross_repository_github_links_use_the_pinned_source_commits():
    expected_refs = {
        "oh-my-harness/llm-harness-runtime": "03aed0ce550aa0c95cb26d9667f6440bc3dd3349",
        "bojieli/ai-agent-book": "1d2e04ee733dde245af2eb718cfc92d2d0542b7e",
    }
    url_pattern = re.compile(
        r"https://github\.com/"
        r"(oh-my-harness/llm-harness-runtime|bojieli/ai-agent-book)/blob/"
        r"([^/\s)#]+)"
    )
    paths = {
        *TEXTBOOK_ROOT.parent.rglob("*.md"),
        *ACADEMY_ROOT.rglob("*.md"),
        *ACADEMY_ROOT.rglob("*.json"),
    }
    seen = set()
    failures = []
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        for repository, ref in url_pattern.findall(text):
            seen.add(repository)
            if ref != expected_refs[repository]:
                failures.append(f"{path}: {repository} uses unpinned ref {ref}")
    assert seen == set(expected_refs), f"missing pinned source families: {seen}"
    assert not failures, "unpinned Academy source links:\n" + "\n".join(failures)
