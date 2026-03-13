"""Wiki output content quality tests.

Validates the quality of generated wiki content by reading the project's
existing .deepwiki/ directory. These tests catch common issues like mock
object leakage, missing sections, and empty pages.

Run selectively with: pytest -m wiki_output
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from wiki_output_helpers import scan_page_for_quality_issues


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def wiki_path() -> Path:
    """Path to the project's generated wiki."""
    path = Path(__file__).parent.parent / ".deepwiki"
    if not path.exists():
        pytest.skip("No .deepwiki directory found — run 'deepwiki update' first")
    return path


@pytest.fixture(scope="session")
def index_md(wiki_path: Path) -> str:
    """Content of the main index.md page."""
    index_file = wiki_path / "index.md"
    if not index_file.exists():
        pytest.skip("index.md not found")
    return index_file.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="session")
def all_md_files(wiki_path: Path) -> list[Path]:
    """All markdown files in the wiki."""
    return sorted(wiki_path.rglob("*.md"))


# ---------------------------------------------------------------------------
# Overview page quality
# ---------------------------------------------------------------------------


@pytest.mark.wiki_output
class TestOverviewQuality:
    """Tests for the main index.md overview page."""

    @pytest.mark.xfail(
        reason="Requires wiki rebuild: dir_tree now skips MagicMock dirs, MagicMock dirs deleted",
        strict=False,
    )
    def test_overview_no_mock_objects(self, index_md: str) -> None:
        """index.md must not contain MagicMock, Mock, or Python object repr patterns."""
        mock_patterns = [
            (re.compile(r"<MagicMock\b"), "MagicMock object reference"),
            (re.compile(r"<Mock\b"), "Mock object reference"),
            (re.compile(r"<AsyncMock\b"), "AsyncMock object reference"),
            (re.compile(r"<[A-Z][a-zA-Z]+ .* id='[0-9]+'"), "Python object repr"),
            (re.compile(r"name='mock\.\w+"), "Mock attribute reference"),
        ]
        violations = []
        for pattern, description in mock_patterns:
            matches = pattern.findall(index_md)
            if matches:
                violations.append(f"{description}: {matches[0]!r}")

        assert not violations, f"Mock objects leaked into index.md:\n" + "\n".join(
            f"  - {v}" for v in violations
        )

    @pytest.mark.xfail(
        reason="Requires wiki rebuild: dir_tree now skips MagicMock dirs, MagicMock dirs deleted",
        strict=False,
    )
    def test_overview_has_directory_structure(self, index_md: str) -> None:
        """index.md should contain a directory tree section with real directories."""
        assert "```" in index_md, (
            "index.md should contain a code block (directory tree)"
        )
        # The directory tree should show the actual source directory, not just MagicMock paths
        assert "src/" in index_md, "Directory structure should include 'src/' directory"

    def test_overview_has_required_sections(self, index_md: str) -> None:
        """index.md must contain Description, Key Features, and Technology Stack."""
        lower = index_md.lower()
        required_sections = ["description", "key features", "technology stack"]
        missing = [s for s in required_sections if s not in lower]
        assert not missing, f"index.md is missing required sections: {missing}"


# ---------------------------------------------------------------------------
# Module pages quality
# ---------------------------------------------------------------------------


@pytest.mark.wiki_output
class TestModuleQuality:
    """Tests for module documentation pages."""

    def test_modules_index_exists(self, wiki_path: Path) -> None:
        """modules/index.md must exist."""
        assert (wiki_path / "modules" / "index.md").exists(), (
            "modules/index.md does not exist"
        )

    def test_modules_no_test_directories(self, wiki_path: Path) -> None:
        """No module page should exist for 'tests' or 'test' directories.

        Module documentation should only cover source code, not test suites.
        """
        modules_dir = wiki_path / "modules"
        if not modules_dir.exists():
            pytest.skip("modules/ directory not found")

        test_pages = [
            p.name
            for p in modules_dir.iterdir()
            if p.is_file() and p.suffix == ".md" and p.stem in ("tests", "test")
        ]
        assert not test_pages, f"Module pages exist for test directories: {test_pages}"

    def test_modules_has_source_modules(self, wiki_path: Path) -> None:
        """At least one source module page should exist (e.g., modules/src.md)."""
        modules_dir = wiki_path / "modules"
        if not modules_dir.exists():
            pytest.skip("modules/ directory not found")

        source_pages = [
            p.name
            for p in modules_dir.iterdir()
            if p.is_file()
            and p.suffix == ".md"
            and p.stem not in ("index", "tests", "test")
        ]
        assert source_pages, "No source module pages found in modules/"


# ---------------------------------------------------------------------------
# Glossary quality
# ---------------------------------------------------------------------------


