"""Tests for QueryService: RAG pipeline and code search."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from local_deepwiki.services.models import QueryResult
from local_deepwiki.services.query_service import (
    CodeSearchRequest,
    QuestionRequest,
    QueryService,
)


def _make_search_result(
    file_path: str = "src/main.py",
    start_line: int = 1,
    end_line: int = 10,
    content: str = "def hello(): pass",
    chunk_type_value: str = "function",
    score: float = 0.9,
    name: str = "hello",
    language_value: str = "python",
    docstring: str | None = None,
    highlights: list[str] | None = None,
) -> MagicMock:
    """Create a mock SearchResult."""
    chunk = MagicMock()
    chunk.file_path = file_path
    chunk.start_line = start_line
    chunk.end_line = end_line
    chunk.content = content
    chunk.chunk_type.value = chunk_type_value
    chunk.name = name
    chunk.language.value = language_value
    chunk.docstring = docstring

    result = MagicMock()
    result.chunk = chunk
    result.score = score
    result.highlights = highlights or []
    return result


def _make_deps(tmp_path: Path) -> tuple[MagicMock, AsyncMock, MagicMock]:
    """Create mock VectorStore, LLMProvider, and Config."""
    vector_store = MagicMock()
    vector_store.search = AsyncMock(return_value=[])

    llm_provider = AsyncMock()
    llm_provider.generate = AsyncMock(return_value="The answer is 42.")

    config = MagicMock()
    config.get_wiki_path.return_value = tmp_path / ".deepwiki"
    return vector_store, llm_provider, config


class TestAnswerQuestion:
    """Tests for QueryService.answer_question."""

    async def test_returns_query_result_with_sources(self, tmp_path: Path):
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        wiki_path = tmp_path / ".deepwiki"
        wiki_page = wiki_path / "files" / "src" / "main.py.md"
        wiki_page.parent.mkdir(parents=True, exist_ok=True)
        wiki_page.write_text("# main.py")

        svc = QueryService(vector_store, llm_provider, config)

        with patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl:
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()
            result = await svc.answer_question(
                QuestionRequest(repo_path=tmp_path, question="What does hello do?")
            )

        assert isinstance(result, QueryResult)
        assert result.answer == "The answer is 42."
        assert len(result.sources) == 1
        assert result.sources[0].file == "src/main.py"
        assert result.sources[0].chunk_type == "function"
        assert result.agentic_metadata is None

    async def test_no_results_returns_empty_sources(self, tmp_path: Path):
        vector_store, llm_provider, config = _make_deps(tmp_path)
        vector_store.search = AsyncMock(return_value=[])

        svc = QueryService(vector_store, llm_provider, config)
        result = await svc.answer_question(
            QuestionRequest(repo_path=tmp_path, question="Nonexistent?")
        )

        assert isinstance(result, QueryResult)
        assert "No relevant code found" in result.answer
        assert result.sources == ()

    async def test_agentic_rag_delegates(self, tmp_path: Path):
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result()

        mock_rag_result = MagicMock()
        mock_rag_result.results = [sr]
        mock_rag_result.metadata = {"rounds": 2, "rewritten": True}

        svc = QueryService(vector_store, llm_provider, config)

        with (
            patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl,
            patch(
                "local_deepwiki.core.agentic_rag.agentic_retrieve",
                new_callable=AsyncMock,
                return_value=mock_rag_result,
            ),
        ):
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()
            result = await svc.answer_question(
                QuestionRequest(repo_path=tmp_path, question="How?", agentic_rag=True)
            )

        assert result.agentic_metadata == {"rounds": 2, "rewritten": True}
        assert len(result.sources) == 1

    async def test_llm_called_with_context(self, tmp_path: Path):
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result(content="def add(a, b): return a + b")
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)

        with patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl:
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()
            await svc.answer_question(
                QuestionRequest(repo_path=tmp_path, question="What does add do?")
            )

        call_args = llm_provider.generate.call_args
        prompt = call_args[0][0]
        assert "def add(a, b): return a + b" in prompt
        assert "What does add do?" in prompt


class TestSearchCode:
    """Tests for QueryService.search_code."""

    async def test_returns_formatted_results(self, tmp_path: Path):
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result(
            file_path="lib/utils.py",
            name="parse",
            chunk_type_value="function",
            language_value="python",
            score=0.85,
            content="def parse(x): ...",
            docstring="Parse input.",
        )
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)
        results = await svc.search_code(
            CodeSearchRequest(repo_path=tmp_path, query="parse")
        )

        assert len(results) == 1
        assert results[0]["file_path"] == "lib/utils.py"
        assert results[0]["name"] == "parse"
        assert results[0]["type"] == "function"
        assert results[0]["score"] == 0.85
        assert results[0]["docstring"] == "Parse input."

    async def test_empty_results(self, tmp_path: Path):
        vector_store, llm_provider, config = _make_deps(tmp_path)
        vector_store.search = AsyncMock(return_value=[])

        svc = QueryService(vector_store, llm_provider, config)
        results = await svc.search_code(
            CodeSearchRequest(repo_path=tmp_path, query="nonexistent")
        )

        assert results == []

    async def test_passes_filters_to_vector_store(self, tmp_path: Path):
        vector_store, llm_provider, config = _make_deps(tmp_path)
        vector_store.search = AsyncMock(return_value=[])

        svc = QueryService(vector_store, llm_provider, config)
        await svc.search_code(
            CodeSearchRequest(
                repo_path=tmp_path,
                query="test",
                limit=5,
                language="python",
                chunk_type="function",
                path_filter="src/**",
                use_fuzzy=True,
                fuzzy_weight=0.5,
            )
        )

        vector_store.search.assert_called_once_with(
            "test",
            limit=5,
            language="python",
            chunk_type="function",
            path_pattern="src/**",
            use_fuzzy=True,
            fuzzy_weight=0.5,
        )

    async def test_includes_highlights_when_present(self, tmp_path: Path):
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result(highlights=["parse_data"])
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)
        results = await svc.search_code(
            CodeSearchRequest(repo_path=tmp_path, query="parse")
        )

        assert results[0]["highlights"] == ["parse_data"]

    async def test_long_content_truncated_in_preview(self, tmp_path: Path):
        vector_store, llm_provider, config = _make_deps(tmp_path)
        long_content = "x" * 500
        sr = _make_search_result(content=long_content)
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)
        results = await svc.search_code(
            CodeSearchRequest(repo_path=tmp_path, query="x")
        )

        assert results[0]["preview"].endswith("...")
        assert len(results[0]["preview"]) == 303  # 300 + "..."


class TestHybridSearchDefault:
    """Tests for hybrid search being enabled by default in answer_question."""

    async def test_answer_question_uses_hybrid_search(self, tmp_path: Path):
        """Non-agentic answer_question should pass use_fuzzy=True to vector search."""
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)

        with patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl:
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()
            await svc.answer_question(
                QuestionRequest(repo_path=tmp_path, question="What does hello do?")
            )

        # Verify the vector store search was called with hybrid search params
        call_kwargs = vector_store.search.call_args[1]
        assert call_kwargs["use_fuzzy"] is True
        assert call_kwargs["fuzzy_weight"] == 0.3


class TestQueryPreprocessing:
    """Tests for query preprocessing (filler stripping + term expansion)."""

    async def test_filler_words_stripped(self, tmp_path: Path):
        """Conversational filler like 'tell' and 'everything' should be stripped
        from the search query (but preserved in the LLM prompt)."""
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)

        with patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl:
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()
            await svc.answer_question(
                QuestionRequest(
                    repo_path=tmp_path,
                    question="tell me everything about the parser",
                )
            )

        # The search query should NOT contain filler words
        search_query = vector_store.search.call_args[0][0]
        assert "tell" not in search_query.lower().split()
        assert "everything" not in search_query.lower().split()

        # The LLM prompt should still use the original question
        llm_prompt = llm_provider.generate.call_args[0][0]
        assert "tell me everything about the parser" in llm_prompt

    async def test_project_terms_expanded(self, tmp_path: Path):
        """Domain terms like 'handler' should be expanded with project-specific
        synonyms (e.g. 'TOOL_HANDLERS', 'handle_') in the search query."""
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)

        with patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl:
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()
            await svc.answer_question(
                QuestionRequest(repo_path=tmp_path, question="handler routing")
            )

        search_query = vector_store.search.call_args[0][0]
        assert "TOOL_HANDLERS" in search_query or "handle_" in search_query


class TestAnswerQuestionStream:
    """Tests for QueryService.answer_question_stream."""

    async def test_streams_sources_then_tokens_then_done(self, tmp_path: Path):
        """Streaming should yield sources, then token chunks, then done."""
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        # Mock generate_stream to yield tokens
        async def mock_stream(*args, **kwargs):
            yield "Hello "
            yield "world"

        llm_provider.generate_stream = mock_stream

        svc = QueryService(vector_store, llm_provider, config)
        chunks: list[dict] = []
        async for chunk in svc.answer_question_stream(
            repo_path=tmp_path, question="What does hello do?"
        ):
            chunks.append(chunk)

        # First chunk should be sources
        assert chunks[0]["type"] == "sources"
        assert isinstance(chunks[0]["sources"], list)
        assert len(chunks[0]["sources"]) == 1
        assert chunks[0]["sources"][0]["file"] == "src/main.py"

        # Last chunk should be done
        assert chunks[-1]["type"] == "done"

        # Middle chunks should be tokens
        token_chunks = [c for c in chunks if c["type"] == "token"]
        assert len(token_chunks) == 2
        assert token_chunks[0]["content"] == "Hello "
        assert token_chunks[1]["content"] == "world"

    async def test_stream_empty_results(self, tmp_path: Path):
        """When search returns nothing, should yield sources, error token, and done."""
        vector_store, llm_provider, config = _make_deps(tmp_path)
        vector_store.search = AsyncMock(return_value=[])

        svc = QueryService(vector_store, llm_provider, config)
        chunks: list[dict] = []
        async for chunk in svc.answer_question_stream(
            repo_path=tmp_path, question="Unknown?"
        ):
            chunks.append(chunk)

        # Should yield sources (empty), token with message, and done
        assert chunks[0]["type"] == "sources"
        assert chunks[0]["sources"] == []

        token_chunks = [c for c in chunks if c["type"] == "token"]
        assert any("No relevant code found" in c["content"] for c in token_chunks)

        assert chunks[-1]["type"] == "done"

    async def test_stream_with_history(self, tmp_path: Path):
        """Streaming with conversation history should include history in prompt."""
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        captured_prompt = []

        async def mock_stream(prompt, **kwargs):
            captured_prompt.append(prompt)
            yield "Answer"

        llm_provider.generate_stream = mock_stream

        history = [
            {"question": "What is foo?", "answer": "Foo is a function."},
        ]

        svc = QueryService(vector_store, llm_provider, config)
        chunks: list[dict] = []
        async for chunk in svc.answer_question_stream(
            repo_path=tmp_path,
            question="Tell me more",
            history=history,
        ):
            chunks.append(chunk)

        # Prompt should contain history context
        assert len(captured_prompt) == 1
        assert "What is foo?" in captured_prompt[0]
        assert "Foo is a function." in captured_prompt[0]
        assert "Tell me more" in captured_prompt[0]

    async def test_stream_llm_error_yields_error_chunk(self, tmp_path: Path):
        """When LLM streaming fails, should yield error chunk and done."""
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        async def failing_stream(*args, **kwargs):
            yield "Starting..."
            raise RuntimeError("LLM connection failed")

        llm_provider.generate_stream = failing_stream

        svc = QueryService(vector_store, llm_provider, config)
        chunks: list[dict] = []
        async for chunk in svc.answer_question_stream(
            repo_path=tmp_path, question="Test?"
        ):
            chunks.append(chunk)

        # Should have sources, at least one token, error, and done
        assert chunks[0]["type"] == "sources"
        error_chunks = [c for c in chunks if c["type"] == "error"]
        assert len(error_chunks) == 1
        assert "message" in error_chunks[0]
        assert chunks[-1]["type"] == "done"

    async def test_stream_max_context_parameter(self, tmp_path: Path):
        """max_context should be passed as limit to vector search."""
        vector_store, llm_provider, config = _make_deps(tmp_path)
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        async def mock_stream(*args, **kwargs):
            yield "Done"

        llm_provider.generate_stream = mock_stream

        svc = QueryService(vector_store, llm_provider, config)
        chunks: list[dict] = []
        async for chunk in svc.answer_question_stream(
            repo_path=tmp_path, question="Test?", max_context=5
        ):
            chunks.append(chunk)

        # Should pass max_context as limit to vector store search
        call_kwargs = vector_store.search.call_args
        assert call_kwargs[1]["limit"] == 5
        assert call_kwargs[1]["search_mode"] == "hybrid"
        assert chunks[0]["type"] == "sources"


async def test_answer_question_stream_uses_hybrid_search(tmp_path: Path):
    """answer_question_stream should use hybrid search mode."""
    mock_vs = MagicMock()
    mock_vs.search = AsyncMock(return_value=[])
    mock_llm = MagicMock()
    mock_config = MagicMock()
    mock_config.get_wiki_path.return_value = tmp_path / ".deepwiki"

    service = QueryService(mock_vs, mock_llm, mock_config)

    chunks = []
    async for chunk in service.answer_question_stream(
        repo_path=tmp_path,
        question="how are vectors created",
    ):
        chunks.append(chunk)

    # Verify hybrid search mode was used
    mock_vs.search.assert_called_once()
    _, kwargs = mock_vs.search.call_args
    assert kwargs.get("search_mode") == "hybrid", (
        f"Expected search_mode='hybrid', got {kwargs}"
    )
