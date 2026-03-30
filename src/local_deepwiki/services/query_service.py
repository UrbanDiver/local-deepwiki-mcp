"""Query service: RAG pipeline and code search business logic.

Extracted from handlers/core.py handle_ask_question and handle_search_code.
RBAC permission checks and audit logging remain in the handler layer.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from local_deepwiki.config import Config
from local_deepwiki.core.rate_limiter import get_rate_limiter
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.errors import sanitize_error_message
from local_deepwiki.logging import get_logger
from local_deepwiki.providers.base import LLMProvider

from .models import QueryResult, SourceEntry

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class QuestionRequest:
    """Immutable parameters for the RAG question-answering pipeline."""

    repo_path: Path
    question: str
    max_context: int = 10
    agentic_rag: bool = False
    wiki_path: Path | None = None
    debug: bool = False


@dataclass(frozen=True, slots=True)
class CodeSearchRequest:
    """Immutable parameters for code search."""

    repo_path: Path
    query: str
    limit: int = 20
    language: str | None = None
    chunk_type: str | None = None
    path_filter: str | None = None
    use_fuzzy: bool = False
    fuzzy_weight: float = 0.3


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

    async def _retrieve_agentic(
        self,
        question: str,
        fetch_limit: int,
        trace: Any,
        t0: float,
    ) -> tuple[list[Any], dict[str, Any] | None]:
        """Run agentic RAG retrieval; return (search_results, agentic_metadata)."""
        from local_deepwiki.core.agentic_rag import agentic_retrieve

        rag_result = await agentic_retrieve(
            question,
            self._vector_store,
            self._llm_provider,
            max_context=fetch_limit,
        )
        if trace:
            trace.agentic_rag_enabled = True
            trace.agentic_time_ms = (time.monotonic() - t0) * 1000
            if rag_result.metadata and rag_result.metadata.get("rewritten"):
                trace.agentic_rewritten_query = rag_result.metadata.get(
                    "rewritten_query"
                )
        return rag_result.results, rag_result.metadata

    async def _retrieve_standard(self, question: str, fetch_limit: int) -> list[Any]:
        """Run standard (query-preprocessed) vector search retrieval."""
        from local_deepwiki.core.query_utils import condense_query, expand_project_terms

        search_query = condense_query(question)
        search_query = expand_project_terms(search_query)
        return await self._vector_store.search(
            search_query,
            limit=fetch_limit,
            use_fuzzy=True,
            fuzzy_weight=0.3,
        )

    async def _rerank_results(
        self,
        reranker: Any,
        question: str,
        search_results: list[Any],
        max_context: int,
        trace: Any,
    ) -> list[Any]:
        """Apply reranking if a reranker is available; otherwise truncate."""
        if reranker and search_results:
            t1 = time.monotonic()
            reranked = await reranker.rerank(
                question, search_results, top_k=max_context
            )
            if trace:
                rerank_ms = (time.monotonic() - t1) * 1000
                trace.record_reranking(reranked, rerank_ms, reranker.model_name)
            return reranked
        return search_results[:max_context]

    async def _retrieve_and_expand(
        self,
        question: str,
        repo_path: Path,
        fetch_limit: int,
        agentic_rag: bool,
        trace: Any,
        t0: float,
    ) -> tuple[list[Any], dict[str, Any] | None]:
        """Run retrieval (standard or agentic) then graph expansion.

        Returns (search_results, agentic_metadata).
        """
        from local_deepwiki.services.graph_expansion import expand_with_graph

        agentic_metadata: dict[str, Any] | None = None
        if agentic_rag:
            search_results, agentic_metadata = await self._retrieve_agentic(
                question, fetch_limit, trace, t0
            )
        else:
            search_results = await self._retrieve_standard(question, fetch_limit)

        search_results = await expand_with_graph(
            search_results, self._vector_store, self._config, repo_path
        )
        if trace:
            trace.record_retrieval(search_results, (time.monotonic() - t0) * 1000)
        return search_results, agentic_metadata

    async def _generate_answer(
        self,
        question: str,
        search_results: list[Any],
        trace: Any,
    ) -> str:
        """Build context, construct prompt, and call the LLM."""
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
        t2 = time.monotonic()
        rate_limiter = get_rate_limiter()
        async with rate_limiter:
            answer = await self._llm_provider.generate(
                prompt, system_prompt=system_prompt
            )
        if trace:
            trace.record_llm((time.monotonic() - t2) * 1000)
        return answer

    async def answer_question(
        self,
        request: QuestionRequest,
    ) -> QueryResult:
        """Execute the full RAG pipeline: search -> [rerank] -> synthesize.

        Args:
            request: Immutable request containing repo path, question,
                max context, agentic RAG toggle, wiki path, and debug flag.

        Returns:
            QueryResult with the synthesized answer and source references.
        """
        from local_deepwiki.core.reranker import get_reranker
        from local_deepwiki.core.tracing import RAGTrace

        trace = RAGTrace(query=request.question) if request.debug else None

        reranker = get_reranker(self._config.search.reranker_model)
        fetch_limit = request.max_context * 2 if reranker else request.max_context

        t0 = time.monotonic()
        search_results, agentic_metadata = await self._retrieve_and_expand(
            request.question,
            request.repo_path,
            fetch_limit,
            request.agentic_rag,
            trace,
            t0,
        )

        if not search_results:
            return QueryResult(
                answer="No relevant code found for your question.",
                sources=(),
                trace=trace.to_dict() if trace else None,
            )

        search_results = await self._rerank_results(
            reranker, request.question, search_results, request.max_context, trace
        )

        answer = await self._generate_answer(request.question, search_results, trace)

        effective_wiki_path = request.wiki_path or self._config.get_wiki_path(
            request.repo_path
        )
        sources = _build_source_entries(search_results, effective_wiki_path)

        return QueryResult(
            answer=answer,
            sources=sources,
            agentic_metadata=agentic_metadata,
            trace=trace.to_dict() if trace else None,
        )

    async def answer_question_stream(
        self,
        repo_path: Path,
        question: str,
        *,
        max_context: int = 15,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream RAG results: sources -> tokens -> done.

        Yields dicts suitable for SSE serialization:
            {"type": "sources", "sources": [...]}
            {"type": "token", "content": "..."}  (one per LLM chunk)
            {"type": "done"}
            {"type": "error", "message": "..."}  (on failure)

        Args:
            repo_path: Resolved path to the indexed repository.
            question: The user's natural-language question.
            max_context: Maximum code chunks for context.
            history: Optional conversation history for follow-up questions.
        """
        # --- Retrieval ---
        search_results = await self._vector_store.search(question, limit=max_context)

        # Yield sources first (even if empty)
        sources = _format_sources_for_stream(search_results)
        yield {"type": "sources", "sources": sources}

        if not search_results:
            yield {
                "type": "token",
                "content": "No relevant code found for your question.",
            }
            yield {"type": "done"}
            return

        # --- Context construction ---
        context = _build_context(search_results)

        # --- Prompt construction (with optional history) ---
        prompt = _build_prompt_with_history(question, history or [], context)
        system_prompt = (
            "You are a knowledgeable assistant for this codebase. "
            "Answer questions as if you have read the entire repository. "
            "Never say 'the provided code' or 'the code context' — "
            "speak as if you naturally know the codebase. "
            "Reference specific files and line numbers when relevant."
        )

        # --- LLM streaming ---
        try:
            async for text_chunk in self._llm_provider.generate_stream(
                prompt, system_prompt=system_prompt, temperature=0.3
            ):
                yield {"type": "token", "content": text_chunk}
        except Exception as e:  # noqa: BLE001 - Report LLM errors to user via stream
            logger.exception("Error during streaming generation: %s", e)
            yield {
                "type": "error",
                "message": sanitize_error_message(str(e)),
            }

        yield {"type": "done"}

    async def search_code(
        self,
        request: CodeSearchRequest,
    ) -> list[dict[str, Any]]:
        """Search code with optional filters.

        Args:
            request: Immutable request containing repo path, query,
                limit, language, chunk type, path filter, fuzzy settings.

        Returns:
            List of result dicts with file_path, name, type, language,
            lines, score, preview, docstring, and optional highlights.
        """
        results = await self._vector_store.search(
            request.query,
            limit=request.limit,
            language=request.language,
            chunk_type=request.chunk_type,
            path_pattern=request.path_filter,
            use_fuzzy=request.use_fuzzy,
            fuzzy_weight=request.fuzzy_weight,
        )

        # --- Graph expansion (optional) ---
        from local_deepwiki.services.graph_expansion import expand_with_graph

        results = await expand_with_graph(
            results, self._vector_store, self._config, request.repo_path
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


def _format_sources_for_stream(search_results: list[Any]) -> list[dict[str, Any]]:
    """Format search results as source citations for streaming.

    Returns a JSON-serializable list (not frozen dataclasses) suitable
    for direct inclusion in SSE payloads.
    """
    sources: list[dict[str, Any]] = []
    for r in search_results:
        chunk = r.chunk
        sources.append(
            {
                "file": chunk.file_path,
                "lines": f"{chunk.start_line}-{chunk.end_line}",
                "type": chunk.chunk_type.value,
                "name": chunk.name,
                "score": round(r.score, 3),
            }
        )
    return sources


def _build_prompt_with_history(
    question: str, history: list[dict[str, str]], context: str
) -> str:
    """Build a prompt that includes conversation history for follow-up questions.

    Args:
        question: The current question.
        history: Previous Q&A exchanges.
        context: Code context from search results.

    Returns:
        A prompt string with history and context.
    """
    history_text = ""
    # Include last 3 exchanges for context
    for exchange in history[-3:]:
        history_text += f"User: {exchange.get('question', '')}\n"
        history_text += f"Assistant: {exchange.get('answer', '')}\n\n"

    if history_text:
        return (
            f"Previous conversation:\n{history_text}\n"
            f"Current question: {question}\n\n"
            f"Relevant source code:\n{context}\n\n"
            "Answer the current question, taking into account the "
            "conversation history if relevant.\n"
            "Reference specific files and line numbers when possible."
        )
    return (
        f"Question: {question}\n\n"
        f"Relevant source code:\n{context}\n\n"
        "Answer the question clearly and accurately.\n"
        "Reference specific files and line numbers when possible."
    )
