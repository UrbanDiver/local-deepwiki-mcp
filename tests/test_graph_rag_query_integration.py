"""Tests for GraphRAG query pipeline integration.

Verifies that ``expand_with_graph`` is wired into ``QueryService`` correctly
and that the helper itself handles enabled/disabled/error cases properly.
The ``GraphAugmentedRetriever`` is always mocked -- its own unit tests live
in ``test_graph_rag_retriever.py``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config.models import GraphRAGConfig
from local_deepwiki.services.graph_expansion import expand_with_graph
from local_deepwiki.services.query_service import (
    CodeSearchRequest,
    QuestionRequest,
    QueryService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    chunk_id: str = "chunk-1",
) -> MagicMock:
    """Create a mock SearchResult."""
    chunk = MagicMock()
    chunk.id = chunk_id
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


def _make_graph_search_result(
    chunk_id: str = "graph-chunk-1",
    file_path: str = "src/helper.py",
    name: str = "helper",
    score: float = 0.4,
) -> MagicMock:
    """Create a mock SearchResult representing a graph-discovered chunk."""
    return _make_search_result(
        chunk_id=chunk_id,
        file_path=file_path,
        name=name,
        score=score,
        highlights=["graph-expanded"],
    )


def _make_config(
    graph_rag_enabled: bool = False, **graph_rag_kwargs: object
) -> MagicMock:
    """Create a mock Config with graph_rag settings."""
    config = MagicMock()
    graph_rag_defaults = {
        "enabled": graph_rag_enabled,
        "max_traversal_depth": 2,
        "max_graph_neighbors": 15,
        "relationship_types": ["calls", "imports"],
        "score_boost_factor": 0.7,
        "extract_during_index": True,
    }
    graph_rag_defaults.update(graph_rag_kwargs)
    config.graph_rag = GraphRAGConfig(**graph_rag_defaults)  # type: ignore[arg-type]
    config.get_vector_db_path.return_value = Path("/nonexistent/vectors.lance")
    config.get_wiki_path.return_value = Path("/nonexistent/.deepwiki")
    config.search.reranker_model = None
    return config


def _make_deps(
    tmp_path: Path,
    graph_rag_enabled: bool = False,
) -> tuple[MagicMock, AsyncMock, MagicMock]:
    """Create mock VectorStore, LLMProvider, and Config."""
    vector_store = MagicMock()
    vector_store.search = AsyncMock(return_value=[])

    llm_provider = AsyncMock()
    llm_provider.generate = AsyncMock(return_value="The answer is 42.")

    config = _make_config(graph_rag_enabled=graph_rag_enabled)
    config.get_wiki_path.return_value = tmp_path / ".deepwiki"
    config.get_vector_db_path.return_value = tmp_path / "vectors.lance"

    return vector_store, llm_provider, config


# ---------------------------------------------------------------------------
# expand_with_graph unit tests
# ---------------------------------------------------------------------------


class TestExpandWithGraph:
    """Tests for the expand_with_graph helper function."""

    async def test_skips_when_disabled(self, tmp_path: Path):
        """When graph_rag.enabled is False, returns results unchanged."""
        config = _make_config(graph_rag_enabled=False)
        vector_store = MagicMock()
        original = [_make_search_result()]

        result = await expand_with_graph(original, vector_store, config, tmp_path)

        assert result is original

    async def test_skips_when_empty_results(self, tmp_path: Path):
        """When search_results is empty, returns it as-is even if enabled."""
        config = _make_config(graph_rag_enabled=True)
        vector_store = MagicMock()
        empty: list[MagicMock] = []

        result = await expand_with_graph(empty, vector_store, config, tmp_path)

        assert result is empty

    async def test_calls_retriever_when_enabled(self, tmp_path: Path):
        """When enabled, creates retriever and calls expand_results."""
        config = _make_config(graph_rag_enabled=True)
        config.get_vector_db_path.return_value = tmp_path / "vectors.lance"
        vector_store = MagicMock()
        original = [_make_search_result()]
        expanded = original + [_make_graph_search_result()]

        with (
            patch(
                "local_deepwiki.services.graph_expansion.KnowledgeGraphStore"
            ) as mock_store_cls,
            patch(
                "local_deepwiki.services.graph_expansion.GraphAugmentedRetriever"
            ) as mock_retriever_cls,
        ):
            mock_retriever = MagicMock()
            mock_retriever.expand_results = AsyncMock(return_value=expanded)
            mock_retriever_cls.return_value = mock_retriever

            result = await expand_with_graph(original, vector_store, config, tmp_path)

        assert result == expanded
        mock_store_cls.assert_called_once_with(tmp_path / "vectors.lance")
        mock_retriever_cls.assert_called_once()
        mock_retriever.expand_results.assert_awaited_once_with(original)

    async def test_passes_config_to_retriever(self, tmp_path: Path):
        """Retriever receives the GraphRAGConfig from the main config."""
        config = _make_config(
            graph_rag_enabled=True,
            max_traversal_depth=3,
            max_graph_neighbors=10,
        )
        config.get_vector_db_path.return_value = tmp_path / "vectors.lance"
        vector_store = MagicMock()
        original = [_make_search_result()]

        with (
            patch("local_deepwiki.services.graph_expansion.KnowledgeGraphStore"),
            patch(
                "local_deepwiki.services.graph_expansion.GraphAugmentedRetriever"
            ) as mock_retriever_cls,
        ):
            mock_retriever = MagicMock()
            mock_retriever.expand_results = AsyncMock(return_value=original)
            mock_retriever_cls.return_value = mock_retriever

            await expand_with_graph(original, vector_store, config, tmp_path)

        call_kwargs = mock_retriever_cls.call_args
        passed_config = call_kwargs.kwargs["config"]
        assert passed_config.max_traversal_depth == 3
        assert passed_config.max_graph_neighbors == 10

    async def test_returns_original_on_error(self, tmp_path: Path):
        """If expansion raises, logs a warning and returns original results."""
        config = _make_config(graph_rag_enabled=True)
        config.get_vector_db_path.return_value = tmp_path / "vectors.lance"
        vector_store = MagicMock()
        original = [_make_search_result()]

        with (
            patch("local_deepwiki.services.graph_expansion.KnowledgeGraphStore"),
            patch(
                "local_deepwiki.services.graph_expansion.GraphAugmentedRetriever"
            ) as mock_retriever_cls,
            patch("local_deepwiki.services.graph_expansion.logger") as mock_logger,
        ):
            mock_retriever = MagicMock()
            mock_retriever.expand_results = AsyncMock(
                side_effect=RuntimeError("LanceDB not found")
            )
            mock_retriever_cls.return_value = mock_retriever

            result = await expand_with_graph(original, vector_store, config, tmp_path)

        assert result is original
        mock_logger.warning.assert_called_once()
        assert "Graph expansion failed" in mock_logger.warning.call_args[0][0]

    async def test_returns_original_on_import_error(self, tmp_path: Path):
        """If graph_rag module fails to import, returns original results."""
        config = _make_config(graph_rag_enabled=True)
        config.get_vector_db_path.return_value = tmp_path / "vectors.lance"
        vector_store = MagicMock()
        original = [_make_search_result()]

        with (
            patch(
                "local_deepwiki.services.graph_expansion.KnowledgeGraphStore",
                side_effect=ImportError("no lancedb"),
            ),
            patch("local_deepwiki.services.graph_expansion.logger") as mock_logger,
        ):
            result = await expand_with_graph(original, vector_store, config, tmp_path)

        assert result is original
        mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# QueryService integration tests
# ---------------------------------------------------------------------------


class TestQueryServiceGraphExpansion:
    """Tests that QueryService properly integrates graph expansion."""

    async def test_answer_question_calls_expand_when_enabled(self, tmp_path: Path):
        """answer_question invokes expand_with_graph after retrieval."""
        vector_store, llm_provider, config = _make_deps(
            tmp_path, graph_rag_enabled=True
        )
        sr = _make_search_result()
        graph_sr = _make_graph_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)

        with (
            patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl,
            patch("local_deepwiki.services.graph_expansion.KnowledgeGraphStore"),
            patch(
                "local_deepwiki.services.graph_expansion.GraphAugmentedRetriever"
            ) as mock_retriever_cls,
        ):
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()

            mock_retriever = MagicMock()
            mock_retriever.expand_results = AsyncMock(return_value=[sr, graph_sr])
            mock_retriever_cls.return_value = mock_retriever

            result = await svc.answer_question(
                QuestionRequest(repo_path=tmp_path, question="What does hello do?")
            )

        # Both vector and graph results should appear in sources
        assert len(result.sources) == 2
        assert result.sources[0].file == "src/main.py"
        assert result.sources[1].file == "src/helper.py"

    async def test_answer_question_skips_expand_when_disabled(self, tmp_path: Path):
        """answer_question does not call retriever when graph_rag disabled."""
        vector_store, llm_provider, config = _make_deps(
            tmp_path, graph_rag_enabled=False
        )
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)

        with (
            patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl,
            patch(
                "local_deepwiki.services.graph_expansion.GraphAugmentedRetriever"
            ) as mock_retriever_cls,
        ):
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()

            result = await svc.answer_question(
                QuestionRequest(repo_path=tmp_path, question="What does hello do?")
            )

        # Retriever should never be instantiated
        mock_retriever_cls.assert_not_called()
        assert len(result.sources) == 1

    async def test_search_code_includes_graph_results(self, tmp_path: Path):
        """search_code includes graph-expanded results in output."""
        vector_store, llm_provider, config = _make_deps(
            tmp_path, graph_rag_enabled=True
        )
        sr = _make_search_result()
        graph_sr = _make_graph_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)

        with (
            patch("local_deepwiki.services.graph_expansion.KnowledgeGraphStore"),
            patch(
                "local_deepwiki.services.graph_expansion.GraphAugmentedRetriever"
            ) as mock_retriever_cls,
        ):
            mock_retriever = MagicMock()
            mock_retriever.expand_results = AsyncMock(return_value=[sr, graph_sr])
            mock_retriever_cls.return_value = mock_retriever

            results = await svc.search_code(
                CodeSearchRequest(repo_path=tmp_path, query="hello")
            )

        assert len(results) == 2
        assert results[0]["file_path"] == "src/main.py"
        assert results[1]["file_path"] == "src/helper.py"
        assert results[1]["highlights"] == ["graph-expanded"]

    async def test_search_code_skips_expand_when_disabled(self, tmp_path: Path):
        """search_code does not call retriever when graph_rag disabled."""
        vector_store, llm_provider, config = _make_deps(
            tmp_path, graph_rag_enabled=False
        )
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)

        with patch(
            "local_deepwiki.services.graph_expansion.GraphAugmentedRetriever"
        ) as mock_retriever_cls:
            results = await svc.search_code(
                CodeSearchRequest(repo_path=tmp_path, query="hello")
            )

        mock_retriever_cls.assert_not_called()
        assert len(results) == 1

    async def test_answer_question_survives_graph_failure(self, tmp_path: Path):
        """answer_question still produces an answer when graph expansion fails."""
        vector_store, llm_provider, config = _make_deps(
            tmp_path, graph_rag_enabled=True
        )
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)

        with (
            patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl,
            patch("local_deepwiki.services.graph_expansion.KnowledgeGraphStore"),
            patch(
                "local_deepwiki.services.graph_expansion.GraphAugmentedRetriever"
            ) as mock_retriever_cls,
        ):
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()

            mock_retriever = MagicMock()
            mock_retriever.expand_results = AsyncMock(
                side_effect=RuntimeError("graph exploded")
            )
            mock_retriever_cls.return_value = mock_retriever

            result = await svc.answer_question(
                QuestionRequest(repo_path=tmp_path, question="What does hello do?")
            )

        # Should still get an answer from original vector results
        assert result.answer == "The answer is 42."
        assert len(result.sources) == 1

    async def test_search_code_survives_graph_failure(self, tmp_path: Path):
        """search_code returns vector results when graph expansion fails."""
        vector_store, llm_provider, config = _make_deps(
            tmp_path, graph_rag_enabled=True
        )
        sr = _make_search_result()
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)

        with (
            patch("local_deepwiki.services.graph_expansion.KnowledgeGraphStore"),
            patch(
                "local_deepwiki.services.graph_expansion.GraphAugmentedRetriever"
            ) as mock_retriever_cls,
        ):
            mock_retriever = MagicMock()
            mock_retriever.expand_results = AsyncMock(
                side_effect=RuntimeError("graph exploded")
            )
            mock_retriever_cls.return_value = mock_retriever

            results = await svc.search_code(
                CodeSearchRequest(repo_path=tmp_path, query="hello")
            )

        assert len(results) == 1
        assert results[0]["file_path"] == "src/main.py"

    async def test_answer_question_graph_results_in_context(self, tmp_path: Path):
        """Graph-expanded results are included in the LLM prompt context."""
        vector_store, llm_provider, config = _make_deps(
            tmp_path, graph_rag_enabled=True
        )
        sr = _make_search_result(content="def hello(): pass")
        graph_sr = _make_graph_search_result()
        # Give the graph result distinct content
        graph_sr.chunk.content = "def helper(): return 42"
        vector_store.search = AsyncMock(return_value=[sr])

        svc = QueryService(vector_store, llm_provider, config)

        with (
            patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl,
            patch("local_deepwiki.services.graph_expansion.KnowledgeGraphStore"),
            patch(
                "local_deepwiki.services.graph_expansion.GraphAugmentedRetriever"
            ) as mock_retriever_cls,
        ):
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()

            mock_retriever = MagicMock()
            mock_retriever.expand_results = AsyncMock(return_value=[sr, graph_sr])
            mock_retriever_cls.return_value = mock_retriever

            await svc.answer_question(
                QuestionRequest(repo_path=tmp_path, question="What does hello do?")
            )

        # The LLM prompt should include content from both vector and graph results
        call_args = llm_provider.generate.call_args
        prompt = call_args[0][0]
        assert "def hello(): pass" in prompt
        assert "def helper(): return 42" in prompt
