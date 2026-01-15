"""Additional tests for handlers.py to improve coverage."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from local_deepwiki.handlers import (
    handle_ask_question,
    handle_deep_research,
    handle_index_repository,
    handle_read_wiki_page,
    handle_read_wiki_structure,
    handle_search_code,
    handle_tool_errors,
)


class TestHandleToolErrorsDecorator:
    """Tests for the handle_tool_errors decorator."""

    async def test_returns_result_on_success(self):
        """Test decorator returns result when handler succeeds."""

        @handle_tool_errors
        async def successful_handler(args):
            return [TextContent(type="text", text="success")]

        result = await successful_handler({})
        assert len(result) == 1
        assert result[0].text == "success"

    async def test_catches_value_error(self):
        """Test decorator catches ValueError and returns error message."""

        @handle_tool_errors
        async def failing_handler(args):
            raise ValueError("Invalid input")

        result = await failing_handler({})
        assert len(result) == 1
        assert "Error: Invalid input" in result[0].text

    async def test_catches_generic_exception(self):
        """Test decorator catches generic exceptions and returns error message."""

        @handle_tool_errors
        async def failing_handler(args):
            raise RuntimeError("Something went wrong")

        result = await failing_handler({})
        assert len(result) == 1
        assert "Error: Something went wrong" in result[0].text

    async def test_propagates_cancelled_error(self):
        """Test decorator re-raises CancelledError."""

        @handle_tool_errors
        async def cancelled_handler(args):
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await cancelled_handler({})


class TestHandleDeepResearch:
    """Tests for handle_deep_research handler."""

    async def test_returns_error_for_empty_question(self):
        """Test error returned for empty question."""
        result = await handle_deep_research({
            "repo_path": "/some/path",
            "question": "",
        })

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "cannot be empty" in result[0].text

    async def test_returns_error_for_unindexed_repo(self, tmp_path):
        """Test error returned when repository is not indexed."""
        result = await handle_deep_research({
            "repo_path": str(tmp_path),
            "question": "What is the architecture?",
        })

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not indexed" in result[0].text

    async def test_clamps_max_chunks_to_valid_range(self, tmp_path):
        """Test that max_chunks is clamped to valid range."""
        result = await handle_deep_research({
            "repo_path": str(tmp_path),
            "question": "Test question",
            "max_chunks": 10000,  # Above max, should be clamped
        })

        # Will fail due to no index, but shouldn't fail due to max_chunks
        assert "Error" in result[0].text
        assert "not indexed" in result[0].text

    async def test_handles_cancelled_error(self, tmp_path):
        """Test that CancelledError is propagated."""

        async def mock_research(*args, **kwargs):
            raise asyncio.CancelledError()

        with patch(
            "local_deepwiki.handlers._handle_deep_research_impl",
            side_effect=asyncio.CancelledError(),
        ):
            with pytest.raises(asyncio.CancelledError):
                await handle_deep_research({
                    "repo_path": str(tmp_path),
                    "question": "Test question",
                })


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
        import os
        import stat

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

        result = await handle_read_wiki_page({
            "wiki_path": str(tmp_path),
            "page": "a/b/c/deep.md",
        })

        assert len(result) == 1
        assert result[0].text == page_content


class TestHandleSearchCodeExtended:
    """Extended tests for handle_search_code handler."""

    async def test_returns_error_for_whitespace_query(self):
        """Test error returned for whitespace-only query."""
        result = await handle_search_code({
            "repo_path": "/some/path",
            "query": "   \t\n  ",
        })

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "cannot be empty" in result[0].text


class TestHandleIndexRepositoryExtended:
    """Extended tests for handle_index_repository handler."""

    async def test_accepts_valid_languages_list(self, tmp_path):
        """Test accepts valid languages list."""
        # Create a minimal Python file
        (tmp_path / "test.py").write_text("print('hello')")

        # This will still fail because no actual indexing infrastructure,
        # but it tests the validation path
        with patch("local_deepwiki.handlers.RepositoryIndexer") as mock_indexer:
            mock_instance = MagicMock()
            mock_instance.index = AsyncMock(return_value=MagicMock(
                total_files=1,
                total_chunks=1,
                languages=["python"],
            ))
            mock_instance.wiki_path = tmp_path / ".deepwiki"
            mock_instance.vector_store = MagicMock()
            mock_indexer.return_value = mock_instance

            with patch("local_deepwiki.handlers.generate_wiki") as mock_wiki:
                mock_wiki.return_value = MagicMock(pages=[])

                result = await handle_index_repository({
                    "repo_path": str(tmp_path),
                    "languages": ["python", "typescript"],
                })

                # Should succeed
                assert len(result) == 1
                data = json.loads(result[0].text)
                assert data["status"] == "success"

    async def test_handles_use_cloud_for_github_flag(self, tmp_path):
        """Test handles use_cloud_for_github flag."""
        (tmp_path / "test.py").write_text("print('hello')")

        with patch("local_deepwiki.handlers.RepositoryIndexer") as mock_indexer:
            mock_instance = MagicMock()
            mock_instance.index = AsyncMock(return_value=MagicMock(
                total_files=1,
                total_chunks=1,
                languages=["python"],
            ))
            mock_instance.wiki_path = tmp_path / ".deepwiki"
            mock_instance.vector_store = MagicMock()
            mock_indexer.return_value = mock_instance

            with patch("local_deepwiki.handlers.generate_wiki") as mock_wiki:
                mock_wiki.return_value = MagicMock(pages=[])

                result = await handle_index_repository({
                    "repo_path": str(tmp_path),
                    "use_cloud_for_github": True,
                })

                assert len(result) == 1
                data = json.loads(result[0].text)
                assert data["status"] == "success"


class TestHandleAskQuestionExtended:
    """Extended tests for handle_ask_question handler."""

    async def test_returns_no_results_message(self, tmp_path):
        """Test returns appropriate message when no results found."""
        # Create mock vector store that returns empty results
        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.get_vector_db_path.return_value = tmp_path / ".deepwiki" / "vectors"
            config.embedding = MagicMock()
            mock_config.return_value = config

            # Create the vector db path so the check passes
            vector_path = tmp_path / ".deepwiki" / "vectors"
            vector_path.mkdir(parents=True)

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore") as mock_vs:
                    mock_store = MagicMock()
                    mock_store.search = AsyncMock(return_value=[])
                    mock_vs.return_value = mock_store

                    result = await handle_ask_question({
                        "repo_path": str(tmp_path),
                        "question": "What is this code?",
                    })

                    assert len(result) == 1
                    assert "No relevant code found" in result[0].text

    async def test_returns_answer_with_sources(self, tmp_path):
        """Test returns answer with sources when results are found."""
        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.get_vector_db_path.return_value = tmp_path / ".deepwiki" / "vectors"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            mock_config.return_value = config

            vector_path = tmp_path / ".deepwiki" / "vectors"
            vector_path.mkdir(parents=True)

            # Create mock search result
            mock_chunk = MagicMock()
            mock_chunk.file_path = "test.py"
            mock_chunk.start_line = 1
            mock_chunk.end_line = 10
            mock_chunk.chunk_type.value = "function"
            mock_chunk.content = "def hello(): pass"

            mock_result = MagicMock()
            mock_result.chunk = mock_chunk
            mock_result.score = 0.9

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore") as mock_vs:
                    mock_store = MagicMock()
                    mock_store.search = AsyncMock(return_value=[mock_result])
                    mock_vs.return_value = mock_store

                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider") as mock_llm:
                        mock_provider = MagicMock()
                        mock_provider.generate = AsyncMock(return_value="This is a test function.")
                        mock_llm.return_value = mock_provider

                        result = await handle_ask_question({
                            "repo_path": str(tmp_path),
                            "question": "What does hello do?",
                        })

                        assert len(result) == 1
                        data = json.loads(result[0].text)
                        assert "answer" in data
                        assert "sources" in data
                        assert data["answer"] == "This is a test function."
                        assert len(data["sources"]) == 1
                        assert data["sources"][0]["file"] == "test.py"


class TestHandleReadWikiStructureToc:
    """Tests for handle_read_wiki_structure with toc.json."""

    async def test_returns_valid_toc_json(self, tmp_path):
        """Test returns toc.json content when it exists and is valid."""
        toc_data = {
            "title": "Project Wiki",
            "entries": [
                {"number": "1", "title": "Overview", "path": "index.md"},
                {"number": "2", "title": "Architecture", "path": "architecture.md"},
            ]
        }
        (tmp_path / "toc.json").write_text(json.dumps(toc_data))

        result = await handle_read_wiki_structure({"wiki_path": str(tmp_path)})

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["title"] == "Project Wiki"
        assert len(data["entries"]) == 2

    async def test_handles_toc_read_error(self, tmp_path):
        """Test falls back to dynamic structure when toc.json can't be read."""
        import os

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

        result = await handle_read_wiki_page({
            "wiki_path": str(tmp_path),
            "page": "unicode.md",
        })

        assert len(result) == 1
        assert result[0].text == content


