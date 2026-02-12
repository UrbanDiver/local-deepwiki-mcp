"""Research routes for the DeepWiki web UI.

Provides the /api/research SSE endpoint for deep, multi-step research
queries over an indexed codebase.
"""

from __future__ import annotations

import asyncio
import json
import queue
from typing import Any, AsyncIterator

from flask import Blueprint, Response, jsonify, request

from local_deepwiki.errors import sanitize_error_message
from local_deepwiki.logging import get_logger
from local_deepwiki.web.routes_chat import stream_async_generator

logger = get_logger(__name__)

research_bp = Blueprint("research", __name__)


def _get_wiki_path():
    """Retrieve the current WIKI_PATH from the main app module."""
    from local_deepwiki.web import app as _app_module

    return _app_module.WIKI_PATH


@research_bp.route("/api/research", methods=["POST"])
def api_research():
    """Handle deep research with streaming progress updates.

    Expects JSON body with:
        - question: The user's question

    Returns:
        Server-Sent Events stream with progress updates and final result.
    """
    wiki_path = _get_wiki_path()
    if wiki_path is None:
        return jsonify({"error": "Wiki path not configured"}), 500

    data = request.get_json() or {}
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"error": "Question is required"}), 400

    if len(question) > 5000:
        return jsonify(
            {"error": "Question exceeds maximum length (5000 characters)"}
        ), 400

    # Determine the repository path from wiki path
    repo_path = wiki_path.parent
    if wiki_path.name == ".deepwiki":
        repo_path = wiki_path.parent

    # Queue for progress updates from async callback
    progress_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()

    async def run_research() -> AsyncIterator[str]:
        """Async generator that runs deep research with progress updates."""
        from local_deepwiki.config import get_config
        from local_deepwiki.core.deep_research import DeepResearchPipeline
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.models import ResearchProgress
        from local_deepwiki.providers.embeddings import get_embedding_provider
        from local_deepwiki.providers.llm import get_cached_llm_provider

        config = get_config()
        vector_db_path = config.get_vector_db_path(repo_path)

        if not vector_db_path.exists():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Repository not indexed. Please run index_repository first.'})}\n\n"
            return

        # Setup providers
        embedding_provider = get_embedding_provider(config.embedding)
        vector_store = VectorStore(vector_db_path, embedding_provider)
        cache_path = config.get_wiki_path(repo_path) / "llm_cache.lance"

        # Determine LLM config for research - use chat_llm_provider if set
        llm_config = config.llm
        chat_provider = config.wiki.chat_llm_provider
        if chat_provider != "default":
            # Override provider for research
            llm_config = llm_config.model_copy(update={"provider": chat_provider})
            logger.info("Using %s provider for deep research", chat_provider)

        llm = get_cached_llm_provider(
            cache_path=cache_path,
            embedding_provider=embedding_provider,
            cache_config=config.llm_cache,
            llm_config=llm_config,
        )

        # Progress callback
        async def on_progress(progress: ResearchProgress) -> None:
            progress_data: dict[str, Any] = {
                "type": "progress",
                "step": progress.step,
                "total_steps": progress.total_steps,
                "step_type": progress.step_type.value,
                "message": progress.message,
            }
            if progress.sub_questions:
                progress_data["sub_questions"] = [
                    {"question": sq.question, "category": sq.category}
                    for sq in progress.sub_questions
                ]
            if progress.chunks_retrieved is not None:
                progress_data["chunks_retrieved"] = progress.chunks_retrieved
            if progress.follow_up_queries:
                progress_data["follow_up_queries"] = progress.follow_up_queries
            if progress.duration_ms is not None:
                progress_data["duration_ms"] = progress.duration_ms

            # Put in queue for the main generator to pick up
            progress_queue.put(progress_data)

        # Create pipeline with config parameters
        dr_config = config.deep_research
        pipeline = DeepResearchPipeline(
            vector_store=vector_store,
            llm_provider=llm,
            max_sub_questions=dr_config.max_sub_questions,
            chunks_per_subquestion=dr_config.chunks_per_subquestion,
            max_total_chunks=dr_config.max_total_chunks,
            max_follow_up_queries=dr_config.max_follow_up_queries,
            synthesis_temperature=dr_config.synthesis_temperature,
            synthesis_max_tokens=dr_config.synthesis_max_tokens,
        )

        # Run research in background, yielding progress as it comes
        research_task = asyncio.create_task(
            pipeline.research(question, progress_callback=on_progress)
        )

        # Yield progress updates as they come in
        while not research_task.done():
            try:
                progress_data = progress_queue.get(timeout=0.1)
                if progress_data is not None:
                    yield f"data: {json.dumps(progress_data)}\n\n"
            except queue.Empty:
                await asyncio.sleep(0.05)

        # Drain any remaining progress updates
        while not progress_queue.empty():
            progress_data = progress_queue.get_nowait()
            if progress_data is not None:
                yield f"data: {json.dumps(progress_data)}\n\n"

        try:
            result = await research_task

            # Format the result
            response = {
                "type": "result",
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
                        "name": src.name,
                        "relevance": round(src.relevance_score, 3),
                    }
                    for src in result.sources
                ],
                "reasoning_trace": [
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
            yield f"data: {json.dumps(response)}\n\n"
        except Exception as e:  # noqa: BLE001 - Report research errors to user via SSE
            logger.exception("Error in deep research: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': sanitize_error_message(str(e))})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(
        stream_async_generator(run_research),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
