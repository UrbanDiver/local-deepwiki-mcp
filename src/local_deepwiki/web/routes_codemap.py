"""Codemap routes for the DeepWiki web UI.

Provides the interactive codemap visualization page, codemap generation API,
topic suggestions, persistent cache browsing, git diff overlay, and
side-by-side comparison view.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from collections.abc import AsyncIterator

from flask import Blueprint, Response, abort, jsonify, render_template, request

from local_deepwiki.errors import sanitize_error_message
from local_deepwiki.generators.codemap.cache import (
    cache_key,
    list_cached_codemaps,
    read_cache,
    write_cache,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.web.routes_chat import stream_async_generator

logger = get_logger(__name__)

codemap_bp = Blueprint("codemap", __name__)


from local_deepwiki.web.utils import get_wiki_path as _get_wiki_path


@codemap_bp.route("/codemap")
def codemap_page() -> Response | str:
    """Render the interactive codemap visualization page."""
    wiki_path = _get_wiki_path()
    if wiki_path is None:
        abort(500, "Wiki path not configured")

    # Check if wiki is indexed
    index_md = wiki_path / "index.md"
    if not index_md.exists():
        logger.info("Wiki not indexed yet, showing onboarding page")
        return render_template("onboarding.html", wiki_path=str(wiki_path.parent))

    return render_template("codemap.html", wiki_path=str(wiki_path))


@codemap_bp.route("/api/codemap/topics")
def api_codemap_topics() -> Response | tuple[Response, int]:
    """Return suggested codemap topics as JSON.

    Calls suggest_topics() from the codemap generator using the indexed
    repository's call graph hubs.

    Returns:
        JSON array of topic suggestions, or empty array on error.
    """
    wiki_path = _get_wiki_path()
    if wiki_path is None:
        return jsonify({"error": "Wiki path not configured"}), 500

    repo_path = wiki_path.parent
    if wiki_path.name == ".deepwiki":
        repo_path = wiki_path.parent

    async def _fetch_topics() -> list[dict]:
        from local_deepwiki.config import get_config
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.generators.codemap import suggest_topics
        from local_deepwiki.providers.embeddings import get_embedding_provider

        config = get_config()
        vector_db_path = config.get_vector_db_path(repo_path)

        if not vector_db_path.exists():
            return []

        embedding_provider = get_embedding_provider(config.embedding)
        vector_store = VectorStore(vector_db_path, embedding_provider)

        try:
            return await suggest_topics(vector_store, repo_path)
        except Exception:  # noqa: BLE001 - Graceful degradation for topic suggestions
            logger.exception("Failed to generate codemap topics")
            return []

    loop = asyncio.new_event_loop()
    try:
        topics = loop.run_until_complete(_fetch_topics())
    finally:
        loop.close()

    return jsonify(topics)


@codemap_bp.route("/api/codemap", methods=["POST"])
def api_codemap() -> Response | tuple[Response, int]:
    """Handle codemap generation with streaming response.

    Expects JSON body with:
        - query: The codemap query (required)
        - focus: Focus mode - execution_flow, data_flow, dependency_chain (default: execution_flow)
        - entry_point: Optional specific entry point function name
        - max_depth: Max traversal depth 1-10 (default: 5)
        - max_nodes: Max nodes 5-60 (default: 30)

    Returns:
        Server-Sent Events stream with progress, result, and done events.
    """
    wiki_path = _get_wiki_path()
    if wiki_path is None:
        return jsonify({"error": "Wiki path not configured"}), 500

    data = request.get_json() or {}
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "Query is required"}), 400

    if len(query) > 5000:
        return jsonify({"error": "Query exceeds maximum length (5000 characters)"}), 400

    focus = data.get("focus", "execution_flow")
    valid_focus = frozenset({"execution_flow", "data_flow", "dependency_chain"})
    if focus not in valid_focus:
        return jsonify(
            {
                "error": f"Invalid focus mode. Must be one of: {', '.join(sorted(valid_focus))}"
            }
        ), 400

    max_depth = data.get("max_depth", 5)
    if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 10:
        return jsonify({"error": "max_depth must be an integer between 1 and 10"}), 400

    max_nodes = data.get("max_nodes", 30)
    if not isinstance(max_nodes, int) or max_nodes < 5 or max_nodes > 60:
        return jsonify({"error": "max_nodes must be an integer between 5 and 60"}), 400

    entry_point = data.get("entry_point")
    if entry_point is not None:
        if not isinstance(entry_point, str):
            return jsonify({"error": "entry_point must be a string"}), 400
        if len(entry_point) > 500:
            return jsonify(
                {"error": "entry_point exceeds maximum length (500 characters)"}
            ), 400
        # Allow alphanumeric, dots, underscores, colons, slashes (typical qualified names)
        if not re.match(r"^[\w.:/ -]+$", entry_point):
            return jsonify({"error": "entry_point contains invalid characters"}), 400

    repo_path = wiki_path.parent
    if wiki_path.name == ".deepwiki":
        repo_path = wiki_path.parent

    # Check cache first
    cache_k = cache_key(query, focus, max_depth, max_nodes)

    async def generate_codemap_stream() -> AsyncIterator[str]:
        """Async generator that streams codemap generation progress and result."""
        # Try cache hit
        cached = read_cache(wiki_path, cache_k)
        if cached is not None:
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Loading from cache...'})}\n\n"
            response = {
                "type": "result",
                "query": cached.get("query", query),
                "focus": cached.get("focus", focus),
                "entry_point": cached.get("entry_point"),
                "mermaid_diagram": cached.get("mermaid_diagram", ""),
                "narrative": cached.get("narrative", ""),
                "nodes": cached.get("nodes", []),
                "edges": cached.get("edges", []),
                "files_involved": cached.get("files_involved", []),
                "total_nodes": cached.get("total_nodes", 0),
                "total_edges": cached.get("total_edges", 0),
                "cross_file_edges": cached.get("cross_file_edges", 0),
                "from_cache": True,
            }
            yield f"data: {json.dumps(response)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        from local_deepwiki.config import get_config
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.generators.codemap import CodemapFocus, generate_codemap
        from local_deepwiki.providers.embeddings import get_embedding_provider
        from local_deepwiki.providers.llm import get_cached_llm_provider

        config = get_config()
        vector_db_path = config.get_vector_db_path(repo_path)

        if not vector_db_path.exists():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Repository not indexed. Please run index_repository first.'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Initializing providers...'})}\n\n"

        embedding_provider = get_embedding_provider(config.embedding)
        vector_store = VectorStore(vector_db_path, embedding_provider)
        cache_path = config.get_wiki_path(repo_path) / "llm_cache.lance"

        llm_config = config.llm
        chat_provider = config.wiki.chat_llm_provider
        if chat_provider != "default":
            llm_config = llm_config.model_copy(update={"provider": chat_provider})

        llm = get_cached_llm_provider(
            cache_path=cache_path,
            embedding_provider=embedding_provider,
            cache_config=config.llm_cache,
            llm_config=llm_config,
        )

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Building codemap graph...'})}\n\n"

        try:
            focus_enum = CodemapFocus(focus)
            result = await generate_codemap(
                query=query,
                vector_store=vector_store,
                llm=llm,
                repo_path=repo_path,
                focus=focus_enum,
                entry_point=entry_point,
                max_depth=max_depth,
                max_nodes=max_nodes,
            )

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Codemap ready.'})}\n\n"

            response = {
                "type": "result",
                "query": result.query,
                "focus": result.focus,
                "entry_point": result.entry_point,
                "mermaid_diagram": result.mermaid_diagram,
                "narrative": result.narrative,
                "nodes": result.nodes,
                "edges": result.edges,
                "files_involved": result.files_involved,
                "total_nodes": result.total_nodes,
                "total_edges": result.total_edges,
                "cross_file_edges": result.cross_file_edges,
            }
            yield f"data: {json.dumps(response)}\n\n"

            # Write to cache
            write_cache(wiki_path, cache_k, response)

        except Exception as e:  # noqa: BLE001 - Report codemap errors to user via SSE
            logger.exception("Error generating codemap: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': sanitize_error_message(str(e))})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(
        stream_async_generator(generate_codemap_stream),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@codemap_bp.route("/api/codemap/cache")
def api_codemap_cache() -> Response | tuple[Response, int]:
    """List cached codemaps or retrieve a specific cached result.

    Query params:
        - key: If provided, return the full cached result for that key.

    Returns:
        JSON list of cached codemaps, or a single cached result.
    """
    wiki_path = _get_wiki_path()
    if wiki_path is None:
        return jsonify({"error": "Wiki path not configured"}), 500

    key = request.args.get("key")
    if key:
        # Validate key format (hex chars only)
        if not re.match(r"^[a-f0-9]{1,16}$", key):
            return jsonify({"error": "Invalid cache key"}), 400
        cached = read_cache(wiki_path, key)
        if cached is None:
            return jsonify({"error": "Cache entry not found or expired"}), 404
        return jsonify(cached)

    return jsonify(list_cached_codemaps(wiki_path))


@codemap_bp.route("/api/codemap/diff")
def api_codemap_diff() -> Response | tuple[Response, int]:
    """Return list of files changed in recent git commits.

    Query params:
        - base_ref: Git ref to diff from (default: HEAD~1)
        - head_ref: Git ref to diff to (default: HEAD)

    Returns:
        JSON with changed_files list of {file, status}.
    """
    wiki_path = _get_wiki_path()
    if wiki_path is None:
        return jsonify({"error": "Wiki path not configured"}), 500

    repo_path = wiki_path.parent
    if wiki_path.name == ".deepwiki":
        repo_path = wiki_path.parent

    base_ref = request.args.get("base_ref", "HEAD~1")
    head_ref = request.args.get("head_ref", "HEAD")

    # Validate git refs to prevent injection
    ref_pattern = re.compile(r"^[a-zA-Z0-9_.\/\-~^]+$")
    for ref_value in [base_ref, head_ref]:
        if not ref_pattern.match(ref_value):
            return jsonify({"error": f"Invalid git ref: {ref_value}"}), 400

    try:
        diff_result = subprocess.run(
            ["git", "diff", "--name-status", base_ref, head_ref],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if diff_result.returncode != 0:
            return jsonify({"error": "git diff failed", "changed_files": []}), 200
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return jsonify({"error": "git not available", "changed_files": []}), 200

    status_map = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed"}
    changed_files = []
    for line in diff_result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status_code, file_name = parts
            status = status_map.get(status_code[0], "modified")
            changed_files.append({"file": file_name, "status": status})

    return jsonify({"changed_files": changed_files})


@codemap_bp.route("/codemap/compare")
def codemap_compare_page() -> Response | str:
    """Render the side-by-side codemap comparison page."""
    wiki_path = _get_wiki_path()
    if wiki_path is None:
        abort(500, "Wiki path not configured")

    # Check if wiki is indexed
    index_md = wiki_path / "index.md"
    if not index_md.exists():
        logger.info("Wiki not indexed yet, showing onboarding page")
        return render_template("onboarding.html", wiki_path=str(wiki_path.parent))

    return render_template("codemap_compare.html", wiki_path=str(wiki_path))
