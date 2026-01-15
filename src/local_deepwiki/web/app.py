"""Simple Flask web UI for browsing DeepWiki documentation.

Uses Jinja2 template files with automatic caching for production performance.
Templates are loaded from the 'templates' subdirectory relative to this module.
"""

import asyncio
import json
import queue
import threading
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Iterator

import markdown
from flask import Flask, Response, abort, jsonify, redirect, render_template, request, url_for

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# Get the directory containing this module for template path resolution
_MODULE_DIR = Path(__file__).parent

# Create Flask app with explicit template folder
# Flask caches compiled templates when debug=False (the default)
app = Flask(__name__, template_folder=str(_MODULE_DIR / "templates"))

# Default wiki path - can be overridden
WIKI_PATH: Path | None = None


def get_wiki_structure(wiki_path: Path) -> tuple[list, dict, list | None]:
    """Get wiki pages and sections, with optional hierarchical TOC.

    Returns:
        Tuple of (pages, sections, toc_entries) where toc_entries is the
        hierarchical numbered TOC if toc.json exists, None otherwise.
    """
    pages = []
    sections = {}
    toc_entries = None

    # Try to load toc.json for hierarchical numbered structure
    toc_path = wiki_path / "toc.json"
    if toc_path.exists():
        try:
            toc_data = json.loads(toc_path.read_text())
            toc_entries = toc_data.get("entries", [])
        except (json.JSONDecodeError, OSError):
            pass  # Fall back to flat structure

    # Get root pages
    for md_file in sorted(wiki_path.glob("*.md")):
        title = extract_title(md_file)
        pages.append({"path": md_file.name, "title": title})

    # Get section pages (used as fallback if no toc.json)
    for section_dir in sorted(wiki_path.iterdir()):
        if section_dir.is_dir() and not section_dir.name.startswith("."):
            section_pages = []
            for md_file in sorted(section_dir.glob("*.md")):
                title = extract_title(md_file)
                section_pages.append({"path": f"{section_dir.name}/{md_file.name}", "title": title})
            if section_pages:
                sections[section_dir.name.replace("_", " ").title()] = section_pages

    return pages, sections, toc_entries


def extract_title(md_file: Path) -> str:
    """Extract title from markdown file."""
    try:
        content = md_file.read_text()
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            if line.startswith("**") and line.endswith("**"):
                return line[2:-2].strip()
    except (OSError, UnicodeDecodeError) as e:
        logger.debug(f"Could not extract title from {md_file}: {e}")
    return md_file.stem.replace("_", " ").replace("-", " ").title()


def render_markdown(content: str) -> str:
    """Render markdown to HTML."""
    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "nl2br",
        ]
    )
    return md.convert(content)


def build_breadcrumb(wiki_path: Path, current_path: str) -> str:
    """Build breadcrumb navigation HTML with clickable links.

    For a path like 'files/src/local_deepwiki/core/chunker.md', generates:
    Home > Files > src > local_deepwiki > core > chunker

    Each segment links to its index.md if one exists in that folder.
    """
    parts = current_path.split("/")

    # Root pages don't need breadcrumbs (or just show Home)
    if len(parts) == 1:
        return ""

    breadcrumb_items = []

    # Always start with Home
    breadcrumb_items.append('<a href="/">Home</a>')

    # Build path progressively and check for index.md at each level
    cumulative_path = ""
    for part in parts[:-1]:  # Exclude the current page
        if cumulative_path:
            cumulative_path = f"{cumulative_path}/{part}"
        else:
            cumulative_path = part

        # Check if there's an index.md in this folder
        index_path = wiki_path / cumulative_path / "index.md"
        display_name = part.replace("_", " ").replace("-", " ").title()

        if index_path.exists():
            link_path = f"{cumulative_path}/index.md"
            breadcrumb_items.append(f'<a href="/wiki/{link_path}">{display_name}</a>')
        else:
            # No index.md, just show as text
            breadcrumb_items.append(f"<span>{display_name}</span>")

    # Add current page name (no link, it's the current page)
    current_page = parts[-1]
    if current_page.endswith(".md"):
        current_page = current_page[:-3]
    current_page = current_page.replace("_", " ").replace("-", " ").title()
    breadcrumb_items.append(f'<span class="current">{current_page}</span>')

    return ' <span class="separator">›</span> '.join(breadcrumb_items)


@app.route("/")
def index():
    """Redirect to index.md."""
    logger.debug("Redirecting / to index.md")
    return redirect(url_for("view_page", path="index.md"))


@app.route("/search.json")
def search_json():
    """Serve the search index JSON file."""
    if WIKI_PATH is None:
        abort(500, "Wiki path not configured")

    search_path = WIKI_PATH / "search.json"
    if not search_path.exists():
        # Return empty index if not generated yet
        return jsonify([])

    try:
        data = json.loads(search_path.read_text())
        return jsonify(data)
    except (json.JSONDecodeError, OSError) as e:
        abort(500, f"Error reading search index: {e}")


