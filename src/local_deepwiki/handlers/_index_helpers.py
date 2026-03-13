"""Shared index loading, vector store creation, and research formatting helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from local_deepwiki.config import get_config
from local_deepwiki.core.path_utils import is_test_file
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.errors import not_indexed_error
from local_deepwiki.handlers.types import ResearchResult
from local_deepwiki.logging import get_logger
from local_deepwiki.providers.embeddings import get_embedding_provider

if TYPE_CHECKING:
    from local_deepwiki.models import DeepResearchResult

logger = get_logger(__name__)


async def _load_index_status(repo_path: Path) -> tuple[Any, Path, Any]:
    """Load index status for a repository, raising if not indexed.

    Args:
        repo_path: Resolved path to the repository.

    Returns:
        Tuple of (IndexStatus, wiki_path, config).

    Raises:
        ValidationError: If repository is not indexed.
    """
    from local_deepwiki.core.index_manager import IndexStatusManager

    config = get_config()
    wiki_path = config.get_wiki_path(repo_path)
    vector_db_path = config.get_vector_db_path(repo_path)

    if not vector_db_path.exists():
        raise not_indexed_error(str(repo_path))

    manager = IndexStatusManager()
    index_status = await asyncio.to_thread(manager.load, wiki_path)
    if index_status is None:
        raise not_indexed_error(str(repo_path))

    return index_status, wiki_path, config


def _create_vector_store(repo_path: Path, config: Any) -> VectorStore:
    """Create a VectorStore with the configured embedding provider.

    Args:
        repo_path: Resolved path to the repository.
        config: Application configuration object.

    Returns:
        Initialized VectorStore instance.
    """
    embedding_provider = get_embedding_provider(config.embedding)
    return VectorStore(
        config.get_vector_db_path(repo_path),
        embedding_provider,
        default_search_mode=config.search.default_search_mode,
        bm25_weight=config.search.bm25_weight,
    )


def _format_research_results(result: "DeepResearchResult") -> ResearchResult:
    """Format the research results for return.

    Args:
        result: The ResearchResult from the pipeline.

    Returns:
        Formatted dictionary ready for JSON serialization.
    """
    return {
        "question": result.question,
        "answer": result.answer,
        "sub_questions": [
            {"question": sq.question, "category": sq.category}
            for sq in result.sub_questions
        ],
        "sources": [
            {
                "file": src.file_path,
                "lines": f"{src.start_line}-{src.end_line}",
                "type": src.chunk_type,
                "name": src.name or "",
                "relevance": round(src.relevance_score, 3),
            }
            for src in result.sources
        ],
        "research_trace": [
            {
                "step": step.step_type.value,
                "description": step.description,
                "duration_ms": step.duration_ms,
            }
            for step in result.reasoning_trace
        ],
        "stats": {
            "chunks_analyzed": result.total_chunks_analyzed,
            "llm_calls": result.total_llm_calls,
        },
    }


def _is_test_file(file_path: str) -> bool:
    """Check if a file path looks like a test file.

    Delegates to :func:`local_deepwiki.core.path_utils.is_test_file`.
    """
    return is_test_file(file_path, check_filename=True)
