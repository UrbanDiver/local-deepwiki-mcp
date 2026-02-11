"""Tests for the 5 new MCP tools: search_wiki, get_project_manifest,
get_file_context, fuzzy_search, get_wiki_stats."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.handlers import (
    handle_fuzzy_search,
    handle_get_file_context,
    handle_get_project_manifest,
    handle_get_wiki_stats,
    handle_search_wiki,
)
from local_deepwiki.models import (
    FuzzySearchArgs,
    GetFileContextArgs,
    GetProjectManifestArgs,
    GetWikiStatsArgs,
    SearchWikiArgs,
)


# ── Args model validation tests ──────────────────────────────────────


class TestSearchWikiArgs:
    def test_valid_args(self):
        args = SearchWikiArgs(repo_path="/tmp/repo", query="test")
        assert args.query == "test"
        assert args.limit == 20

    def test_empty_query_rejected(self):
        with pytest.raises(Exception):
            SearchWikiArgs(repo_path="/tmp/repo", query="")

    def test_limit_bounds(self):
        args = SearchWikiArgs(repo_path="/tmp/repo", query="test", limit=100)
        assert args.limit == 100
        with pytest.raises(Exception):
            SearchWikiArgs(repo_path="/tmp/repo", query="test", limit=101)

    def test_entity_types_filter(self):
        args = SearchWikiArgs(
            repo_path="/tmp/repo", query="test", entity_types=["function", "class"]
        )
        assert args.entity_types == ["function", "class"]


class TestGetProjectManifestArgs:
    def test_valid_args(self):
        args = GetProjectManifestArgs(repo_path="/tmp/repo")
        assert args.use_cache is True

    def test_no_cache(self):
        args = GetProjectManifestArgs(repo_path="/tmp/repo", use_cache=False)
        assert args.use_cache is False


class TestGetFileContextArgs:
    def test_valid_args(self):
        args = GetFileContextArgs(repo_path="/tmp/repo", file_path="src/main.py")
        assert args.file_path == "src/main.py"

    def test_empty_file_path_rejected(self):
        with pytest.raises(Exception):
            GetFileContextArgs(repo_path="/tmp/repo", file_path="")


class TestFuzzySearchArgs:
    def test_valid_args(self):
        args = FuzzySearchArgs(repo_path="/tmp/repo", query="calculate")
        assert args.threshold == 0.6
        assert args.limit == 10

    def test_threshold_bounds(self):
        args = FuzzySearchArgs(repo_path="/tmp/repo", query="test", threshold=0.0)
        assert args.threshold == 0.0
        args = FuzzySearchArgs(repo_path="/tmp/repo", query="test", threshold=1.0)
        assert args.threshold == 1.0
        with pytest.raises(Exception):
            FuzzySearchArgs(repo_path="/tmp/repo", query="test", threshold=1.1)

    def test_entity_type_filter(self):
        args = FuzzySearchArgs(
            repo_path="/tmp/repo", query="test", entity_type="function"
        )
        assert args.entity_type == "function"


class TestGetWikiStatsArgs:
    def test_valid_args(self):
        args = GetWikiStatsArgs(repo_path="/tmp/repo")
        assert args.repo_path == "/tmp/repo"


# ── Handler tests ────────────────────────────────────────────────────


def _make_index_status(repo_path="/tmp/repo"):
    """Create a mock IndexStatus."""
    status = MagicMock()
    status.repo_path = repo_path
    status.indexed_at = 1700000000.0
    status.total_files = 10
    status.total_chunks = 100
    status.languages = ["python"]
    status.schema_version = 3
    status.files = []
    return status


def _make_config(repo_path="/tmp/repo"):
    """Create a mock config."""
    config = MagicMock()
    config.get_vector_db_path.return_value = Path(repo_path) / ".vector_db"
    config.get_wiki_path.return_value = Path(repo_path) / ".deepwiki"
    config.embedding = MagicMock()
    return config


@pytest.fixture
def mock_access_control():
    with (
        patch("local_deepwiki.handlers.analysis_search.get_access_controller") as m1,
        patch("local_deepwiki.handlers.analysis_metadata.get_access_controller") as m2,
    ):
        controller = MagicMock()
        m1.return_value = controller
        m2.return_value = controller
        yield controller


@pytest.fixture
def wiki_dir(tmp_path):
    """Create a temporary wiki directory with test data."""
    wiki_path = tmp_path / ".deepwiki"
    wiki_path.mkdir()

    # search.json
    search_data = {
        "pages": [
            {
                "path": "files/src/main.md",
                "title": "Main Module",
                "headings": ["Overview", "Functions"],
                "terms": ["parse_config", "load_data"],
                "snippet": "The main module handles configuration parsing.",
            },
            {
                "path": "files/src/utils.md",
                "title": "Utilities",
                "headings": ["Helper Functions"],
                "terms": ["format_string"],
                "snippet": "Various utility helpers for the project.",
            },
        ],
        "entities": [
            {
                "type": "entity",
                "entity_type": "function",
                "name": "parse_config",
                "display_name": "parse_config",
                "path": "files/src/main.md",
                "file": "src/main.py",
                "signature": "(path) -> Config",
                "description": "Parse configuration from a YAML file.",
                "is_async": False,
                "raises": [],
                "keywords": ["parse", "config", "yaml"],
            },
            {
                "type": "entity",
                "entity_type": "class",
                "name": "Config",
                "display_name": "Config",
                "path": "files/src/main.md",
                "file": "src/main.py",
                "signature": "",
                "description": "Configuration container class.",
                "is_async": False,
                "raises": [],
                "keywords": ["config"],
            },
        ],
        "meta": {"total_pages": 2, "total_entities": 2},
    }
    (wiki_path / "search.json").write_text(json.dumps(search_data))

    # toc.json
    toc_data = [
        {"title": "Main Module", "path": "files/src/main.md"},
        {"title": "Utilities", "path": "files/src/utils.md"},
    ]
    (wiki_path / "toc.json").write_text(json.dumps(toc_data))

    # wiki_status.json
    (wiki_path / "wiki_status.json").write_text(
        json.dumps({"generated_pages": 2, "skipped_pages": 0})
    )

    # A wiki markdown file
    files_dir = wiki_path / "files" / "src"
    files_dir.mkdir(parents=True)
    (files_dir / "main.md").write_text("# Main Module\nContent here.")

    return wiki_path


class TestHandleSearchWiki:
    async def test_search_pages_by_title(self, tmp_path, wiki_dir, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with patch(
            "local_deepwiki.handlers.analysis_search._load_index_status",
            return_value=(index_status, wiki_dir, config),
        ):
            result = await handle_search_wiki(
                {"repo_path": str(tmp_path), "query": "Main Module"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total_matches"] >= 1
        assert data["matches"][0]["title"] == "Main Module"

    async def test_search_entities(self, tmp_path, wiki_dir, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with patch(
            "local_deepwiki.handlers.analysis_search._load_index_status",
            return_value=(index_status, wiki_dir, config),
        ):
            result = await handle_search_wiki(
                {"repo_path": str(tmp_path), "query": "parse_config"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert any(m["type"] == "entity" for m in data["matches"])

    async def test_search_with_entity_type_filter(
        self, tmp_path, wiki_dir, mock_access_control
    ):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with patch(
            "local_deepwiki.handlers.analysis_search._load_index_status",
            return_value=(index_status, wiki_dir, config),
        ):
            result = await handle_search_wiki(
                {
                    "repo_path": str(tmp_path),
                    "query": "config",
                    "entity_types": ["class"],
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        for m in data["matches"]:
            assert m["type"] == "entity" and m["entity_type"] == "class"

    async def test_search_no_results(self, tmp_path, wiki_dir, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with patch(
            "local_deepwiki.handlers.analysis_search._load_index_status",
            return_value=(index_status, wiki_dir, config),
        ):
            result = await handle_search_wiki(
                {"repo_path": str(tmp_path), "query": "nonexistent_xyz"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total_matches"] == 0

    async def test_search_missing_search_index(self, tmp_path, mock_access_control):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with patch(
            "local_deepwiki.handlers.analysis_search._load_index_status",
            return_value=(index_status, wiki_path, config),
        ):
            result = await handle_search_wiki(
                {"repo_path": str(tmp_path), "query": "test"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "Search index not found" in data["error"]

    async def test_search_invalid_args(self, mock_access_control):
        result = await handle_search_wiki({"repo_path": "/tmp/repo"})
        assert "Error" in result[0].text

    async def test_search_by_keyword(self, tmp_path, wiki_dir, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with patch(
            "local_deepwiki.handlers.analysis_search._load_index_status",
            return_value=(index_status, wiki_dir, config),
        ):
            result = await handle_search_wiki(
                {"repo_path": str(tmp_path), "query": "yaml"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total_matches"] >= 1

    async def test_search_page_only_filter(
        self, tmp_path, wiki_dir, mock_access_control
    ):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with patch(
            "local_deepwiki.handlers.analysis_search._load_index_status",
            return_value=(index_status, wiki_dir, config),
        ):
            result = await handle_search_wiki(
                {
                    "repo_path": str(tmp_path),
                    "query": "config",
                    "entity_types": ["page"],
                }
            )

        data = json.loads(result[0].text)
        for m in data["matches"]:
            assert m["type"] == "page"

    async def test_search_nonexistent_repo(self, mock_access_control):
        result = await handle_search_wiki(
            {"repo_path": "/nonexistent/path/xyz", "query": "test"}
        )
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text


class TestHandleGetProjectManifest:
    async def test_manifest_found(self, tmp_path, mock_access_control):
        from local_deepwiki.generators.manifest import ProjectManifest

        manifest = ProjectManifest(
            name="test-project",
            version="1.0.0",
            language="Python",
            dependencies={"requests": ">=2.0"},
        )

        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=manifest,
        ):
            result = await handle_get_project_manifest({"repo_path": str(tmp_path)})

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["manifest"]["name"] == "test-project"
        assert data["manifest"]["version"] == "1.0.0"
        assert data["manifest"]["dependencies"] == {"requests": ">=2.0"}

    async def test_no_manifest_files(self, tmp_path, mock_access_control):
        from local_deepwiki.generators.manifest import ProjectManifest

        empty_manifest = ProjectManifest()

        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=empty_manifest,
        ):
            result = await handle_get_project_manifest({"repo_path": str(tmp_path)})

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "No recognized package manifest" in data["message"]

    async def test_nonexistent_repo(self, mock_access_control):
        result = await handle_get_project_manifest(
            {"repo_path": "/nonexistent/path/xyz"}
        )
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_no_cache_option(self, tmp_path, mock_access_control):
        from local_deepwiki.generators.manifest import ProjectManifest

        manifest = ProjectManifest(name="fresh-parse", language="Python")

        with patch(
            "local_deepwiki.generators.manifest.parse_manifest",
            return_value=manifest,
        ):
            result = await handle_get_project_manifest(
                {"repo_path": str(tmp_path), "use_cache": False}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["manifest"]["name"] == "fresh-parse"

    async def test_tech_stack_summary_included(self, tmp_path, mock_access_control):
        from local_deepwiki.generators.manifest import ProjectManifest

        manifest = ProjectManifest(
            name="my-proj", language="Python", language_version="3.12"
        )

        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=manifest,
        ):
            result = await handle_get_project_manifest({"repo_path": str(tmp_path)})

        data = json.loads(result[0].text)
        assert "tech_stack_summary" in data["manifest"]


class TestHandleGetFileContext:
    async def test_file_context(self, tmp_path, mock_access_control):
        from local_deepwiki.generators.context_builder import FileContext

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("import os\ndef main(): pass")

        mock_context = FileContext(
            file_path="src/main.py",
            imports=["import os"],
            imported_modules=["os"],
            callers={"main": ["src/cli.py"]},
            related_files=["src/utils.py"],
            type_definitions=["Config: class Config(BaseModel):"],
        )

        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        mock_vector_store = AsyncMock()
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[MagicMock()])

        with (
            patch(
                "local_deepwiki.handlers.analysis_metadata._load_index_status",
                return_value=(index_status, tmp_path / ".deepwiki", config),
            ),
            patch(
                "local_deepwiki.handlers.analysis_metadata._create_vector_store",
                return_value=mock_vector_store,
            ),
            patch(
                "local_deepwiki.generators.context_builder.build_file_context",
                new_callable=AsyncMock,
                return_value=mock_context,
            ),
        ):
            result = await handle_get_file_context(
                {"repo_path": str(tmp_path), "file_path": "src/main.py"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["context"]["imports"] == ["import os"]
        assert data["context"]["callers"] == {"main": ["src/cli.py"]}
        assert data["context"]["related_files"] == ["src/utils.py"]
        assert len(data["context"]["type_definitions"]) == 1

    async def test_file_not_found(self, tmp_path, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with patch(
            "local_deepwiki.handlers.analysis_metadata._load_index_status",
            return_value=(index_status, tmp_path / ".deepwiki", config),
        ):
            result = await handle_get_file_context(
                {"repo_path": str(tmp_path), "file_path": "nonexistent.py"}
            )
            assert "Error" in result[0].text
            assert "does not exist" in result[0].text

    async def test_no_chunks(self, tmp_path, mock_access_control):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "empty.py").write_text("")

        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        mock_vector_store = AsyncMock()
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[])

        with (
            patch(
                "local_deepwiki.handlers.analysis_metadata._load_index_status",
                return_value=(index_status, tmp_path / ".deepwiki", config),
            ),
            patch(
                "local_deepwiki.handlers.analysis_metadata._create_vector_store",
                return_value=mock_vector_store,
            ),
        ):
            result = await handle_get_file_context(
                {"repo_path": str(tmp_path), "file_path": "src/empty.py"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "No indexed chunks" in data["message"]

    async def test_invalid_args_missing_file_path(self, mock_access_control):
        result = await handle_get_file_context({"repo_path": "/tmp/repo"})
        assert "Error" in result[0].text

    async def test_path_traversal_rejected(self, tmp_path, mock_access_control):
        """Path traversal via '../' must be blocked."""
        result = await handle_get_file_context(
            {"repo_path": str(tmp_path), "file_path": "../../etc/passwd"}
        )
        assert "Error" in result[0].text
        assert "traversal" in result[0].text.lower()


class TestHandleFuzzySearch:
    async def test_fuzzy_search_basic(self, tmp_path, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        mock_helper = MagicMock()
        mock_helper.build_name_index = AsyncMock()
        mock_helper.find_similar_names.return_value = [
            ("calculate_sum", 0.92),
            ("calculate_diff", 0.75),
        ]
        mock_helper._name_to_entries = {
            "calculate_sum": [
                MagicMock(
                    file_path="src/math.py", chunk_type=MagicMock(value="function")
                )
            ],
            "calculate_diff": [
                MagicMock(
                    file_path="src/math.py", chunk_type=MagicMock(value="function")
                )
            ],
        }
        mock_helper.get_file_suggestions.return_value = ["src/math.py"]
        mock_helper.get_stats.return_value = {"total_names": 100, "unique_names": 80}

        with (
            patch(
                "local_deepwiki.handlers.analysis_search._load_index_status",
                return_value=(index_status, tmp_path / ".deepwiki", config),
            ),
            patch(
                "local_deepwiki.handlers.analysis_search._create_vector_store",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.core.fuzzy_search.FuzzySearchHelper",
                return_value=mock_helper,
            ),
        ):
            result = await handle_fuzzy_search(
                {"repo_path": str(tmp_path), "query": "calcluate_sum"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total_matches"] == 2
        assert data["matches"][0]["name"] == "calculate_sum"
        assert data["matches"][0]["score"] == 0.92
        assert data["file_suggestions"] == ["src/math.py"]
        assert data["index_stats"]["total_names"] == 100

    async def test_fuzzy_search_no_matches(self, tmp_path, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        mock_helper = MagicMock()
        mock_helper.build_name_index = AsyncMock()
        mock_helper.find_similar_names.return_value = []
        mock_helper._name_to_entries = {}
        mock_helper.get_file_suggestions.return_value = []
        mock_helper.get_stats.return_value = {"total_names": 0, "unique_names": 0}

        with (
            patch(
                "local_deepwiki.handlers.analysis_search._load_index_status",
                return_value=(index_status, tmp_path / ".deepwiki", config),
            ),
            patch(
                "local_deepwiki.handlers.analysis_search._create_vector_store",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.core.fuzzy_search.FuzzySearchHelper",
                return_value=mock_helper,
            ),
        ):
            result = await handle_fuzzy_search(
                {"repo_path": str(tmp_path), "query": "zzzzz"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total_matches"] == 0
        assert "hint" in data
        assert "lower the threshold" in data["hint"]

    async def test_fuzzy_search_with_entity_type(self, tmp_path, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        mock_helper = MagicMock()
        mock_helper.build_name_index = AsyncMock()
        mock_helper.find_similar_names.return_value = [("MyClass", 0.9)]
        mock_helper._name_to_entries = {
            "MyClass": [
                MagicMock(
                    file_path="src/models.py", chunk_type=MagicMock(value="class")
                )
            ],
        }
        mock_helper.get_file_suggestions.return_value = []
        mock_helper.get_stats.return_value = {"total_names": 50, "unique_names": 50}

        with (
            patch(
                "local_deepwiki.handlers.analysis_search._load_index_status",
                return_value=(index_status, tmp_path / ".deepwiki", config),
            ),
            patch(
                "local_deepwiki.handlers.analysis_search._create_vector_store",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.core.fuzzy_search.FuzzySearchHelper",
                return_value=mock_helper,
            ),
        ):
            result = await handle_fuzzy_search(
                {
                    "repo_path": str(tmp_path),
                    "query": "MyClss",
                    "entity_type": "class",
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["matches"][0]["name"] == "MyClass"

    async def test_nonexistent_repo(self, mock_access_control):
        result = await handle_fuzzy_search(
            {"repo_path": "/nonexistent/path/xyz", "query": "test"}
        )
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text


class TestHandleGetWikiStats:
    async def test_full_stats(self, tmp_path, wiki_dir, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with patch(
            "local_deepwiki.handlers.analysis_metadata._load_index_status",
            return_value=(index_status, wiki_dir, config),
        ):
            result = await handle_get_wiki_stats({"repo_path": str(tmp_path)})

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["index"]["total_files"] == 10
        assert data["index"]["total_chunks"] == 100
        assert data["wiki_pages"]["total_pages"] == 2
        assert data["search_index"]["total_page_entries"] == 2
        assert data["search_index"]["total_entity_entries"] == 2
        assert data["total_wiki_files"] >= 1
        assert data["manifest_cached"] is False
        assert "wiki_status" in data

    async def test_minimal_stats(self, tmp_path, mock_access_control):
        """Test stats with only index_status (no JSON files)."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with patch(
            "local_deepwiki.handlers.analysis_metadata._load_index_status",
            return_value=(index_status, wiki_path, config),
        ):
            result = await handle_get_wiki_stats({"repo_path": str(tmp_path)})

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["index"]["total_files"] == 10
        assert data["wiki_pages"]["total_pages"] == 0
        assert data["manifest_cached"] is False
        assert "wiki_status" not in data

    async def test_nonexistent_repo(self, mock_access_control):
        result = await handle_get_wiki_stats({"repo_path": "/nonexistent/path/xyz"})
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_includes_coverage(self, tmp_path, mock_access_control):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "coverage.json").write_text(
            json.dumps({"documented_files": 8, "total_files": 10, "coverage": 0.80})
        )

        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with patch(
            "local_deepwiki.handlers.analysis_metadata._load_index_status",
            return_value=(index_status, wiki_path, config),
        ):
            result = await handle_get_wiki_stats({"repo_path": str(tmp_path)})

        data = json.loads(result[0].text)
        # Verify curated coverage output
        assert data["coverage"]["documented_percentage"] == 80.0
        assert data["coverage"]["total_entities"] == 10
        assert data["coverage"]["documented_entities"] == 8
        assert data["coverage"]["undocumented_entities"] == 2


