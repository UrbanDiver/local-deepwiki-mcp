"""Integration tests for analysis handlers: search, entity, metadata, and deep research.

This test module validates the analysis handler pipelines that were not covered
by test_integration_pipeline.py:
- search_wiki (full-text search across wiki pages and entities)
- fuzzy_search (Levenshtein-based name matching)
- explain_entity (composite: glossary + call graph + API docs)
- impact_analysis (blast radius via reverse call graph)
- get_file_context (imports, callers, related files)
- get_complexity_metrics (cyclomatic complexity via tree-sitter)
- deep_research (multi-step reasoning pipeline)

All tests use real VectorStore (LanceDB) with content-aware embeddings and
mock LLM providers to avoid external dependencies.
"""

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
from local_deepwiki.models import (
    IndexStatus,
    WikiPage,
)
from local_deepwiki.providers.base import EmbeddingProvider


# =============================================================================
# Content-Aware Embedding Provider (self-contained per project convention)
# =============================================================================


class ContentAwareEmbeddingProvider(EmbeddingProvider):
    """Mock embedding that produces different vectors per text, making search meaningful.

    Each text is hashed to produce distinguishable normalized vectors so that
    vector search actually ranks results by relevance.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def name(self) -> str:
        return "mock:content-aware"

    def get_dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Hash-based embeddings: different content produces different normalized vectors."""
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
    """Create a sample Python repo with classes, functions, imports, and tests.

    Richer than the basic fixture to exercise analysis handler features:
    - Cross-file imports (main.py imports from utils.py)
    - Inheritance (UserModel extends BaseModel)
    - Functions with docstrings, type hints, parameters (API docs, complexity)
    - Test file referencing entities (test examples extraction)
    """
    repo_path = tmp_path / "sample_repo"
    repo_path.mkdir()

    src_dir = repo_path / "src"
    src_dir.mkdir()

    # Main module with classes and cross-file import
    (src_dir / "main.py").write_text(
        '"""Main application module."""\n'
        "\n"
        "from src.utils import validate_config\n"
        "\n"
        "\n"
        "class Application:\n"
        '    """Main application class.\n'
        "\n"
        "    Handles initialization and lifecycle of the application.\n"
        '    """\n'
        "\n"
        "    def __init__(self, config: dict):\n"
        '        """Initialize the application.\n'
        "\n"
        "        Args:\n"
        "            config: Configuration dictionary.\n"
        '        """\n'
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
        "\n"
        "    @property\n"
        "    def is_running(self) -> bool:\n"
        '        """Check if application is running."""\n'
        "        return self._running\n"
        "\n"
        "\n"
        "def create_app(config: dict) -> Application:\n"
        '    """Factory function to create an Application instance.\n'
        "\n"
        "    Args:\n"
        "        config: Application configuration.\n"
        "\n"
        "    Returns:\n"
        "        Configured Application instance.\n"
        '    """\n'
        "    return Application(config)\n"
    )

    # Utils module with helper functions
    (src_dir / "utils.py").write_text(
        '"""Utility functions for the application."""\n'
        "\n"
        "from typing import Any\n"
        "\n"
        "\n"
        "def validate_config(config: dict) -> bool:\n"
        '    """Validate the configuration dictionary.\n'
        "\n"
        "    Args:\n"
        "        config: Configuration to validate.\n"
        "\n"
        "    Returns:\n"
        "        True if valid, False otherwise.\n"
        '    """\n'
        '    required_keys = ["name", "version"]\n'
        "    return all(key in config for key in required_keys)\n"
        "\n"
        "\n"
        "def format_output(data: Any) -> str:\n"
        '    """Format data for output.\n'
        "\n"
        "    Args:\n"
        "        data: Data to format.\n"
        "\n"
        "    Returns:\n"
        "        Formatted string representation.\n"
        '    """\n'
        "    if isinstance(data, dict):\n"
        '        return "\\n".join(f"{k}: {v}" for k, v in data.items())\n'
        "    return str(data)\n"
    )

    # Models module with inheritance
    (src_dir / "models.py").write_text(
        '"""Data models for the application."""\n'
        "\n"
        "\n"
        "class BaseModel:\n"
        '    """Base model with common fields."""\n'
        "\n"
        "    def __init__(self, id: int, name: str):\n"
        "        self.id = id\n"
        "        self.name = name\n"
        "\n"
        "    def to_dict(self) -> dict:\n"
        '        """Convert to dictionary."""\n'
        '        return {"id": self.id, "name": self.name}\n'
        "\n"
        "\n"
        "class UserModel(BaseModel):\n"
        '    """User model extending BaseModel."""\n'
        "\n"
        "    def __init__(self, id: int, name: str, email: str):\n"
        "        super().__init__(id, name)\n"
        "        self.email = email\n"
        "\n"
        "    def to_dict(self) -> dict:\n"
        '        """Convert to dictionary with email."""\n'
        "        base = super().to_dict()\n"
        '        return {**base, "email": self.email}\n'
    )

    # Test file
    tests_dir = repo_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_main.py").write_text(
        '"""Tests for main module."""\n'
        "\n"
        "import pytest\n"
        "from src.main import Application, create_app\n"
        "\n"
        "\n"
        "def test_application_init():\n"
        '    """Test Application initialization."""\n'
        '    app = Application({"name": "test"})\n'
        '    assert app.config == {"name": "test"}\n'
        "    assert not app.is_running\n"
        "\n"
        "\n"
        "def test_create_app():\n"
        '    """Test create_app factory function."""\n'
        '    app = create_app({"name": "test"})\n'
        "    assert isinstance(app, Application)\n"
    )

    return repo_path


