"""Research routes for the DeepWiki web UI.

Provides the /api/research SSE endpoint for deep, multi-step research
queries over an indexed codebase.
"""

from __future__ import annotations

import asyncio
import json
import queue
from collections.abc import AsyncIterator
from typing import Any

from flask import Blueprint, Response, jsonify, request

from local_deepwiki.errors import sanitize_error_message
from local_deepwiki.logging import get_logger
from local_deepwiki.web.routes_chat import stream_async_generator

logger = get_logger(__name__)

research_bp = Blueprint("research", __name__)


from local_deepwiki.web.utils import get_wiki_path as _get_wiki_path


def _build_progress_data(progress: Any) -> dict[str, Any]:
    """Build the SSE progress payload from a ResearchProgress object."""
    data: dict[str, Any] = {
        "type": "progress",
        "step": progress.step,
        "total_steps": progress.total_steps,
        "step_type": progress.step_type.value,
        "message": progress.message,
    }
    if progress.sub_questions:
        data["sub_questions"] = [
            {"question": sq.question, "category": sq.category}
            for sq in progress.sub_questions
        ]
    if progress.chunks_retrieved is not None:
        data["chunks_retrieved"] = progress.chunks_retrieved
    if progress.follow_up_queries:
        data["follow_up_queries"] = progress.follow_up_queries
    if progress.duration_ms is not None:
        data["duration_ms"] = progress.duration_ms
    return data


def _build_research_result(result: Any) -> dict[str, Any]:
    """Build the SSE result payload from a completed research result."""
    return {
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


async def _drain_progress_queue(
    progress_queue: "queue.Queue[dict[str, Any] | None]",
) -> AsyncIterator[str]:
    """Yield SSE strings for all items remaining in the progress queue."""
    while not progress_queue.empty():
        item = progress_queue.get_nowait()
        if item is not None:
            yield f"data: {json.dumps(item)}\n\n"


async def _research_stream_generator(
    repo_path: Any,
    question: str,
    progress_queue: "queue.Queue[dict[str, Any] | None]",
) -> AsyncIterator[str]:
    """Async generator that runs deep research with SSE progress updates."""
    from local_deepwiki.core.deep_research import DeepResearchPipeline
    from local_deepwiki.web.utils import create_providers

    providers = create_providers(repo_path)
    vector_db_path = providers.config.get_vector_db_path(repo_path)

    if not vector_db_path.exists():
        yield f"data: {json.dumps({'type': 'error', 'message': 'Repository not indexed. Please run index_repository first.'})}\n\n"
        return

    async def on_progress(progress: Any) -> None:
        progress_queue.put(_build_progress_data(progress))

    from local_deepwiki.core.deep_research.config import ResearchConfig

    dr_config = providers.config.deep_research
    pipeline = DeepResearchPipeline(
        vector_store=providers.vector_store,
        llm_provider=providers.llm,
        config=ResearchConfig(
            max_sub_questions=dr_config.max_sub_questions,
            chunks_per_subquestion=dr_config.chunks_per_subquestion,
            max_total_chunks=dr_config.max_total_chunks,
            max_follow_up_queries=dr_config.max_follow_up_queries,
            synthesis_temperature=dr_config.synthesis_temperature,
            synthesis_max_tokens=dr_config.synthesis_max_tokens,
        ),
    )

    research_task = asyncio.create_task(
        pipeline.research(question, progress_callback=on_progress)
    )

    while not research_task.done():
        try:
            item = progress_queue.get(timeout=0.1)
            if item is not None:
                yield f"data: {json.dumps(item)}\n\n"
        except queue.Empty:
            await asyncio.sleep(0.05)

    async for sse in _drain_progress_queue(progress_queue):
        yield sse

    try:
        result = await research_task
        yield f"data: {json.dumps(_build_research_result(result))}\n\n"
    except Exception as e:  # noqa: BLE001 - Report research errors to user via SSE
        logger.exception("Error in deep research: %s", e)
        yield f"data: {json.dumps({'type': 'error', 'message': sanitize_error_message(str(e))})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@research_bp.route("/api/research", methods=["POST"])
def api_research() -> Response | tuple[Response, int]:
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

    repo_path = wiki_path.parent

    progress_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def run_research() -> AsyncIterator[str]:
        return _research_stream_generator(repo_path, question, progress_queue)

    return Response(
        stream_async_generator(run_research),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
