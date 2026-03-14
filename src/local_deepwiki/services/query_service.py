"""Query service: RAG pipeline and code search business logic.

Extracted from handlers/core.py handle_ask_question and handle_search_code.
RBAC permission checks and audit logging remain in the handler layer.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from local_deepwiki.config import Config
from local_deepwiki.core.rate_limiter import get_rate_limiter
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.logging import get_logger
from local_deepwiki.providers.base import LLMProvider

from .models import QueryResult, SourceEntry

logger = get_logger(__name__)


class QueryService:
    """Encapsulates the RAG query pipeline and code search.

    Uses dependency injection for VectorStore, LLMProvider, and Config
    rather than constructing them internally, making the service testable
    and explicit about its dependencies.
    """

    __slots__ = ("_vector_store", "_llm_provider", "_config")

    def __init__(
        self,
        vector_store: VectorStore,
        llm_provider: LLMProvider,
        config: Config,
    ) -> None:
        self._vector_store = vector_store
        self._llm_provider = llm_provider
        self._config = config

    async def answer_question(
        self,
        repo_path: Path,
        question: str,
        *,
        max_context: int = 10,
        agentic_rag: bool = False,
        wiki_path: Path | None = None,
        debug: bool = False,
    ) -> QueryResult:
        """Execute the full RAG pipeline: search -> [rerank] -> synthesize.

        Args:
            repo_path: Resolved path to the indexed repository.
            question: The user's natural-language question.
            max_context: Maximum code chunks for context.
            agentic_rag: Enable agentic RAG (grade relevance, rewrite query).
            wiki_path: Path to wiki directory (for wiki_resource URIs).
            debug: Include a RAGTrace in the result for pipeline debugging.

        Returns:
            QueryResult with the synthesized answer and source references.
        """
        from local_deepwiki.core.reranker import get_reranker
        from local_deepwiki.core.tracing import RAGTrace

        trace = RAGTrace(query=question) if debug else None
        agentic_metadata: dict[str, Any] | None = None

        # --- Retrieval ---
        reranker = get_reranker(self._config.search.reranker_model)
        # Over-fetch when reranking so the reranker has enough candidates
        fetch_limit = max_context * 2 if reranker else max_context

        t0 = time.monotonic()
        if agentic_rag:
            from local_deepwiki.core.agentic_rag import agentic_retrieve

            rag_result = await agentic_retrieve(
                question,
                self._vector_store,
                self._llm_provider,
                max_context=fetch_limit,
            )
            search_results = rag_result.results
            agentic_metadata = rag_result.metadata
            if trace:
                trace.agentic_rag_enabled = True
                trace.agentic_time_ms = (time.monotonic() - t0) * 1000
                if rag_result.metadata and rag_result.metadata.get("rewritten"):
                    trace.agentic_rewritten_query = rag_result.metadata.get(
                        "rewritten_query"
                    )
        else:
            search_results = await self._vector_store.search(
                question, limit=fetch_limit
            )

        # --- Graph expansion (optional) ---
        from local_deepwiki.services.graph_expansion import expand_with_graph

        search_results = await expand_with_graph(
            search_results, self._vector_store, self._config, repo_path
        )

        if trace:
            retrieval_ms = (time.monotonic() - t0) * 1000
            trace.record_retrieval(search_results, retrieval_ms)

        if not search_results:
            return QueryResult(
                answer="No relevant code found for your question.",
                sources=(),
                trace=trace.to_dict() if trace else None,
            )

        # --- Reranking (optional) ---
        if reranker and search_results:
            t1 = time.monotonic()
            search_results = await reranker.rerank(
                question, search_results, top_k=max_context
            )
            if trace:
                rerank_ms = (time.monotonic() - t1) * 1000
                trace.record_reranking(search_results, rerank_ms, reranker.model_name)
        else:
            search_results = search_results[:max_context]

        # --- Context construction ---
        context = _build_context(search_results)
        if trace:
            trace.record_context(len(search_results), len(context))

        prompt = (
            f"Question: {question}\n\n"
            f"Relevant source code:\n{context}\n\n"
            "Answer the question clearly and accurately. "
            "Reference specific files and line numbers when possible."
        )
        system_prompt = (
            "You are a knowledgeable assistant for this codebase. "
            "Answer questions as if you have read the entire repository. "
            "Never say 'the provided code' or 'the code context' — "
            "speak as if you naturally know the codebase."
        )

        # --- LLM generation ---
        t2 = time.monotonic()
        rate_limiter = get_rate_limiter()
        async with rate_limiter:
            answer = await self._llm_provider.generate(
                prompt, system_prompt=system_prompt
            )
        if trace:
            trace.record_llm((time.monotonic() - t2) * 1000)

        effective_wiki_path = wiki_path or self._config.get_wiki_path(repo_path)
        sources = _build_source_entries(search_results, effective_wiki_path)

        return QueryResult(
            answer=answer,
            sources=sources,
            agentic_metadata=agentic_metadata,
            trace=trace.to_dict() if trace else None,
        )

    async def search_code(
        self,
        repo_path: Path,
        query: str,
        *,
        limit: int = 20,
        language: str | None = None,
        chunk_type: str | None = None,
        path_filter: str | None = None,
        use_fuzzy: bool = False,
        fuzzy_weight: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Search code with optional filters.

        Args:
            repo_path: Resolved path to the indexed repository.
            query: Search query string.
            limit: Maximum results to return.
            language: Optional language filter.
            chunk_type: Optional chunk type filter.
            path_filter: Optional file path pattern filter.
            use_fuzzy: Enable fuzzy text matching.
            fuzzy_weight: Weight for fuzzy vs vector (0.0-1.0).

        Returns:
            List of result dicts with file_path, name, type, language,
            lines, score, preview, docstring, and optional highlights.
        """
        results = await self._vector_store.search(
            query,
            limit=limit,
            language=language,
            chunk_type=chunk_type,
            path_pattern=path_filter,
            use_fuzzy=use_fuzzy,
            fuzzy_weight=fuzzy_weight,
        )

        # --- Graph expansion (optional) ---
        from local_deepwiki.services.graph_expansion import expand_with_graph

        results = await expand_with_graph(
            results, self._vector_store, self._config, repo_path
        )

        if not results:
            return []

        output: list[dict[str, Any]] = []
        for r in results:
            chunk = r.chunk
            entry: dict[str, Any] = {
                "file_path": chunk.file_path,
                "name": chunk.name,
                "type": chunk.chunk_type.value,
                "language": chunk.language.value,
                "lines": f"{chunk.start_line}-{chunk.end_line}",
                "score": round(r.score, 4),
                "preview": (
                    chunk.content[:300] + "..."
                    if len(chunk.content) > 300
                    else chunk.content
                ),
                "docstring": chunk.docstring,
            }
            if r.highlights:
                entry["highlights"] = r.highlights
            output.append(entry)

        return output


def _build_context(search_results: list[Any]) -> str:
    """Build LLM context string from search results."""
    parts: list[str] = []
    for search_result in search_results:
        chunk = search_result.chunk
        parts.append(
            f"File: {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})\n"
            f"Type: {chunk.chunk_type.value}\n"
            f"```\n{chunk.content}\n```"
        )
    return "\n\n---\n\n".join(parts)


def _build_source_entries(
    search_results: list[Any],
    wiki_path: Path,
) -> tuple[SourceEntry, ...]:
    """Build immutable SourceEntry tuple from search results."""
    from local_deepwiki.handlers._response import build_wiki_resource_uri

    entries: list[SourceEntry] = []
    for r in search_results:
        wiki_resource: str | None = None
        file_wiki_page = f"files/{r.chunk.file_path}.md"
        if (wiki_path / file_wiki_page).exists():
            wiki_resource = build_wiki_resource_uri(wiki_path, file_wiki_page)

        entries.append(
            SourceEntry(
                file=r.chunk.file_path,
                lines=f"{r.chunk.start_line}-{r.chunk.end_line}",
                chunk_type=r.chunk.chunk_type.value,
                score=r.score,
                wiki_resource=wiki_resource,
            )
        )
    return tuple(entries)