# ── Tool registration tests ──────────────────────────────────────────


class TestToolRegistration:
    def test_all_new_tools_in_handlers(self):
        from local_deepwiki.server import TOOL_HANDLERS

        new_tools = [
            "search_wiki",
            "get_project_manifest",
            "get_file_context",
            "fuzzy_search",
            "get_wiki_stats",
        ]
        for tool in new_tools:
            assert tool in TOOL_HANDLERS, f"{tool} not registered in TOOL_HANDLERS"

    async def test_list_tools_includes_new_tools(self):
        from local_deepwiki.server import list_tools

        tools = await list_tools()
        tool_names = {t.name for t in tools}

        new_tools = [
            "search_wiki",
            "get_project_manifest",
            "get_file_context",
            "fuzzy_search",
            "get_wiki_stats",
        ]
        for tool in new_tools:
            assert tool in tool_names, f"{tool} not in list_tools()"

    async def test_tool_schemas_have_required_fields(self):
        """Verify each new tool has proper inputSchema."""
        from local_deepwiki.server import list_tools

        tools = await list_tools()
        new_tool_names = {
            "search_wiki",
            "get_project_manifest",
            "get_file_context",
            "fuzzy_search",
            "get_wiki_stats",
        }

        for tool in tools:
            if tool.name in new_tool_names:
                schema = tool.inputSchema
                assert schema["type"] == "object"
                assert "properties" in schema
                assert "repo_path" in schema["properties"]
                assert "required" in schema
                assert "repo_path" in schema["required"]