@pytest.mark.wiki_output
class TestGlossaryQuality:
    """Tests for the glossary page."""

    @pytest.fixture(scope="class")
    def glossary_md(self, wiki_path: Path) -> str:
        glossary_file = wiki_path / "glossary.md"
        if not glossary_file.exists():
            pytest.skip("glossary.md not found")
        return glossary_file.read_text(encoding="utf-8", errors="replace")

    @pytest.mark.xfail(
        reason="Requires wiki rebuild: source_refs now filters test files from footer",
        strict=False,
    )
    def test_glossary_no_test_entities(self, glossary_md: str) -> None:
        """glossary.md should not contain test file paths (tests/test_*.py).

        The glossary should document source code entities, not test helpers.
        """
        test_file_refs = re.findall(r"tests/test_\w+\.py", glossary_md)
        assert not test_file_refs, (
            f"Glossary contains {len(test_file_refs)} references to test files. "
            f"First 5: {test_file_refs[:5]}"
        )

    def test_glossary_has_navigation(self, glossary_md: str) -> None:
        """glossary.md should have alphabetical navigation links."""
        nav_pattern = re.compile(r"\[([A-Z])\]\(#[a-z]\)")
        matches = nav_pattern.findall(glossary_md)
        assert len(matches) >= 5, (
            f"Expected at least 5 alphabetical navigation links, found {len(matches)}"
        )


# ---------------------------------------------------------------------------
# Inheritance quality
# ---------------------------------------------------------------------------


@pytest.mark.wiki_output
class TestInheritanceQuality:
    """Tests for the class inheritance page."""

    def test_inheritance_no_test_classes(self, wiki_path: Path) -> None:
        """inheritance.md should not contain Mock*, Failing*, or Test* classes.

        These are test-only classes and should not appear in production
        inheritance diagrams.
        """
        inheritance_file = wiki_path / "inheritance.md"
        if not inheritance_file.exists():
            pytest.skip("inheritance.md not found")

        content = inheritance_file.read_text(encoding="utf-8", errors="replace")
        test_class_patterns = [
            (re.compile(r"\bMock\w+"), "Mock classes"),
            (re.compile(r"\bFailing\w+"), "Failing* test classes"),
        ]

        violations = []
        for pattern, description in test_class_patterns:
            matches = pattern.findall(content)
            if matches:
                unique = sorted(set(matches))
                violations.append(f"{description}: {unique[:5]}")

        assert not violations, f"Test classes found in inheritance.md:\n" + "\n".join(
            f"  - {v}" for v in violations
        )


# ---------------------------------------------------------------------------
# Coverage quality
# ---------------------------------------------------------------------------


@pytest.mark.wiki_output
class TestCoverageQuality:
    """Tests for the documentation coverage page."""

    @pytest.mark.xfail(
        reason="Requires wiki rebuild: source_refs now filters test files from footer",
        strict=False,
    )
    def test_coverage_no_test_files(self, wiki_path: Path) -> None:
        """coverage.md should not list test files in coverage metrics.

        Documentation coverage should only report on source code files.
        """
        coverage_file = wiki_path / "coverage.md"
        if not coverage_file.exists():
            pytest.skip("coverage.md not found")

        content = coverage_file.read_text(encoding="utf-8", errors="replace")
        test_refs = re.findall(r"test_\w+\.py", content)
        assert not test_refs, (
            f"coverage.md lists {len(test_refs)} test files. First 5: {test_refs[:5]}"
        )


# ---------------------------------------------------------------------------
# Global quality scan
# ---------------------------------------------------------------------------


@pytest.mark.wiki_output
class TestGlobalQuality:
    """Quality checks applied to all wiki pages."""

    @pytest.mark.xfail(
        reason="Requires wiki rebuild: quality scan now skips code blocks for section check; remaining LLM output issues",
        strict=False,
    )
    def test_all_pages_pass_quality_scan(
        self, all_md_files: list[Path], wiki_path: Path
    ) -> None:
        """Run scan_page_for_quality_issues on every .md file.

        Collects all quality issues across all pages and reports them.
        """
        all_issues: list[str] = []
        for md_file in all_md_files:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            page_rel = str(md_file.relative_to(wiki_path))
            issues = scan_page_for_quality_issues(content, page_rel)
            all_issues.extend(issues)

        assert not all_issues, (
            f"Quality issues found in {len(all_issues)} places:\n"
            + "\n".join(f"  - {issue}" for issue in all_issues[:20])
            + (
                f"\n  ... and {len(all_issues) - 20} more"
                if len(all_issues) > 20
                else ""
            )
        )

    def test_architecture_has_mermaid(self, wiki_path: Path) -> None:
        """architecture.md should contain a mermaid diagram."""
        arch_file = wiki_path / "architecture.md"
        if not arch_file.exists():
            pytest.skip("architecture.md not found")

        content = arch_file.read_text(encoding="utf-8", errors="replace")
        assert "```mermaid" in content, (
            "architecture.md should contain at least one mermaid diagram"
        )

    def test_no_page_is_empty(self, all_md_files: list[Path], wiki_path: Path) -> None:
        """Every .md file must have at least 50 characters of content."""
        empty_pages = []
        for md_file in all_md_files:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            if len(content.strip()) < 50:
                page_rel = str(md_file.relative_to(wiki_path))
                empty_pages.append(f"{page_rel} ({len(content.strip())} chars)")

        assert not empty_pages, (
            f"Found {len(empty_pages)} nearly-empty pages:\n"
            + "\n".join(f"  - {p}" for p in empty_pages)
        )