@app.route("/wiki/<path:path>")
def view_page(path: str):
    """View a wiki page."""
    logger.debug(f"Viewing page: {path}")

    if WIKI_PATH is None:
        logger.error("Wiki path not configured")
        abort(500, "Wiki path not configured")

    file_path = WIKI_PATH / path
    if not file_path.exists() or not file_path.is_file():
        logger.warning(f"Page not found: {path}")
        abort(404, f"Page not found: {path}")

    try:
        content = file_path.read_text()
        html_content = render_markdown(content)
    except (OSError, UnicodeDecodeError) as e:
        abort(500, f"Error reading page: {e}")

    pages, sections, toc_entries = get_wiki_structure(WIKI_PATH)
    title = extract_title(file_path)

    # Build breadcrumb navigation
    breadcrumb = build_breadcrumb(WIKI_PATH, path)

    return render_template(
        "page.html",
        content=html_content,
        title=title,
        pages=pages,
        sections=sections,
        toc_entries=toc_entries,
        current_path=path,
        breadcrumb=breadcrumb,
    )


def stream_async_generator(async_gen_factory: Callable[[], AsyncIterator[str]]) -> Iterator[str]:
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
            logger.error(f"Error in async generator: {item}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(item)})}\n\n"
            break
        yield item

    thread.join()


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
        sources.append({
            "file": chunk.file_path,
            "lines": f"{chunk.start_line}-{chunk.end_line}",
            "type": chunk.chunk_type.value,
            "name": chunk.name,
            "score": round(r.score, 3),
        })
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


@app.route("/chat")
def chat_page():
    """Render the chat interface."""
    if WIKI_PATH is None:
        abort(500, "Wiki path not configured")
    return render_template("chat.html", wiki_path=str(WIKI_PATH))


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Handle chat Q&A with streaming response.

    Expects JSON body with:
        - question: The user's question
        - history: Optional list of previous Q&A exchanges

    Returns:
        Server-Sent Events stream with tokens and sources.
    """
    if WIKI_PATH is None:
        return jsonify({"error": "Wiki path not configured"}), 500

    data = request.get_json() or {}
    question = data.get("question", "").strip()
    history = data.get("history", [])

    if not question:
        return jsonify({"error": "Question is required"}), 400

    # Determine the repository path from wiki path
    repo_path = WIKI_PATH.parent
    if WIKI_PATH.name == ".deepwiki":
        repo_path = WIKI_PATH.parent

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
            logger.info(f"Using {chat_provider} provider for chat")

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
            async for chunk in llm.generate_stream(
                prompt, system_prompt=system_prompt, temperature=0.3
            ):
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
        except Exception as e:  # noqa: BLE001 - Report LLM errors to user via SSE
            logger.exception(f"Error generating response: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(
        stream_async_generator(generate_response),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/research", methods=["POST"])
def api_research():
    """Handle deep research with streaming progress updates.

    Expects JSON body with:
        - question: The user's question

    Returns:
        Server-Sent Events stream with progress updates and final result.
    """
    if WIKI_PATH is None:
        return jsonify({"error": "Wiki path not configured"}), 500

    data = request.get_json() or {}
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"error": "Question is required"}), 400

    # Determine the repository path from wiki path
    repo_path = WIKI_PATH.parent
    if WIKI_PATH.name == ".deepwiki":
        repo_path = WIKI_PATH.parent

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
            logger.info(f"Using {chat_provider} provider for deep research")

        llm = get_cached_llm_provider(
            cache_path=cache_path,
            embedding_provider=embedding_provider,
            cache_config=config.llm_cache,
            llm_config=llm_config,
        )

        # Progress callback
        async def on_progress(progress: ResearchProgress) -> None:
            progress_data = {
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
            logger.exception(f"Error in deep research: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(
        stream_async_generator(run_research),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def create_app(wiki_path: str | Path) -> Flask:
    """Create Flask app with wiki path configured."""
    global WIKI_PATH
    WIKI_PATH = Path(wiki_path)
    if not WIKI_PATH.exists():
        logger.error(f"Wiki path does not exist: {wiki_path}")
        raise ValueError(f"Wiki path does not exist: {wiki_path}")
    logger.info(f"Configured wiki path: {WIKI_PATH}")
    return app


def run_server(
    wiki_path: str | Path, host: str = "127.0.0.1", port: int = 8080, debug: bool = False
):
    """Run the wiki web server."""
    app = create_app(wiki_path)
    logger.info(f"Starting DeepWiki server at http://{host}:{port}")
    logger.info(f"Serving wiki from: {wiki_path}")
    print(f"Starting DeepWiki server at http://{host}:{port}")
    print(f"Serving wiki from: {wiki_path}")
    app.run(host=host, port=port, debug=debug)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Serve DeepWiki documentation")
    parser.add_argument(
        "wiki_path", nargs="?", default=".deepwiki", help="Path to the .deepwiki directory"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    wiki_path = Path(args.wiki_path).resolve()
    run_server(wiki_path, args.host, args.port, args.debug)


if __name__ == "__main__":
    main()