class TestHandleSearchCodeWithResults:
    """Tests for handle_search_code with mocked results."""

    async def test_returns_formatted_results(self, tmp_path):
        """Test returns properly formatted search results."""
        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = tmp_path / ".deepwiki" / "vectors"
            config.embedding = MagicMock()
            mock_config.return_value = config

            # Create the vector db path
            vector_path = tmp_path / ".deepwiki" / "vectors"
            vector_path.mkdir(parents=True)

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore") as mock_vs:
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

                    mock_store = MagicMock()
                    mock_store.search = AsyncMock(return_value=[mock_result])
                    mock_vs.return_value = mock_store

                    result = await handle_search_code({
                        "repo_path": str(tmp_path),
                        "query": "test function",
                    })

                    assert len(result) == 1
                    data = json.loads(result[0].text)
                    assert len(data) == 1
                    assert data[0]["file_path"] == "test.py"
                    assert data[0]["name"] == "test_function"
                    assert data[0]["score"] == 0.95

    async def test_returns_no_results_message(self, tmp_path):
        """Test returns no results message when search is empty."""
        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = tmp_path / ".deepwiki" / "vectors"
            config.embedding = MagicMock()
            mock_config.return_value = config

            vector_path = tmp_path / ".deepwiki" / "vectors"
            vector_path.mkdir(parents=True)

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore") as mock_vs:
                    mock_store = MagicMock()
                    mock_store.search = AsyncMock(return_value=[])
                    mock_vs.return_value = mock_store

                    result = await handle_search_code({
                        "repo_path": str(tmp_path),
                        "query": "nonexistent",
                    })

                    assert len(result) == 1
                    assert "No results found" in result[0].text

    async def test_truncates_long_content_preview(self, tmp_path):
        """Test truncates long content in preview."""
        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = tmp_path / ".deepwiki" / "vectors"
            config.embedding = MagicMock()
            mock_config.return_value = config

            vector_path = tmp_path / ".deepwiki" / "vectors"
            vector_path.mkdir(parents=True)

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

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore") as mock_vs:
                    mock_store = MagicMock()
                    mock_store.search = AsyncMock(return_value=[mock_result])
                    mock_vs.return_value = mock_store

                    result = await handle_search_code({
                        "repo_path": str(tmp_path),
                        "query": "long function",
                    })

                    assert len(result) == 1
                    data = json.loads(result[0].text)
                    # Preview should be truncated with "..."
                    assert data[0]["preview"].endswith("...")
                    assert len(data[0]["preview"]) <= 303  # 300 + "..."