@pytest.fixture
def test_config() -> Config:
    """Create a test configuration optimized for integration tests."""
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
    """Index sample_python_repo into a real VectorStore with wiki artifacts.

    Generates:
    - Real LanceDB vector store with code chunks
    - search.json with pages and entity entries
    - toc.json with page listing

    Returns:
        Tuple of (repo_path, wiki_path, vector_store, index_status, config).
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

    # Create minimal wiki pages for search.json generation
    now = time.time()
    pages = [
        WikiPage(
            path="index.md",
            title="Sample Repo",
            content="# Sample Repo\n\nA sample Python application with Application class.",
            generated_at=now,
        ),
        WikiPage(
            path="files/src/main.md",
            title="main.py",
            content="# main.py\n\nMain module with Application class and create_app function.",
            generated_at=now,
        ),
        WikiPage(
            path="files/src/utils.md",
            title="utils.py",
            content="# utils.py\n\nUtility module with validate_config and format_output.",
            generated_at=now,
        ),
        WikiPage(
            path="files/src/models.md",
            title="models.py",
            content="# models.py\n\nData models with BaseModel and UserModel classes.",
            generated_at=now,
        ),
    ]

    # Write wiki markdown files
    for page in pages:
        page_path = wiki_path / page.path
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(page.content)

    # Generate full search index (pages + entities from real vectorstore)
    search_index = await generate_full_search_index(pages, index_status, vector_store)
    (wiki_path / "search.json").write_text(json.dumps(search_index, indent=2))

    # Generate toc.json
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

    return (sample_python_repo, wiki_path, vector_store, index_status, test_config)


# =============================================================================
# Plumbing Helpers
# =============================================================================


def _make_permissive_access_controller():
    """Create a permissive mock access controller."""
    mock_ac = MagicMock()
    mock_ac.require_permission = MagicMock()
    mock_ac.get_current_subject.return_value = None
    return mock_ac


def _patch_analysis_plumbing(
    module_path: str,
    index_status: IndexStatus,
    wiki_path: Path,
    config: Config,
    vector_store: Any = None,
) -> ExitStack:
    """Patch shared handler plumbing for an analysis handler module.

    Each analysis handler module imports _load_index_status, _create_vector_store,
    and get_access_controller from _shared. This helper patches them at the
    correct import location.

    Args:
        module_path: Dotted module path (e.g. "local_deepwiki.handlers.analysis_search").
        index_status: IndexStatus to return from _load_index_status.
        wiki_path: Wiki path to return from _load_index_status.
        config: Config to return from _load_index_status.
        vector_store: Optional VectorStore to return from _create_vector_store.

    Returns:
        ExitStack with active patches.
    """
    stack = ExitStack()

    # _load_index_status -> return test data
    stack.enter_context(
        patch(
            f"{module_path}._load_index_status",
            new_callable=AsyncMock,
            return_value=(index_status, wiki_path, config),
        )
    )

    # _create_vector_store -> return real or mock vector store
    if vector_store is not None:
        stack.enter_context(
            patch(
                f"{module_path}._create_vector_store",
                return_value=vector_store,
            )
        )

    # Permissive RBAC
    stack.enter_context(
        patch(
            f"{module_path}.get_access_controller",
            return_value=_make_permissive_access_controller(),
        )
    )

    # No-op query validation (where used)
    try:
        stack.enter_context(patch(f"{module_path}.validate_query_parameters"))
    except AttributeError:
        pass  # Not all modules import validate_query_parameters

    return stack


# =============================================================================
# Search Wiki Integration Tests
# =============================================================================


class TestSearchWikiIntegration:
    """Tests for handle_search_wiki with real search.json from indexed repo."""

    async def test_search_wiki_finds_entity_by_name(self, indexed_repo):
        """Search for 'Application' and verify entity match with correct type and file."""
        from local_deepwiki.handlers.analysis_search import handle_search_wiki

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        with _patch_analysis_plumbing(
            "local_deepwiki.handlers.analysis_search",
            index_status,
            wiki_path,
            config,
        ):
            result = await handle_search_wiki(
                {"repo_path": str(repo_path), "query": "Application", "limit": 10}
            )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total_matches"] > 0

        # Should find the Application class entity
        entity_matches = [m for m in data["matches"] if m["type"] == "entity"]
        assert len(entity_matches) > 0
        app_match = next(
            (m for m in entity_matches if "Application" in (m.get("name") or "")),
            None,
        )
        assert app_match is not None
        assert app_match["entity_type"] == "class"
        assert "main.py" in app_match["file"]

    async def test_search_wiki_finds_page_by_title(self, indexed_repo):
        """Search for a page title and verify page match with path."""
        from local_deepwiki.handlers.analysis_search import handle_search_wiki

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        with _patch_analysis_plumbing(
            "local_deepwiki.handlers.analysis_search",
            index_status,
            wiki_path,
            config,
        ):
            result = await handle_search_wiki(
                {"repo_path": str(repo_path), "query": "utils", "limit": 10}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total_matches"] > 0

        # Should find pages or entities related to utils
        all_names = [m.get("title") or m.get("name", "") for m in data["matches"]]
        assert any("utils" in name.lower() for name in all_names)


# =============================================================================
# Fuzzy Search Integration Tests
# =============================================================================


class TestFuzzySearchIntegration:
    """Tests for handle_fuzzy_search with real VectorStore chunks."""

    async def test_fuzzy_search_finds_similar_name(self, indexed_repo):
        """Search for 'Applicaton' (typo) and verify 'Application' appears."""
        from local_deepwiki.handlers.analysis_search import handle_fuzzy_search

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        with _patch_analysis_plumbing(
            "local_deepwiki.handlers.analysis_search",
            index_status,
            wiki_path,
            config,
            vector_store,
        ):
            result = await handle_fuzzy_search(
                {
                    "repo_path": str(repo_path),
                    "query": "Applicaton",
                    "threshold": 0.5,
                    "limit": 10,
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total_matches"] > 0

        match_names = [m["name"] for m in data["matches"]]
        assert "Application" in match_names

        # Each match should have a score > 0
        for match in data["matches"]:
            assert match["score"] > 0

    async def test_fuzzy_search_includes_file_suggestions(self, indexed_repo):
        """Search for 'main' and verify file_suggestions includes main.py."""
        from local_deepwiki.handlers.analysis_search import handle_fuzzy_search

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        with _patch_analysis_plumbing(
            "local_deepwiki.handlers.analysis_search",
            index_status,
            wiki_path,
            config,
            vector_store,
        ):
            result = await handle_fuzzy_search(
                {
                    "repo_path": str(repo_path),
                    "query": "main",
                    "threshold": 0.3,
                    "limit": 10,
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"

        file_suggestions = data.get("file_suggestions", [])
        assert any("main.py" in f for f in file_suggestions)


# =============================================================================
# Explain Entity Integration Tests
# =============================================================================


class TestExplainEntityIntegration:
    """Tests for handle_explain_entity with real search.json and source files."""

    async def test_explain_entity_class(self, indexed_repo):
        """Explain 'Application' class and verify entity_found, entity_info, call_graph, api_docs."""
        from local_deepwiki.handlers.analysis_entity import handle_explain_entity

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        with _patch_analysis_plumbing(
            "local_deepwiki.handlers.analysis_entity",
            index_status,
            wiki_path,
            config,
            vector_store,
        ):
            result = await handle_explain_entity(
                {
                    "repo_path": str(repo_path),
                    "entity_name": "Application",
                    "include_call_graph": True,
                    "include_api_docs": True,
                    "include_inheritance": False,
                    "include_test_examples": False,
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["entity_found"] is True

        # Entity info
        entity_info = data["entity_info"]
        assert entity_info["type"] == "class"
        assert "main.py" in entity_info["file"]

        # Call graph should be present (may be empty but structurally valid)
        assert "call_graph" in data
        assert "calls" in data["call_graph"]
        assert "called_by" in data["call_graph"]

        # API docs should have class methods
        assert "api_docs" in data
        api_docs = data["api_docs"]
        assert "methods" in api_docs
        method_names = [m["name"] for m in api_docs["methods"]]
        assert "__init__" in method_names
        assert "start" in method_names

    async def test_explain_entity_function(self, indexed_repo):
        """Explain 'validate_config' function and verify api_docs with parameters."""
        from local_deepwiki.handlers.analysis_entity import handle_explain_entity

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        with _patch_analysis_plumbing(
            "local_deepwiki.handlers.analysis_entity",
            index_status,
            wiki_path,
            config,
            vector_store,
        ):
            result = await handle_explain_entity(
                {
                    "repo_path": str(repo_path),
                    "entity_name": "validate_config",
                    "include_call_graph": True,
                    "include_api_docs": True,
                    "include_inheritance": False,
                    "include_test_examples": False,
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["entity_found"] is True
        assert data["entity_info"]["type"] == "function"

        # API docs for the function
        assert "api_docs" in data
        api_docs = data["api_docs"]
        assert "parameters" in api_docs
        param_names = [p["name"] for p in api_docs["parameters"]]
        assert "config" in param_names
        assert api_docs["return_type"] == "bool"


# =============================================================================
# Impact Analysis Integration Tests
# =============================================================================


class TestImpactAnalysisIntegration:
    """Tests for handle_impact_analysis with real VectorStore and source files."""

    async def test_impact_analysis_on_utils(self, indexed_repo):
        """Analyze impact of src/utils.py and verify reverse_call_graph and impact_summary."""
        from local_deepwiki.handlers.analysis_entity import handle_impact_analysis

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        with _patch_analysis_plumbing(
            "local_deepwiki.handlers.analysis_entity",
            index_status,
            wiki_path,
            config,
            vector_store,
        ):
            result = await handle_impact_analysis(
                {
                    "repo_path": str(repo_path),
                    "file_path": "src/utils.py",
                    "include_reverse_calls": True,
                    "include_inheritance": False,
                    "include_dependents": False,
                    "include_wiki_pages": True,
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["file_path"] == "src/utils.py"

        # Reverse call graph should be present
        assert "reverse_call_graph" in data

        # Impact summary should have risk_level
        assert "impact_summary" in data
        summary = data["impact_summary"]
        assert "risk_level" in summary
        assert summary["risk_level"] in ("low", "medium", "high")

        # affected_wiki_pages should be present (may be empty)
        assert "affected_wiki_pages" in data


# =============================================================================
# File Context Integration Tests
# =============================================================================


class TestFileContextIntegration:
    """Tests for handle_get_file_context with real VectorStore chunks."""

    async def test_file_context_shows_imports_and_related(self, indexed_repo):
        """Get context for src/main.py and verify imports and related_files."""
        from local_deepwiki.handlers.analysis_metadata import handle_get_file_context

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        with _patch_analysis_plumbing(
            "local_deepwiki.handlers.analysis_metadata",
            index_status,
            wiki_path,
            config,
            vector_store,
        ):
            result = await handle_get_file_context(
                {"repo_path": str(repo_path), "file_path": "src/main.py"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        context = data["context"]
        assert context["file_path"] == "src/main.py"

        # Should have imports (main.py imports from utils)
        assert "imports" in context
        assert isinstance(context["imports"], list)

        # Should have related_files
        assert "related_files" in context
        assert isinstance(context["related_files"], list)


# =============================================================================
# Complexity Metrics Integration Tests
# =============================================================================


class TestComplexityMetricsIntegration:
    """Tests for handle_get_complexity_metrics with real source files."""

    async def test_complexity_metrics_on_python_file(self, indexed_repo):
        """Analyze src/main.py and verify functions, classes, and complexity fields."""
        from local_deepwiki.handlers.analysis_metadata import (
            handle_get_complexity_metrics,
        )

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        # Only need access controller patch (no index or vectorstore needed)
        with patch(
            "local_deepwiki.handlers.analysis_metadata.get_access_controller",
            return_value=_make_permissive_access_controller(),
        ):
            result = await handle_get_complexity_metrics(
                {"repo_path": str(repo_path), "file_path": "src/main.py"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["file_path"] == "src/main.py"
        assert data["language"] == "python"

        # Lines
        assert "lines" in data
        assert data["lines"]["total"] > 0

        # Counts - should have at least the Application class and its methods
        assert "counts" in data
        assert data["counts"]["classes"] >= 1
        assert data["counts"]["functions"] >= 1

        # Complexity metrics
        assert "complexity" in data
        assert "avg_cyclomatic" in data["complexity"]
        assert "max_cyclomatic" in data["complexity"]

        # Functions list
        assert "functions" in data
        func_names = [f["name"] for f in data["functions"]]
        assert "__init__" in func_names

        # Classes list
        assert "classes" in data
        class_names = [c["name"] for c in data["classes"]]
        assert "Application" in class_names


# =============================================================================
# Deep Research Integration Tests
# =============================================================================


class TestDeepResearchIntegration:
    """Tests for handle_deep_research with real VectorStore and mock LLM."""

    async def test_deep_research_produces_structured_result(self, indexed_repo):
        """Run deep research and verify structured result with answer and sub_questions."""
        from local_deepwiki.handlers.research import handle_deep_research

        repo_path, wiki_path, vector_store, index_status, config = indexed_repo

        # Mock LLM that returns canned responses for each research phase
        mock_llm = MagicMock()

        async def mock_generate(prompt: str, **kwargs) -> str:
            prompt_lower = prompt.lower()
            if "decompose" in prompt_lower or "sub-question" in prompt_lower:
                return json.dumps(
                    {
                        "sub_questions": [
                            {
                                "question": "What is the Application class?",
                                "category": "definition",
                            },
                            {"question": "How does it start?", "category": "behavior"},
                        ]
                    }
                )
            if "gap" in prompt_lower or "follow-up" in prompt_lower:
                return json.dumps({"follow_up_queries": []})
            # Synthesis / default
            return (
                "The Application class manages the app lifecycle. "
                "It initializes with a config dict and provides start/stop methods."
            )

        mock_llm.generate = AsyncMock(side_effect=mock_generate)

        stack = ExitStack()

        # Patch get_config to return test config with correct paths
        mock_config = MagicMock()
        mock_config.get_vector_db_path.return_value = vector_store.db_path
        mock_config.get_wiki_path.return_value = wiki_path
        mock_config.embedding = config.embedding
        mock_config.llm = config.llm
        mock_config.llm_cache = config.llm_cache
        mock_config.deep_research = config.deep_research
        mock_config.get_prompts.return_value = config.get_prompts()
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.research.get_config",
                return_value=mock_config,
            )
        )

        # Patch get_embedding_provider to return our content-aware provider
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.research.get_embedding_provider",
                return_value=ContentAwareEmbeddingProvider(),
            )
        )

        # Patch VectorStore in research module to return our real store
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.research.VectorStore",
                return_value=vector_store,
            )
        )

        # Patch get_cached_llm_provider to return our mock
        stack.enter_context(
            patch(
                "local_deepwiki.providers.llm.get_cached_llm_provider",
                return_value=mock_llm,
            )
        )

        # Patch RBAC
        stack.enter_context(
            patch(
                "local_deepwiki.handlers.research.get_access_controller",
                return_value=_make_permissive_access_controller(),
            )
        )

        # Patch validation (no-op)
        stack.enter_context(
            patch("local_deepwiki.handlers.research.validate_deep_research_parameters")
        )

        with stack:
            result = await handle_deep_research(
                {
                    "repo_path": str(repo_path),
                    "question": "How does the Application class work?",
                    "max_chunks": 20,
                }
            )

        assert len(result) == 1
        data = json.loads(result[0].text)

        # Should be a successful research result (not an error)
        # The result may have "question" + "answer" (success) or "status" key
        if "status" in data and data["status"] == "error":
            pytest.fail(f"Deep research returned error: {data}")

        # Verify structured result
        assert "answer" in data
        assert len(data["answer"]) > 0
        assert "sub_questions" in data
        assert "stats" in data
        assert data["stats"]["chunks_analyzed"] >= 0
