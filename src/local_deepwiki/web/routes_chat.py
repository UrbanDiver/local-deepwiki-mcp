"""Chat routes for the DeepWiki web UI.

Provides the /chat page and /api/chat SSE endpoint for RAG-based Q&A
over an indexed codebase.
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

from flask import Blueprint, Response, abort, jsonify, render_template, request

from local_deepwiki.errors import sanitize_error_message
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

chat_bp = Blueprint("chat", __name__)


from local_deepwiki.web.utils import get_wiki_path as _get_wiki_path


def stream_async_generator(
    async_gen_factory: Callable[[], AsyncIterator[str]],
) -> Iterator[str]:
    """Bridge an async generator to a sync generator using a queue.

    This allows streaming async results through Flask's synchronous response handling.

    Args:
        async_gen_factory: A callable that returns an async iterator.

    Yields:
        Items from the async generator.
    """
    result_queue: queue.Queue[str | None | Exception] = queue.Queue()

    def run_async() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:

            async def collect() -> None:
                try:
                    async for item in async_gen_factory():
                        result_queue.put(item)
                except Exception as e:  # noqa: BLE001 - Bridge arbitrary async errors to sync queue
                    result_queue.put(e)
                finally:
                    result_queue.put(None)  # Sentinel to signal completion

            loop.run_until_complete(collect())
        finally:
            loop.close()

    thread = threading.Thread(target=run_async)
    thread.start()

    while True:
        item = result_queue.get()
        if item is None:
            break
        if isinstance(item, Exception):
            logger.error("Error in async generator: %s", item)
            yield f"data: {json.dumps({'type': 'error', 'message': sanitize_error_message(str(item))})}\n\n"
            break
        yield item

    # Wait for thread to finish with timeout to avoid hanging
    thread.join(timeout=30.0)
    if thread.is_alive():
        logger.warning("Async generator thread did not finish within 30 seconds")


def format_sources(search_results: list[Any]) -> list[dict[str, Any]]:
    """Format search results as source citations.

    Args:
        search_results: List of SearchResult objects.

    Returns:
        List of source dictionaries with file, lines, type, and score.
    """
    sources = []
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


def build_prompt_with_history(
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
        return f"""Previous conversation:
{history_text}
Current question: {question}

Code context:
{context}

Answer the current question, taking into account the conversation history if relevant.
Provide a clear, accurate answer based on the code provided."""
    else:
        return f"""Question: {question}

Code context:
{context}

Provide a clear, accurate answer based on the code provided."""


@chat_bp.route("/chat")
def chat_page() -> Response | str:
    """Render the chat interface."""
    wiki_path = _get_wiki_path()
    if wiki_path is None:
        abort(500, "Wiki path not configured")

    # Check if wiki is indexed
    index_md = wiki_path / "index.md"
    if not index_md.exists():
        logger.info("Wiki not indexed yet, showing onboarding page")
        return render_template("onboarding.html", wiki_path=str(wiki_path.parent))

    return render_template("chat.html", wiki_path=str(wiki_path))


@chat_bp.route("/api/chat", methods=["POST"])
def api_chat() -> Response | tuple[Response, int]:
    """Handle chat Q&A with streaming response.

    Expects JSON body with:
        - question: The user's question
        - history: Optional list of previous Q&A exchanges

    Returns:
        Server-Sent Events stream with tokens and sources.
    """
    wiki_path = _get_wiki_path()
    if wiki_path is None:
        return jsonify({"error": "Wiki path not configured"}), 500

    data = request.get_json() or {}
    question = data.get("question", "").strip()
    history = data.get("history", [])

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

    async def generate_response() -> AsyncIterator[str]:
        """Async generator that streams the chat response."""
        from local_deepwiki.config import get_config
        from local_deepwiki.core.vectorstore import VectorStore
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

        # Determine LLM config for chat - use chat_llm_provider if set
        llm_config = config.llm
        chat_provider = config.wiki.chat_llm_provider
        if chat_provider != "default":
            # Override provider for chat
            llm_config = llm_config.model_copy(update={"provider": chat_provider})
            logger.info("Using %s provider for chat", chat_provider)

        llm = get_cached_llm_provider(
            cache_path=cache_path,
            embedding_provider=embedding_provider,
            cache_config=config.llm_cache,
            llm_config=llm_config,
        )

        # Search for relevant context
        search_results = await vector_store.search(question, limit=5)

        # Send sources first
        sources = format_sources(search_results)
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        if not search_results:
            yield f"data: {json.dumps({'type': 'token', 'content': 'No relevant code found for your question.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Build context from search results
        context_parts = []
        for result in search_results:
            chunk = result.chunk
            context_parts.append(
                f"File: {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})\n"
                f"Type: {chunk.chunk_type.value}\n"
                f"```\n{chunk.content}\n```"
            )
        context = "\n\n---\n\n".join(context_parts)

        # Build prompt with history
        prompt = build_prompt_with_history(question, history, context)
        system_prompt = (
            "You are a helpful code assistant. Answer questions about code clearly and accurately. "
            "Reference specific files and line numbers when relevant."
        )

        # Stream the response
        try:
            async for text_chunk in llm.generate_stream(
                prompt, system_prompt=system_prompt, temperature=0.3
            ):
                yield f"data: {json.dumps({'type': 'token', 'content': text_chunk})}\n\n"
        except Exception as e:  # noqa: BLE001 - Report LLM errors to user via SSE
            logger.exception("Error generating response: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': sanitize_error_message(str(e))})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(
        stream_async_generator(generate_response),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
