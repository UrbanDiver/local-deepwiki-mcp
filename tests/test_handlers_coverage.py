"""Additional tests for handlers.py to improve coverage."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from local_deepwiki.handlers import (
    _handle_deep_research_impl,
    handle_ask_question,
    handle_deep_research,
    handle_export_wiki_pdf,
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
        result = await handle_deep_research(
            {
                "repo_path": "/some/path",
                "question": "",
            }
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "cannot be empty" in result[0].text

    async def test_returns_error_for_unindexed_repo(self, tmp_path):
        """Test error returned when repository is not indexed."""
        result = await handle_deep_research(
            {
                "repo_path": str(tmp_path),
                "question": "What is the architecture?",
            }
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not indexed" in result[0].text

    async def test_clamps_max_chunks_to_valid_range(self, tmp_path):
        """Test that max_chunks is clamped to valid range."""
        result = await handle_deep_research(
            {
                "repo_path": str(tmp_path),
                "question": "Test question",
                "max_chunks": 10000,  # Above max, should be clamped
            }
        )

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
                await handle_deep_research(
                    {
                        "repo_path": str(tmp_path),
                        "question": "Test question",
                    }
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

    async def test_returns_error_for_whitespace_query(self):
        """Test error returned for whitespace-only query."""
        result = await handle_search_code(
            {
                "repo_path": "/some/path",
                "query": "   \t\n  ",
            }
        )

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
            mock_instance.index = AsyncMock(
                return_value=MagicMock(
                    total_files=1,
                    total_chunks=1,
                    languages=["python"],
                )
            )
            mock_instance.wiki_path = tmp_path / ".deepwiki"
            mock_instance.vector_store = MagicMock()
            mock_indexer.return_value = mock_instance

            with patch("local_deepwiki.handlers.generate_wiki") as mock_wiki:
                mock_wiki.return_value = MagicMock(pages=[])

                result = await handle_index_repository(
                    {
                        "repo_path": str(tmp_path),
                        "languages": ["python", "typescript"],
                    }
                )

                # Should succeed
                assert len(result) == 1
                data = json.loads(result[0].text)
                assert data["status"] == "success"

    async def test_handles_use_cloud_for_github_flag(self, tmp_path):
        """Test handles use_cloud_for_github flag."""
        (tmp_path / "test.py").write_text("print('hello')")

        with patch("local_deepwiki.handlers.RepositoryIndexer") as mock_indexer:
            mock_instance = MagicMock()
            mock_instance.index = AsyncMock(
                return_value=MagicMock(
                    total_files=1,
                    total_chunks=1,
                    languages=["python"],
                )
            )
            mock_instance.wiki_path = tmp_path / ".deepwiki"
            mock_instance.vector_store = MagicMock()
            mock_indexer.return_value = mock_instance

            with patch("local_deepwiki.handlers.generate_wiki") as mock_wiki:
                mock_wiki.return_value = MagicMock(pages=[])

                result = await handle_index_repository(
                    {
                        "repo_path": str(tmp_path),
                        "use_cloud_for_github": True,
                    }
                )

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

                    result = await handle_ask_question(
                        {
                            "repo_path": str(tmp_path),
                            "question": "What is this code?",
                        }
                    )

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

                        result = await handle_ask_question(
                            {
                                "repo_path": str(tmp_path),
                                "question": "What does hello do?",
                            }
                        )

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


class TestHandleIndexRepositoryProgressCallback:
    """Tests for handle_index_repository progress callback."""

    async def test_progress_callback_is_called(self, tmp_path):
        """Test progress callback is invoked during indexing."""
        (tmp_path / "test.py").write_text("print('hello')")

        captured_messages = []

        with patch("local_deepwiki.handlers.RepositoryIndexer") as mock_indexer:
            mock_instance = MagicMock()

            async def mock_index(full_rebuild=False, progress_callback=None):
                # Call the progress callback to test line 119
                if progress_callback:
                    progress_callback("Indexing files", 1, 10)
                    progress_callback("Creating embeddings", 5, 10)
                return MagicMock(
                    total_files=1,
                    total_chunks=1,
                    languages={"python": 1},
                )

            mock_instance.index = mock_index
            mock_instance.wiki_path = tmp_path / ".deepwiki"
            mock_instance.vector_store = MagicMock()
            mock_indexer.return_value = mock_instance

            with patch("local_deepwiki.handlers.generate_wiki") as mock_wiki:
                mock_wiki.return_value = MagicMock(pages=[])

                result = await handle_index_repository(
                    {
                        "repo_path": str(tmp_path),
                    }
                )

                assert len(result) == 1
                data = json.loads(result[0].text)
                assert data["status"] == "success"
                # Check that progress messages were captured
                assert any("Indexing files" in msg for msg in data["messages"])
                assert any("Creating embeddings" in msg for msg in data["messages"])


class TestHandleDeepResearchErrorHandling:
    """Tests for handle_deep_research error handling paths."""

    async def test_handles_generic_exception(self, tmp_path):
        """Test that generic exceptions are caught and returned as errors."""
        with patch(
            "local_deepwiki.handlers._handle_deep_research_impl",
            side_effect=RuntimeError("Unexpected error"),
        ):
            result = await handle_deep_research(
                {
                    "repo_path": str(tmp_path),
                    "question": "Test question",
                }
            )

            assert len(result) == 1
            assert "Error" in result[0].text
            assert "Unexpected error" in result[0].text


class TestHandleDeepResearchImpl:
    """Tests for _handle_deep_research_impl implementation."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_llm_provider(self):
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.generate = AsyncMock(return_value="Test answer")
        return mock

    async def test_successful_research(self, tmp_path):
        """Test successful deep research execution."""
        # Create vector db path
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze gaps",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            from types import SimpleNamespace

                            # Create mock research result with proper types
                            mock_result = SimpleNamespace(
                                question="Test question",
                                answer="Test answer",
                                sub_questions=[
                                    SimpleNamespace(question="Sub Q1", category="architecture"),
                                ],
                                sources=[
                                    SimpleNamespace(
                                        file_path="test.py",
                                        start_line=1,
                                        end_line=10,
                                        chunk_type="function",
                                        name="test_func",
                                        relevance_score=0.9,
                                    ),
                                ],
                                reasoning_trace=[
                                    SimpleNamespace(
                                        step_type=SimpleNamespace(value="decomposition"),
                                        description="Breaking down question",
                                        duration_ms=100,
                                    ),
                                ],
                                total_chunks_analyzed=10,
                                total_llm_calls=3,
                            )

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(return_value=mock_result)
                            mock_pipeline_class.return_value = mock_pipeline

                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "What is the architecture?",
                                }
                            )

                            assert len(result) == 1
                            data = json.loads(result[0].text)
                            assert data["question"] == "Test question"
                            assert data["answer"] == "Test answer"
                            assert len(data["sub_questions"]) == 1
                            assert len(data["sources"]) == 1
                            assert data["stats"]["chunks_analyzed"] == 10

    async def test_research_with_preset(self, tmp_path):
        """Test deep research with preset parameter."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=5,
                chunks_per_subquestion=10,
                max_total_chunks=50,
                max_follow_up_queries=3,
                synthesis_temperature=0.5,
                synthesis_max_tokens=4000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_result = MagicMock()
                            mock_result.question = "Test"
                            mock_result.answer = "Answer"
                            mock_result.sub_questions = []
                            mock_result.sources = []
                            mock_result.reasoning_trace = []
                            mock_result.total_chunks_analyzed = 5
                            mock_result.total_llm_calls = 2

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(return_value=mock_result)
                            mock_pipeline_class.return_value = mock_pipeline

                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                    "preset": "thorough",
                                }
                            )

                            # Verify preset was passed to config
                            config.deep_research.with_preset.assert_called_with("thorough")
                            assert len(result) == 1

    async def test_research_cancelled_error(self, tmp_path):
        """Test handling of ResearchCancelledError."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            from local_deepwiki.core.deep_research import ResearchCancelledError

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(
                                side_effect=ResearchCancelledError("synthesis")
                            )
                            mock_pipeline_class.return_value = mock_pipeline

                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                }
                            )

                            assert len(result) == 1
                            data = json.loads(result[0].text)
                            assert data["status"] == "cancelled"
                            assert "synthesis" in data["message"]

    async def test_research_asyncio_cancelled_error(self, tmp_path):
        """Test handling of asyncio.CancelledError."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(side_effect=asyncio.CancelledError())
                            mock_pipeline_class.return_value = mock_pipeline

                            with pytest.raises(asyncio.CancelledError):
                                await _handle_deep_research_impl(
                                    {
                                        "repo_path": str(tmp_path),
                                        "question": "Test question",
                                    }
                                )

    async def test_progress_callback_with_server(self, tmp_path):
        """Test progress callback sends notifications with server."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        # Create mock server with request context
        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.meta.progressToken = "test-token"
        mock_ctx.session.send_progress_notification = AsyncMock()
        mock_server.request_context = mock_ctx

        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_result = MagicMock()
                            mock_result.question = "Test"
                            mock_result.answer = "Answer"
                            mock_result.sub_questions = []
                            mock_result.sources = []
                            mock_result.reasoning_trace = []
                            mock_result.total_chunks_analyzed = 5
                            mock_result.total_llm_calls = 2

                            async def mock_research(
                                question, progress_callback=None, cancellation_check=None
                            ):
                                # Call progress callback to test notification sending
                                if progress_callback:
                                    from local_deepwiki.models import (
                                        ResearchProgress,
                                        ResearchProgressType,
                                    )

                                    await progress_callback(
                                        ResearchProgress(
                                            step=1,
                                            step_type=ResearchProgressType.DECOMPOSITION_COMPLETE,
                                            message="Decomposing question",
                                        )
                                    )
                                return mock_result

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = mock_research
                            mock_pipeline_class.return_value = mock_pipeline

                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                },
                                server=mock_server,
                            )

                            assert len(result) == 1

    async def test_progress_callback_without_server(self, tmp_path):
        """Test progress callback handles missing server gracefully."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_result = MagicMock()
                            mock_result.question = "Test"
                            mock_result.answer = "Answer"
                            mock_result.sub_questions = []
                            mock_result.sources = []
                            mock_result.reasoning_trace = []
                            mock_result.total_chunks_analyzed = 5
                            mock_result.total_llm_calls = 2

                            async def mock_research(
                                question, progress_callback=None, cancellation_check=None
                            ):
                                if progress_callback:
                                    from local_deepwiki.models import (
                                        ResearchProgress,
                                        ResearchProgressType,
                                    )

                                    # This should not raise even without server
                                    await progress_callback(
                                        ResearchProgress(
                                            step=1,
                                            step_type=ResearchProgressType.DECOMPOSITION_COMPLETE,
                                            message="Decomposing",
                                        )
                                    )
                                return mock_result

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = mock_research
                            mock_pipeline_class.return_value = mock_pipeline

                            # Call without server - should not raise
                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                }
                            )

                            assert len(result) == 1

    async def test_server_without_progress_token(self, tmp_path):
        """Test handling server without progress token in request context."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        # Create mock server with request context but no progress token
        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.meta = None  # No meta
        mock_server.request_context = mock_ctx

        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_result = MagicMock()
                            mock_result.question = "Test"
                            mock_result.answer = "Answer"
                            mock_result.sub_questions = []
                            mock_result.sources = []
                            mock_result.reasoning_trace = []
                            mock_result.total_chunks_analyzed = 5
                            mock_result.total_llm_calls = 2

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(return_value=mock_result)
                            mock_pipeline_class.return_value = mock_pipeline

                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                },
                                server=mock_server,
                            )

                            assert len(result) == 1

    async def test_server_lookup_error(self, tmp_path):
        """Test handling LookupError when accessing request context."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        # Create mock server that raises LookupError on request_context access
        mock_server = MagicMock()
        type(mock_server).request_context = property(
            lambda self: (_ for _ in ()).throw(LookupError("Not in request context"))
        )

        with patch("local_deepwiki.handlers.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.get_embedding_provider"):
                with patch("local_deepwiki.handlers.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_result = MagicMock()
                            mock_result.question = "Test"
                            mock_result.answer = "Answer"
                            mock_result.sub_questions = []
                            mock_result.sources = []
                            mock_result.reasoning_trace = []
                            mock_result.total_chunks_analyzed = 5
                            mock_result.total_llm_calls = 2

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(return_value=mock_result)
                            mock_pipeline_class.return_value = mock_pipeline

                            # Should not raise
                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                },
                                server=mock_server,
                            )

                            assert len(result) == 1


class TestHandleExportWikiPdf:
    """Tests for handle_export_wiki_pdf handler."""

    async def test_returns_error_for_nonexistent_wiki(self, tmp_path):
        """Test error returned for non-existent wiki path."""
        import sys

        nonexistent = tmp_path / "does_not_exist"

        # Mock the pdf module before import
        mock_pdf_module = MagicMock()
        mock_pdf_module.export_to_pdf = MagicMock(return_value="Success")

        with patch.dict(sys.modules, {"local_deepwiki.export.pdf": mock_pdf_module}):
            result = await handle_export_wiki_pdf({"wiki_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_exports_single_file_pdf(self, tmp_path):
        """Test exporting wiki to single PDF file."""
        import sys

        # Create minimal wiki
        (tmp_path / "index.md").write_text("# Test Wiki")

        mock_pdf_module = MagicMock()
        mock_pdf_module.export_to_pdf = MagicMock(return_value="Exported successfully")

        with patch.dict(sys.modules, {"local_deepwiki.export.pdf": mock_pdf_module}):
            result = await handle_export_wiki_pdf(
                {
                    "wiki_path": str(tmp_path),
                    "single_file": True,
                }
            )

            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["status"] == "success"
            assert data["message"] == "Exported successfully"
            # Default output should be wiki_name.pdf
            assert data["output_path"].endswith(".pdf")

    async def test_exports_multiple_pdfs(self, tmp_path):
        """Test exporting wiki to multiple PDF files."""
        import sys

        (tmp_path / "index.md").write_text("# Test Wiki")

        mock_pdf_module = MagicMock()
        mock_pdf_module.export_to_pdf = MagicMock(return_value="Exported 5 pages")

        with patch.dict(sys.modules, {"local_deepwiki.export.pdf": mock_pdf_module}):
            result = await handle_export_wiki_pdf(
                {
                    "wiki_path": str(tmp_path),
                    "single_file": False,
                }
            )

            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["status"] == "success"
            # Multiple files output should be wiki_name_pdfs directory
            assert data["output_path"].endswith("_pdfs")

    async def test_exports_with_custom_output_path(self, tmp_path):
        """Test exporting wiki to custom output path."""
        import sys

        (tmp_path / "index.md").write_text("# Test Wiki")
        output_path = tmp_path / "custom_output.pdf"

        mock_pdf_module = MagicMock()
        mock_pdf_module.export_to_pdf = MagicMock(return_value="Exported to custom path")

        with patch.dict(sys.modules, {"local_deepwiki.export.pdf": mock_pdf_module}):
            result = await handle_export_wiki_pdf(
                {
                    "wiki_path": str(tmp_path),
                    "output_path": str(output_path),
                }
            )

            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["status"] == "success"
            assert str(output_path) in data["output_path"]

    async def test_default_single_file_true(self, tmp_path):
        """Test that single_file defaults to True."""
        import sys

        (tmp_path / "index.md").write_text("# Test Wiki")

        mock_pdf_module = MagicMock()
        mock_export = MagicMock(return_value="Success")
        mock_pdf_module.export_to_pdf = mock_export

        with patch.dict(sys.modules, {"local_deepwiki.export.pdf": mock_pdf_module}):
            await handle_export_wiki_pdf(
                {
                    "wiki_path": str(tmp_path),
                }
            )

            # Verify export_to_pdf was called with single_file=True
            mock_export.assert_called_once()
            call_kwargs = mock_export.call_args[1]
            assert call_kwargs["single_file"] is True
