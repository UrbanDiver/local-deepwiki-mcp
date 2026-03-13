"""Regression guards for wiki output quality bugs."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from conftest import make_code_chunk, make_file_info, make_index_status
from local_deepwiki.models import ChunkType
from wiki_output_helpers import (
    BAD_PATTERNS,
    _strip_code_blocks,
    scan_page_for_quality_issues,
)


class TestMockLeakageGuard:
    """Prevent MagicMock objects from appearing in wiki output."""

    def test_scan_detects_magicmock(self):
        content = "## Directory Structure\n<MagicMock name='mock.path' id='123'>\n"
        issues = scan_page_for_quality_issues(content, "index.md")
        assert any("MagicMock" in i for i in issues)

    def test_scan_allows_mock_in_code_blocks(self):
        content = "## Testing\n\n```python\nmock = MagicMock()\n```\n"
        issues = scan_page_for_quality_issues(content, "test.md")
        assert not any("MagicMock" in i for i in issues)

    def test_scan_detects_python_object_repr(self):
        content = "<SomeClass object at 0x7f id='456'>\n"
        issues = scan_page_for_quality_issues(content, "index.md")
        assert len(issues) > 0

    def test_scan_passes_clean_content(self):
        content = (
            "# Overview\n\n## Description\n\nThis is a clean page.\n\n"
            "## Features\n\n- Feature 1\n"
        )
        issues = scan_page_for_quality_issues(content, "index.md")
        assert issues == []

    def test_scan_detects_none_heading(self):
        content = "## None\n\nSome content\n"
        issues = scan_page_for_quality_issues(content, "page.md")
        assert any("None" in i for i in issues)

    def test_scan_detects_empty_section(self):
        content = "## Section 1\n## Section 2\n\nContent\n"
        issues = scan_page_for_quality_issues(content, "page.md")
        assert any("Empty section" in i for i in issues)

    def test_scan_detects_mock_object_reference(self):
        content = "The module uses <Mock name='mock.connect' id='789'>.\n"
        issues = scan_page_for_quality_issues(content, "page.md")
        assert any("Mock object reference" in i for i in issues)

    def test_scan_detects_asyncmock_reference(self):
        content = "Result: <AsyncMock name='mock.fetch' id='321'>\n"
        issues = scan_page_for_quality_issues(content, "page.md")
        assert any("AsyncMock" in i for i in issues)

    def test_scan_detects_none_list_item(self):
        content = "## Items\n\n- Valid item\n- None\n"
        issues = scan_page_for_quality_issues(content, "page.md")
        assert any("None as list item" in i for i in issues)


class TestStripCodeBlocks:
    """Verify that code block stripping works for quality scanning."""

    def test_strips_fenced_python_block(self):
        content = "Before\n```python\ncode here\n```\nAfter"
        result = _strip_code_blocks(content)
        assert "code here" not in result
        assert "Before" in result
        assert "After" in result

    def test_strips_mermaid_block(self):
        content = "Text\n```mermaid\ngraph TD;\n```\nMore text"
        result = _strip_code_blocks(content)
        assert "graph TD" not in result

    def test_preserves_content_outside_blocks(self):
        content = "# Title\n\nParagraph text.\n"
        result = _strip_code_blocks(content)
        assert result == content


class TestBadPatterns:
    """Ensure BAD_PATTERNS cover the expected set of quality issues."""

    def test_pattern_count(self):
        assert len(BAD_PATTERNS) >= 7

    @pytest.mark.parametrize(
        "text,should_match",
        [
            ("<MagicMock name='x' id='1'>", True),
            ("<Mock id='1'>", True),
            ("<AsyncMock id='1'>", True),
            ("MagicMock()", False),  # constructor call, not repr
            ("## None", True),
            ("- None", True),
            ("- None of the above", False),  # only exact "- None"
        ],
    )
    def test_individual_patterns(self, text: str, should_match: bool):
        matched = any(pat.search(text) for pat, _ in BAD_PATTERNS)
        assert matched == should_match, f"Pattern match mismatch for: {text!r}"


class TestTestDirectoryFiltering:
    """Ensure test directories are excluded from module generation."""

    async def test_modules_exclude_test_directories(self):
        from local_deepwiki.generators.wiki.modules import generate_module_docs

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="## Module docs")

        src_chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vs = MagicMock()
        mock_vs.get_chunks_by_file = AsyncMock(return_value=[src_chunk])
        mock_vs.search = AsyncMock(return_value=[])

        mock_sm = MagicMock()
        mock_sm.needs_regeneration = MagicMock(return_value=True)
        mock_sm.needs_regeneration_structural = MagicMock(return_value=True)
        mock_sm.load_existing_page = AsyncMock(return_value=None)
        mock_sm.record_page_status = MagicMock()
        mock_sm.record_summary_page_status = MagicMock()

        index_status = make_index_status(
            repo_path="/tmp/repo",
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
                make_file_info(path="tests/test_main.py"),
                make_file_info(path="tests/test_utils.py"),
                make_file_info(path="test/unit_test.py"),
                make_file_info(path="test/integration_test.py"),
            ],
        )

        pages, _, _ = await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vs,
            llm=mock_llm,
            system_prompt="prompt",
            status_manager=mock_sm,
            full_rebuild=True,
        )

        page_paths = [p.path for p in pages]
        assert "modules/tests.md" not in page_paths
        assert "modules/test.md" not in page_paths
        # src module should exist
        assert "modules/src.md" in page_paths


class TestGlossaryTestFiltering:
    """Ensure test entities are excluded from the glossary."""

    async def test_glossary_excludes_test_file_entities(self):
        from local_deepwiki.generators.analysis.glossary import collect_all_entities

        src_chunk = make_code_chunk(
            file_path="src/models.py",
            name="User",
            chunk_type=ChunkType.CLASS,
        )
        test_chunk = make_code_chunk(
            file_path="tests/test_models.py",
            name="TestUser",
            chunk_type=ChunkType.CLASS,
        )

        mock_vs = MagicMock()

        # get_all_chunks is called once per entity type (class, function, method)
        # Return our chunks only for the "class" call
        def _get_all_chunks(chunk_type: str | None = None, **kwargs):
            if chunk_type == "class":
                return iter([src_chunk, test_chunk])
            return iter([])

        mock_vs.get_all_chunks = MagicMock(side_effect=_get_all_chunks)

        index_status = make_index_status(repo_path="/tmp/repo", files=[])
        entities = await collect_all_entities(index_status, mock_vs)

        entity_names = [e.name for e in entities]
        assert "User" in entity_names
        assert "TestUser" not in entity_names


class TestCoverageTestFiltering:
    """Ensure test files are excluded from coverage reports."""

    async def test_coverage_excludes_test_files(self):
        from local_deepwiki.generators.analysis.coverage import analyze_project_coverage

        mock_vs = MagicMock()
        mock_vs.get_chunks_by_file = AsyncMock(return_value=[])

        index_status = make_index_status(
            repo_path="/tmp/repo",
            files=[
                make_file_info(path="src/models.py"),
                make_file_info(path="tests/test_models.py"),
                make_file_info(path="test/test_utils.py"),
            ],
        )

        _, file_coverages = await analyze_project_coverage(index_status, mock_vs)

        covered_paths = [fc.file_path for fc in file_coverages]
        assert "src/models.py" in covered_paths
        assert "tests/test_models.py" not in covered_paths
        assert "test/test_utils.py" not in covered_paths


class TestInheritanceTestFiltering:
    """Ensure test classes are excluded from inheritance trees."""

    async def test_inheritance_excludes_test_classes(self):
        from local_deepwiki.generators.analysis.inheritance import (
            collect_class_hierarchy,
        )

        src_chunk = make_code_chunk(
            file_path="src/base.py",
            name="BaseService",
            chunk_type=ChunkType.CLASS,
            content="class BaseService:\n    pass",
        )
        src_chunk2 = make_code_chunk(
            file_path="src/auth.py",
            name="AuthService",
            chunk_type=ChunkType.CLASS,
            content="class AuthService(BaseService):\n    pass",
        )
        test_chunk = make_code_chunk(
            file_path="tests/test_service.py",
            name="MockService",
            chunk_type=ChunkType.CLASS,
            content="class MockService(BaseService):\n    pass",
        )

        mock_vs = MagicMock()
        mock_vs.get_all_chunks = MagicMock(
            return_value=iter([src_chunk, src_chunk2, test_chunk])
        )

        index_status = make_index_status(repo_path="/tmp/repo", files=[])
        classes = await collect_class_hierarchy(index_status, mock_vs)

        assert "BaseService" in classes
        assert "AuthService" in classes
        assert "MockService" not in classes
