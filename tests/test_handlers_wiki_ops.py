"""Tests for handler wiki operations - read wiki structure, read wiki page, search code."""

import json
import os
import stat
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from local_deepwiki.handlers import (
    handle_read_wiki_page,
    handle_read_wiki_structure,
    handle_search_code,
)


class TestHandleReadWikiStructureExtended:
    """Extended tests for handle_read_wiki_structure handler."""

    async def test_handles_invalid_toc_json(self, tmp_path):
        """Test falls back to dynamic structure when toc.json is invalid."""
        # Create invalid JSON
        (tmp_path / "toc.json").write_text("not valid json")
        (tmp_path / "index.md").write_text("# Home")

        result = await handle_read_wiki_structure({"wiki_path": str(tmp_path)})

        assert len(result) == 1
        data = json.loads(result[0].text)
        # Should have fallen back to dynamic structure
        assert "pages" in data or "sections" in data

    async def test_handles_unreadable_markdown_file(self, tmp_path):
        """Test handles errors when reading markdown file titles."""
        # Create a markdown file
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test")

        # Make it unreadable (on Unix systems)
        if os.name != "nt":  # Skip on Windows
            original_mode = md_file.stat().st_mode
            try:
                md_file.chmod(0o000)
                result = await handle_read_wiki_structure({"wiki_path": str(tmp_path)})
                # Should still return a structure, using filename as title
                assert len(result) == 1
            finally:
                md_file.chmod(original_mode)

    async def test_builds_nested_section_structure(self, tmp_path):
        """Test builds correct structure for nested directories."""
        # Create nested structure
        (tmp_path / "index.md").write_text("# Home")

        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "core.md").write_text("# Core")
        (modules_dir / "utils.md").write_text("# Utils")

        files_dir = tmp_path / "files"
        files_dir.mkdir()
        (files_dir / "main.md").write_text("# Main")

        result = await handle_read_wiki_structure({"wiki_path": str(tmp_path)})

        assert len(result) == 1
        data = json.loads(result[0].text)

        # Check sections were created
        assert "sections" in data
        assert "modules" in data["sections"]
        assert "files" in data["sections"]


class TestHandleReadWikiPageExtended:
    """Extended tests for handle_read_wiki_page handler."""

    async def test_handles_deeply_nested_page(self, tmp_path):
        """Test reading a deeply nested page."""
        deep_dir = tmp_path / "a" / "b" / "c"
        deep_dir.mkdir(parents=True)
        page_content = "# Deep Page"
        (deep_dir / "deep.md").write_text(page_content)

        result = await handle_read_wiki_page(
            {
                "wiki_path": str(tmp_path),
                "page": "a/b/c/deep.md",
            }
        )

        assert len(result) == 1
        assert result[0].text == page_content


