"""Integration tests for agentic tool handlers (Phase 3+5).

Exercises suggest_next_actions, batch_explain_entities, and query_codebase
against a real indexed repository with a real LanceDB vector store and
content-aware embeddings.  Only LLM calls and RBAC are mocked.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import ChunkingConfig, Config, ParsingConfig, WikiConfig
from local_deepwiki.core.indexer import RepositoryIndexer
from local_deepwiki.models import IndexStatus, WikiPage
from local_deepwiki.providers.base import EmbeddingProvider


# =============================================================================
# Content-Aware Embedding Provider (same approach as test_integration_analysis)
# =============================================================================


class ContentAwareEmbeddingProvider(EmbeddingProvider):
    """Hash-based embeddings that produce distinguishable normalized vectors."""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def name(self) -> str:
        return "mock:content-aware"

    def get_dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            h = hashlib.sha256(text.encode()).digest()
            raw = [h[i % len(h)] / 255.0 for i in range(self._dimension)]
            norm = math.sqrt(sum(x * x for x in raw))
            vec = [x / norm for x in raw] if norm > 0 else raw
            results.append(vec)
        return results


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_python_repo(tmp_path: Path) -> Path:
    """Create a minimal Python repo with classes and functions."""
    repo_path = tmp_path / "sample_repo"
    repo_path.mkdir()

    src_dir = repo_path / "src"
    src_dir.mkdir()

    (src_dir / "main.py").write_text(
        '"""Main application module."""\n'
        "\n"
        "from src.utils import validate_config\n"
        "\n"
        "\n"
        "class Application:\n"
        '    """Main application class."""\n'
        "\n"
        "    def __init__(self, config: dict):\n"
        "        self.config = config\n"
        "        self._running = False\n"
        "\n"
        "    def start(self) -> None:\n"
        '        """Start the application."""\n'
        "        if validate_config(self.config):\n"
        "            self._running = True\n"
        "\n"
        "    def stop(self) -> None:\n"
        '        """Stop the application."""\n'
        "        self._running = False\n"
    )

    (src_dir / "utils.py").write_text(
        '"""Utility functions."""\n'
        "\n"
        "\n"
        "def validate_config(config: dict) -> bool:\n"
        '    """Validate configuration dictionary."""\n'
        '    return "name" in config and "version" in config\n'
        "\n"
        "\n"
        "def format_output(data) -> str:\n"
        '    """Format data for display."""\n'
        "    return str(data)\n"
    )

    return repo_path


@pytest.fixture
def test_config() -> Config:
    chunking = ChunkingConfig().model_copy(
        update={"batch_size": 10, "max_chunk_size": 2000}
    )
    parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
    wiki = WikiConfig().model_copy(update={"max_concurrent_llm": 2})
    return Config().model_copy(
        update={"chunking": chunking, "parsing": parsing, "wiki": wiki}
    )


@pytest.fixture
async def indexed_repo(sample_python_repo: Path, tmp_path: Path, test_config: Config):
    """Index a sample repo into a real VectorStore with wiki artifacts.

    Returns (repo_path, wiki_path, vector_store, index_status, config).
    """
    from local_deepwiki.core.vectorstore import VectorStore
    from local_deepwiki.generators.search import generate_full_search_index

    embedding_provider = ContentAwareEmbeddingProvider()
    db_path = tmp_path / "vectors.lance"
    vector_store = VectorStore(db_path, embedding_provider)

    indexer = RepositoryIndexer(sample_python_repo, test_config)
    indexer.vector_store = vector_store

    index_status = await indexer.index(full_rebuild=True)
    wiki_path = indexer.wiki_path

    now = time.time()
    pages = [
        WikiPage(
            path="index.md",
            title="Sample Repo",
            content="# Sample Repo\n\nA sample Python application.",
            generated_at=now,
        ),
        WikiPage(
            path="files/src/main.md",
            title="main.py",
            content="# main.py\n\nMain module with Application class.",
            generated_at=now,
        ),
        WikiPage(
            path="files/src/utils.md",
            title="utils.py",
            content="# utils.py\n\nUtility module with validate_config.",
            generated_at=now,
        ),
    ]

    for page in pages:
        page_path = wiki_path / page.path
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(page.content)

    search_index = await generate_full_search_index(pages, index_status, vector_store)
    (wiki_path / "search.json").write_text(json.dumps(search_index, indent=2))

    toc_data = {
        "pages": [
            {
                "title": p.title,
                "path": p.path,
                "source_file": p.path.replace("files/", "").replace(".md", ".py")
                if p.path.startswith("files/")
                else "",
            }
            for p in pages
        ]
    }
    (wiki_path / "toc.json").write_text(json.dumps(toc_data, indent=2))

    # Write index_status.json (needed by some handlers)
    status_data = {
        "repo_path": str(sample_python_repo),
        "indexed_at": now,
        "total_files": index_status.total_files,
        "total_chunks": index_status.total_chunks,
        "languages": index_status.languages,
        "files": [
            {"path": f.path, "language": f.language, "chunks": f.chunk_count}
            for f in index_status.files
        ],
        "schema_version": 1,
    }
    (wiki_path / "index_status.json").write_text(json.dumps(status_data, indent=2))

    return (sample_python_repo, wiki_path, vector_store, index_status, test_config)


# =============================================================================
# Helpers
# =============================================================================


def _make_permissive_access_controller():
    mock_ac = MagicMock()
    mock_ac.require_permission = MagicMock()
    mock_ac.get_current_subject.return_value = None
    return mock_ac


def _patch_agentic_plumbing(
    index_status: IndexStatus,
    wiki_path: Path,
    config: Config,
) -> ExitStack:
    """Patch _load_index_status and RBAC for the agentic handlers module."""
    stack = ExitStack()

    stack.enter_context(
        patch(
            "local_deepwiki.handlers.agentic._load_index_status",
            new_callable=AsyncMock,
            return_value=(index_status, wiki_path, config),
        )
    )

    stack.enter_context(
        patch(
            "local_deepwiki.handlers.agentic.get_access_controller",
            return_value=_make_permissive_access_controller(),
        )
    )

    return stack


# =============================================================================
# Tests: suggest_next_actions
# =============================================================================


class TestSuggestNextActionsIntegration:
    """Integration tests for suggest_next_actions with a real wiki directory."""

    async def test_detects_existing_wiki(self, indexed_repo) -> None:
        """With a real wiki, should suggest read_wiki_structure, not index_repository."""
        from local_deepwiki.handlers.agentic import handle_suggest_next_actions

        repo_path, wiki_path, _vs, _is, config = indexed_repo

        with patch("local_deepwiki.config.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.get_wiki_path.return_value = wiki_path
            mock_config.return_value = mock_cfg

            result = await handle_suggest_next_actions({"repo_path": str(repo_path)})

        data = json.loads(result[0].text)
        suggestions = data["data"]["suggestions"]
        tool_names = [s["tool"] for s in suggestions]

        assert "read_wiki_structure" in tool_names
        assert "index_repository" not in tool_names

    async def test_graph_traversal_sequence(self) -> None:
        """After index_repository -> read_wiki_structure, suggestions evolve correctly."""
        from local_deepwiki.handlers.agentic import handle_suggest_next_actions

        # Step 1: after indexing
        result1 = await handle_suggest_next_actions(
            {"tools_used": ["index_repository"]}
        )
        data1 = json.loads(result1[0].text)
        tools1 = [s["tool"] for s in data1["data"]["suggestions"]]
        assert "read_wiki_structure" in tools1

        # Step 2: after reading structure
        result2 = await handle_suggest_next_actions(
            {"tools_used": ["index_repository", "read_wiki_structure"]}
        )
        data2 = json.loads(result2[0].text)
        tools2 = [s["tool"] for s in data2["data"]["suggestions"]]

        # read_wiki_structure already used, should not reappear
        assert "read_wiki_structure" not in tools2
        # Should suggest deeper exploration tools
        assert any(
            t in tools2 for t in ("read_wiki_page", "search_wiki", "ask_question")
        )


# =============================================================================
# Tests: batch_explain_entities
# =============================================================================


class TestBatchExplainEntitiesIntegration:
    """Integration tests for batch_explain_entities with real search.json."""

    async def test_finds_real_entities(self, indexed_repo) -> None:
        """Look up entities that exist in the real search index."""
        from local_deepwiki.handlers.agentic import handle_batch_explain_entities

        repo_path, wiki_path, _vs, index_status, config = indexed_repo

        with _patch_agentic_plumbing(index_status, wiki_path, config):
            result = await handle_batch_explain_entities(
                {
                    "repo_path": str(repo_path),
                    "entity_names": ["Application", "validate_config"],
                }
            )

        data = json.loads(result[0].text)
        assert data["data"]["total_requested"] == 2
        assert data["data"]["total_found"] == 2

        results = data["data"]["results"]
        app_result = next(r for r in results if r["entity"] == "Application")
        assert app_result["found"] is True
        assert app_result["matches"][0]["type"] == "class"
        assert "main.py" in app_result["matches"][0]["file"]

        vc_result = next(r for r in results if r["entity"] == "validate_config")
        assert vc_result["found"] is True
        assert vc_result["matches"][0]["type"] == "function"

    async def test_partial_match(self, indexed_repo) -> None:
        """Mix of real and nonexistent entities returns partial results."""
        from local_deepwiki.handlers.agentic import handle_batch_explain_entities

        repo_path, wiki_path, _vs, index_status, config = indexed_repo

        with _patch_agentic_plumbing(index_status, wiki_path, config):
            result = await handle_batch_explain_entities(
                {
                    "repo_path": str(repo_path),
                    "entity_names": ["Application", "nonexistent_func"],
                }
            )

        data = json.loads(result[0].text)
        assert data["data"]["total_found"] == 1
        results = data["data"]["results"]
        assert results[0]["found"] is True
        assert results[1]["found"] is False


# =============================================================================
# Tests: query_codebase
# =============================================================================


class TestQueryCodebaseIntegration:
    """Integration tests for query_codebase with real vector store + mock LLM."""

    async def test_returns_structured_response(self, indexed_repo) -> None:
        """query_codebase returns a valid envelope with answer and escalated flag."""
        from local_deepwiki.handlers.agentic import handle_query_codebase

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        # Mock the LLM to return a long answer (no escalation)
        long_answer = "The Application class initializes with a config dict. " * 10
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=long_answer)

        stack = ExitStack()

        # Patch RBAC for query_codebase
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.agentic.get_access_controller",
                return_value=_make_permissive_access_controller(),
            )
        )

        # Patch plumbing for the inner handle_ask_question call
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.core._load_index_status",
                new_callable=AsyncMock,
                return_value=(index_status, wiki_path, config),
            )
        )
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.core._create_vector_store",
                return_value=vector_store,
            )
        )
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.core.get_access_controller",
                return_value=_make_permissive_access_controller(),
            )
        )
        stack.enter_context(
            patch("local_deepwiki.handlers.core.validate_query_parameters")
        )

        # Patch LLM provider used by ask_question
        stack.enter_context(
            patch(
                "local_deepwiki.providers.llm.get_cached_llm_provider",
                return_value=mock_llm,
            )
        )

        # Patch get_config for agentic_rag path (used by core.py)
        mock_cfg = MagicMock()
        mock_cfg.get_wiki_path.return_value = wiki_path
        mock_cfg.get_vector_db_path.return_value = vector_store.db_path
        mock_cfg.embedding = config.embedding
        mock_cfg.llm = config.llm
        mock_cfg.llm_cache = config.llm_cache
        mock_cfg.get_prompts.return_value = config.get_prompts()
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.core.get_config",
                return_value=mock_cfg,
            )
        )

        # Patch get_embedding_provider for agentic_rag path
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.core.get_embedding_provider",
                return_value=ContentAwareEmbeddingProvider(),
            )
        )

        with stack:
            result = await handle_query_codebase(
                {
                    "repo_path": str(repo_path),
                    "query": "How does the Application class work?",
                }
            )

        data = json.loads(result[0].text)
        assert data["tool"] == "query_codebase"
        assert data["status"] == "success"
        assert "answer" in data["data"] or "escalated" in data["data"]
        assert data["data"]["escalated"] is False
        assert "hints" in data

    async def test_no_escalation_when_disabled(self, indexed_repo) -> None:
        """With auto_escalate=False, short answers are not escalated."""
        from local_deepwiki.handlers.agentic import handle_query_codebase

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        # Mock LLM returns very short answer
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="Short.")

        stack = ExitStack()
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.agentic.get_access_controller",
                return_value=_make_permissive_access_controller(),
            )
        )
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.core._load_index_status",
                new_callable=AsyncMock,
                return_value=(index_status, wiki_path, config),
            )
        )
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.core._create_vector_store",
                return_value=vector_store,
            )
        )
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.core.get_access_controller",
                return_value=_make_permissive_access_controller(),
            )
        )
        stack.enter_context(
            patch("local_deepwiki.handlers.core.validate_query_parameters")
        )
        stack.enter_context(
            patch(
                "local_deepwiki.providers.llm.get_cached_llm_provider",
                return_value=mock_llm,
            )
        )
        mock_cfg = MagicMock()
        mock_cfg.get_wiki_path.return_value = wiki_path
        mock_cfg.get_vector_db_path.return_value = vector_store.db_path
        mock_cfg.embedding = config.embedding
        mock_cfg.llm = config.llm
        mock_cfg.llm_cache = config.llm_cache
        mock_cfg.get_prompts.return_value = config.get_prompts()
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.core.get_config",
                return_value=mock_cfg,
            )
        )
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.core.get_embedding_provider",
                return_value=ContentAwareEmbeddingProvider(),
            )
        )

        with stack:
            result = await handle_query_codebase(
                {
                    "repo_path": str(repo_path),
                    "query": "What is Application?",
                    "auto_escalate": False,
                }
            )

        data = json.loads(result[0].text)
        assert data["data"]["escalated"] is False


# =============================================================================
# Tests: End-to-end tool chain
# =============================================================================


class TestAgenticToolChainIntegration:
    """Test that agentic tools compose correctly in sequence."""

    async def test_suggest_then_batch_explain(self, indexed_repo) -> None:
        """suggest_next_actions -> batch_explain_entities using discovered entities."""
        from local_deepwiki.handlers.agentic import (
            handle_batch_explain_entities,
            handle_suggest_next_actions,
        )

        repo_path, wiki_path, _vs, index_status, config = indexed_repo

        # Step 1: get suggestions after indexing
        result1 = await handle_suggest_next_actions(
            {"tools_used": ["index_repository"]}
        )
        data1 = json.loads(result1[0].text)
        assert data1["status"] == "success"

        # Step 2: use batch_explain_entities (a tool that would logically follow)
        with _patch_agentic_plumbing(index_status, wiki_path, config):
            result2 = await handle_batch_explain_entities(
                {
                    "repo_path": str(repo_path),
                    "entity_names": ["Application", "validate_config", "format_output"],
                }
            )

        data2 = json.loads(result2[0].text)
        assert data2["status"] == "success"
        assert data2["data"]["total_requested"] == 3
        # At least Application and validate_config should be found
        assert data2["data"]["total_found"] >= 2

        # Verify entity details are structurally complete
        for r in data2["data"]["results"]:
            assert "entity" in r
            assert "found" in r
            if r["found"]:
                assert len(r["matches"]) > 0
                match = r["matches"][0]
                assert "name" in match
                assert "type" in match
                assert "file" in match
