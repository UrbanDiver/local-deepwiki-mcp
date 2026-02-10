"""Tests for handler index and Q&A operations - tool errors, index repository, ask question."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from local_deepwiki.handlers import (
    handle_ask_question,
    handle_index_repository,
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
        # Error now includes hints and wraps the original message
        assert "Something went wrong" in result[0].text
        assert "Error" in result[0].text

    async def test_propagates_cancelled_error(self):
        """Test decorator re-raises CancelledError."""

        @handle_tool_errors
        async def cancelled_handler(args):
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await cancelled_handler({})


class TestHandleIndexRepositoryExtended:
    """Extended tests for handle_index_repository handler."""

    async def test_accepts_valid_languages_list(self, tmp_path):
        """Test accepts valid languages list."""
        # Create a minimal Python file
        (tmp_path / "test.py").write_text("print('hello')")

        # This will still fail because no actual indexing infrastructure,
        # but it tests the validation path
        with patch("local_deepwiki.handlers.core.RepositoryIndexer") as mock_indexer:
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

            with patch("local_deepwiki.handlers.core.generate_wiki") as mock_wiki:
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

        with patch("local_deepwiki.handlers.core.RepositoryIndexer") as mock_indexer:
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

            with patch("local_deepwiki.handlers.core.generate_wiki") as mock_wiki:
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
        config = MagicMock()
        config.embedding = MagicMock()
        wiki_path = tmp_path / ".deepwiki"

        with patch(
            "local_deepwiki.handlers.core._load_index_status",
            return_value=(MagicMock(), wiki_path, config),
        ):
            mock_store = MagicMock()
            mock_store.search = AsyncMock(return_value=[])

            with patch(
                "local_deepwiki.handlers.core._create_vector_store",
                return_value=mock_store,
            ):
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
        config = MagicMock()
        config.embedding = MagicMock()
        config.llm_cache = MagicMock()
        config.llm = MagicMock()
        wiki_path = tmp_path / ".deepwiki"

        with patch(
            "local_deepwiki.handlers.core._load_index_status",
            return_value=(MagicMock(), wiki_path, config),
        ):
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

            mock_store = MagicMock()
            mock_store.search = AsyncMock(return_value=[mock_result])

            with patch(
                "local_deepwiki.handlers.core._create_vector_store",
                return_value=mock_store,
            ):
                with (
                    patch(
                        "local_deepwiki.handlers.core.get_embedding_provider",
                        return_value=MagicMock(),
                    ),
                    patch(
                        "local_deepwiki.providers.llm.get_cached_llm_provider"
                    ) as mock_llm,
                ):
                    mock_provider = MagicMock()
                    mock_provider.generate = AsyncMock(
                        return_value="This is a test function."
                    )
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


class TestHandleIndexRepositoryProgressCallback:
    """Tests for handle_index_repository progress callback."""

    async def test_progress_callback_is_called(self, tmp_path):
        """Test progress callback is invoked during indexing."""
        (tmp_path / "test.py").write_text("print('hello')")

        captured_messages = []

        with patch("local_deepwiki.handlers.core.RepositoryIndexer") as mock_indexer:
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

            with patch("local_deepwiki.handlers.core.generate_wiki") as mock_wiki:
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
