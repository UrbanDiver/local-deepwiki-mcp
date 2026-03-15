"""Shared utilities for web route blueprints."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_deepwiki.services.query_service import QueryService


def get_wiki_path() -> Path | None:
    """Retrieve the current WIKI_PATH, preferring Flask app config.

    Checks current_app.config first (set by create_app), which works even
    when the server is launched via ``python -m`` where __main__ and the
    importable module are separate objects.  Falls back to the module-level
    global for backward compatibility with tests that monkeypatch it directly.
    """
    from flask import current_app

    path = current_app.config.get("WIKI_PATH")
    if path is not None:
        return path

    from local_deepwiki.web import app as _app_module

    return _app_module.WIKI_PATH


def create_query_service(repo_path: Path) -> "QueryService":
    """Create a QueryService with providers from config.

    Encapsulates the repeated provider setup pattern used across
    chat, codemap, and research routes: get_config -> embedding provider ->
    vector store -> LLM provider -> QueryService.

    Args:
        repo_path: Path to the repository root.

    Returns:
        A configured QueryService instance.
    """
    from local_deepwiki.config import get_config
    from local_deepwiki.core.vectorstore import VectorStore
    from local_deepwiki.logging import get_logger
    from local_deepwiki.providers.embeddings import get_embedding_provider
    from local_deepwiki.providers.llm import get_cached_llm_provider
    from local_deepwiki.services.query_service import QueryService

    logger = get_logger(__name__)
    config = get_config()
    vector_db_path = config.get_vector_db_path(repo_path)

    embedding_provider = get_embedding_provider(config.embedding)
    vector_store = VectorStore(vector_db_path, embedding_provider)
    cache_path = config.get_wiki_path(repo_path) / "llm_cache.lance"

    # Determine LLM config for chat - use chat_llm_provider if set
    llm_config = config.llm
    chat_provider = config.wiki.chat_llm_provider
    if chat_provider != "default":
        llm_config = llm_config.model_copy(update={"provider": chat_provider})
        logger.info("Using %s provider for chat", chat_provider)

    llm = get_cached_llm_provider(
        cache_path=cache_path,
        embedding_provider=embedding_provider,
        cache_config=config.llm_cache,
        llm_config=llm_config,
    )

    return QueryService(vector_store, llm, config)