class TestHandleSearchCodeExtended:
    """Extended tests for handle_search_code handler."""

    async def test_returns_error_for_whitespace_query(self, tmp_path):
        """Test error returned for whitespace-only query (repo not indexed)."""
        result = await handle_search_code(
            {
                "repo_path": str(tmp_path),
                "query": "   \t\n  ",
            }
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        # Whitespace passes min_length but fails at repo check
        assert "not indexed" in result[0].text


class TestHandleReadWikiStructureToc:
    """Tests for handle_read_wiki_structure with toc.json."""

    async def test_returns_valid_toc_json(self, tmp_path):
        """Test returns toc.json content when it exists and is valid."""
        toc_data = {
            "title": "Project Wiki",
            "entries": [
                {"number": "1", "title": "Overview", "path": "index.md"},
                {"number": "2", "title": "Architecture", "path": "architecture.md"},
            ],
        }
        (tmp_path / "toc.json").write_text(json.dumps(toc_data))

        result = await handle_read_wiki_structure({"wiki_path": str(tmp_path)})

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["title"] == "Project Wiki"
        assert len(data["entries"]) == 2

    async def test_handles_toc_read_error(self, tmp_path):
        """Test falls back to dynamic structure when toc.json can't be read."""
        toc_path = tmp_path / "toc.json"
        toc_path.write_text('{"title": "Test"}')
        (tmp_path / "index.md").write_text("# Home")

        if os.name != "nt":  # Skip on Windows
            original_mode = toc_path.stat().st_mode
            try:
                toc_path.chmod(0o000)
                result = await handle_read_wiki_structure({"wiki_path": str(tmp_path)})
                # Should fall back to dynamic structure
                assert len(result) == 1
                data = json.loads(result[0].text)
                assert "pages" in data or "sections" in data
            finally:
                toc_path.chmod(original_mode)


class TestHandleReadWikiPageContent:
    """Tests for handle_read_wiki_page content handling."""

    async def test_reads_unicode_content(self, tmp_path):
        """Test reads unicode content correctly."""
        content = "# 你好世界\n\nこんにちは 🎉"
        (tmp_path / "unicode.md").write_text(content, encoding="utf-8")

        result = await handle_read_wiki_page(
            {
                "wiki_path": str(tmp_path),
                "page": "unicode.md",
            }
        )

        assert len(result) == 1
        assert result[0].text == content


class TestHandleSearchCodeWithResults:
    """Tests for handle_search_code with mocked results."""

    async def test_returns_formatted_results(self, tmp_path):
        """Test returns properly formatted search results."""
        config = MagicMock()
        config.embedding = MagicMock()

        with patch(
            "local_deepwiki.handlers.core._load_index_status",
            return_value=(MagicMock(), tmp_path / ".deepwiki", config),
        ):
            # Create mock search result
            mock_chunk = MagicMock()
            mock_chunk.file_path = "test.py"
            mock_chunk.name = "test_function"
            mock_chunk.chunk_type.value = "function"
            mock_chunk.language.value = "python"
            mock_chunk.start_line = 1
            mock_chunk.end_line = 10
            mock_chunk.content = "def test(): pass"
            mock_chunk.docstring = "A test function"

            mock_result = MagicMock()
            mock_result.chunk = mock_chunk
            mock_result.score = 0.95
            mock_result.highlights = []

            mock_store = MagicMock()
            mock_store.search = AsyncMock(return_value=[mock_result])

            with patch(
                "local_deepwiki.handlers.core._create_vector_store",
                return_value=mock_store,
            ):
                result = await handle_search_code(
                    {
                        "repo_path": str(tmp_path),
                        "query": "test function",
                    }
                )

                assert len(result) == 1
                data = json.loads(result[0].text)
                assert len(data) == 1
                assert data[0]["file_path"] == "test.py"
                assert data[0]["name"] == "test_function"
                assert data[0]["score"] == 0.95

    async def test_returns_no_results_message(self, tmp_path):
        """Test returns no results message when search is empty."""
        config = MagicMock()
        config.embedding = MagicMock()

        with patch(
            "local_deepwiki.handlers.core._load_index_status",
            return_value=(MagicMock(), tmp_path / ".deepwiki", config),
        ):
            mock_store = MagicMock()
            mock_store.search = AsyncMock(return_value=[])

            with patch(
                "local_deepwiki.handlers.core._create_vector_store",
                return_value=mock_store,
            ):
                result = await handle_search_code(
                    {
                        "repo_path": str(tmp_path),
                        "query": "nonexistent",
                    }
                )

                assert len(result) == 1
                assert "No results found" in result[0].text

    async def test_truncates_long_content_preview(self, tmp_path):
        """Test truncates long content in preview."""
        config = MagicMock()
        config.embedding = MagicMock()

        with patch(
            "local_deepwiki.handlers.core._load_index_status",
            return_value=(MagicMock(), tmp_path / ".deepwiki", config),
        ):
            # Create mock with long content
            mock_chunk = MagicMock()
            mock_chunk.file_path = "long.py"
            mock_chunk.name = "long_function"
            mock_chunk.chunk_type.value = "function"
            mock_chunk.language.value = "python"
            mock_chunk.start_line = 1
            mock_chunk.end_line = 100
            mock_chunk.content = "x" * 500  # Long content
            mock_chunk.docstring = None

            mock_result = MagicMock()
            mock_result.chunk = mock_chunk
            mock_result.score = 0.8
            mock_result.highlights = []

            mock_store = MagicMock()
            mock_store.search = AsyncMock(return_value=[mock_result])

            with patch(
                "local_deepwiki.handlers.core._create_vector_store",
                return_value=mock_store,
            ):
                result = await handle_search_code(
                    {
                        "repo_path": str(tmp_path),
                        "query": "long function",
                    }
                )

                assert len(result) == 1
                data = json.loads(result[0].text)
                # Preview should be truncated with "..."
                assert data[0]["preview"].endswith("...")
                assert len(data[0]["preview"]) <= 303  # 300 + "..."
