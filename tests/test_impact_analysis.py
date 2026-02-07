"""Tests for the impact_analysis MCP tool handler."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.handlers import handle_impact_analysis


@pytest.fixture
def mock_access_control():
    with patch("local_deepwiki.handlers.get_access_controller") as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def mock_index_status(tmp_path):
    status = MagicMock()
    status.repo_path = str(tmp_path)
    status.indexed_at = 1700000000.0
    status.total_files = 10
    status.total_chunks = 50
    status.languages = {"python": 10}
    status.schema_version = 2
    status.file_hashes = {}
    status.files = []
    return status


@pytest.fixture
def mock_config(tmp_path):
    config = MagicMock()
    config.embedding = MagicMock()
    config.get_vector_db_path.return_value = tmp_path / "vectordb"
    config.get_wiki_path.return_value = tmp_path / ".deepwiki"
    return config


@pytest.fixture
def setup_repo(tmp_path):
    """Create a minimal repo structure with a target file and wiki dir."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    target_file = src_dir / "server.py"
    target_file.write_text("def handle_request(): pass\n")

    wiki_dir = tmp_path / ".deepwiki"
    wiki_dir.mkdir()

    return tmp_path, src_dir, target_file, wiki_dir


def _write_toc(wiki_dir: Path, pages: list[dict]) -> None:
    """Write toc.json to the wiki directory."""
    (wiki_dir / "toc.json").write_text(json.dumps(pages))


class TestImpactAnalysisBasic:
    """Test basic impact analysis with callers and dependents."""

    async def test_impact_analysis_basic(
        self, setup_repo, mock_access_control, mock_index_status, mock_config
    ):
        tmp_path, _src_dir, _target_file, wiki_dir = setup_repo
        _write_toc(wiki_dir, [])

        mock_reverse_graph = {
            "handle_request": ["router.dispatch", "tests.test_handle"],
        }
        mock_call_graph = {
            "router.dispatch": ["handle_request"],
            "tests.test_handle": ["handle_request"],
        }

        @dataclass
        class FakeContext:
            file_path: str = "src/server.py"
            imports: list = field(default_factory=list)
            imported_modules: list = field(default_factory=list)
            callers: dict = field(
                default_factory=lambda: {
                    "handle_request": ["src/router.py", "tests/test_server.py"]
                }
            )
            related_files: list = field(default_factory=lambda: ["src/utils.py"])
            type_definitions: list = field(default_factory=list)

        mock_vector_store = AsyncMock()
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[MagicMock()])

        with (
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor.extract_from_file",
                return_value=mock_call_graph,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value=mock_reverse_graph,
            ),
            patch(
                "local_deepwiki.generators.inheritance.collect_class_hierarchy",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.context_builder.build_file_context",
                new_callable=AsyncMock,
                return_value=FakeContext(),
            ),
            patch("local_deepwiki.handlers.get_embedding_provider"),
            patch(
                "local_deepwiki.handlers.VectorStore",
                return_value=mock_vector_store,
            ),
        ):
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "src/server.py",
                }
            )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["file_path"] == "src/server.py"
        assert "reverse_call_graph" in data
        assert "handle_request" in data["reverse_call_graph"]
        assert "file_dependents" in data
        assert "src/router.py" in data["file_dependents"]["importing_files"]
        assert data["impact_summary"]["risk_level"] in ("low", "medium", "high")
        assert data["impact_summary"]["total_affected_files"] >= 1


class TestImpactAnalysisWithEntityName:
    """Test narrowing analysis to a specific entity."""

    async def test_impact_analysis_with_entity_name(
        self, setup_repo, mock_access_control, mock_index_status, mock_config
    ):
        tmp_path, _src_dir, _target_file, wiki_dir = setup_repo
        _write_toc(wiki_dir, [])

        mock_reverse_graph = {
            "handle_request": ["router.dispatch"],
            "other_func": ["some_caller"],
        }

        mock_vector_store = AsyncMock()
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[])

        with (
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor.extract_from_file",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value=mock_reverse_graph,
            ),
            patch(
                "local_deepwiki.generators.inheritance.collect_class_hierarchy",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("local_deepwiki.handlers.get_embedding_provider"),
            patch(
                "local_deepwiki.handlers.VectorStore",
                return_value=mock_vector_store,
            ),
        ):
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "src/server.py",
                    "entity_name": "handle_request",
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["entity_name"] == "handle_request"
        # Should only contain the filtered entity
        assert "handle_request" in data["reverse_call_graph"]
        assert "other_func" not in data["reverse_call_graph"]


class TestImpactAnalysisNoCallers:
    """Test file with no external callers."""

    async def test_impact_analysis_no_callers(
        self, setup_repo, mock_access_control, mock_index_status, mock_config
    ):
        tmp_path, _src_dir, _target_file, wiki_dir = setup_repo
        _write_toc(wiki_dir, [])

        mock_vector_store = AsyncMock()
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[])

        with (
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor.extract_from_file",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.inheritance.collect_class_hierarchy",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("local_deepwiki.handlers.get_embedding_provider"),
            patch(
                "local_deepwiki.handlers.VectorStore",
                return_value=mock_vector_store,
            ),
        ):
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "src/server.py",
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["reverse_call_graph"] == {}
        assert data["inheritance_dependents"] == {}
        assert data["impact_summary"]["total_affected_files"] == 0
        assert data["impact_summary"]["risk_level"] == "low"


class TestImpactAnalysisWithInheritance:
    """Test file with classes that have children in other files."""

    async def test_impact_analysis_with_inheritance(
        self, setup_repo, mock_access_control, mock_index_status, mock_config
    ):
        tmp_path, _src_dir, _target_file, wiki_dir = setup_repo
        _write_toc(wiki_dir, [])

        @dataclass
        class FakeClassNode:
            name: str
            file_path: str
            parents: list = field(default_factory=list)
            children: list = field(default_factory=list)
            is_abstract: bool = False
            docstring: str | None = None

        classes = {
            "BaseHandler": FakeClassNode(
                name="BaseHandler",
                file_path="src/server.py",
                children=["ChildHandler", "OtherHandler"],
            ),
            "ChildHandler": FakeClassNode(
                name="ChildHandler",
                file_path="src/child.py",
                parents=["BaseHandler"],
            ),
            "OtherHandler": FakeClassNode(
                name="OtherHandler",
                file_path="src/other.py",
                parents=["BaseHandler"],
            ),
        }

        mock_vector_store = AsyncMock()
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[])

        with (
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor.extract_from_file",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.inheritance.collect_class_hierarchy",
                new_callable=AsyncMock,
                return_value=classes,
            ),
            patch("local_deepwiki.handlers.get_embedding_provider"),
            patch(
                "local_deepwiki.handlers.VectorStore",
                return_value=mock_vector_store,
            ),
        ):
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "src/server.py",
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "BaseHandler" in data["inheritance_dependents"]
        children = data["inheritance_dependents"]["BaseHandler"]
        # Children from other files should be qualified with file path
        assert any("ChildHandler" in c for c in children)
        assert any("OtherHandler" in c for c in children)
        assert data["impact_summary"]["total_affected_files"] >= 2


class TestImpactAnalysisDisableSections:
    """Test disabling individual include flags."""

    async def test_impact_analysis_disable_sections(
        self, setup_repo, mock_access_control, mock_index_status, mock_config
    ):
        tmp_path, _src_dir, _target_file, wiki_dir = setup_repo
        _write_toc(wiki_dir, [])

        with (
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
        ):
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "src/server.py",
                    "include_reverse_calls": False,
                    "include_dependents": False,
                    "include_inheritance": False,
                    "include_wiki_pages": False,
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "reverse_call_graph" not in data
        assert "inheritance_dependents" not in data
        assert "file_dependents" not in data
        assert "affected_wiki_pages" not in data
        assert data["impact_summary"]["total_affected_files"] == 0
        assert data["impact_summary"]["risk_level"] == "low"


class TestImpactAnalysisWikiPages:
    """Test matching wiki pages."""

    async def test_impact_analysis_wiki_pages_found(
        self, setup_repo, mock_access_control, mock_index_status, mock_config
    ):
        tmp_path, _src_dir, _target_file, wiki_dir = setup_repo

        toc_data = [
            {
                "title": "Server Module",
                "path": "files/src/server.md",
                "source_file": "src/server.py",
            },
            {
                "title": "Parser Module",
                "path": "files/src/parser.md",
                "source_file": "src/parser.py",
            },
        ]
        _write_toc(wiki_dir, toc_data)

        with (
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
        ):
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "src/server.py",
                    "include_reverse_calls": False,
                    "include_dependents": False,
                    "include_inheritance": False,
                    "include_wiki_pages": True,
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert len(data["affected_wiki_pages"]) == 1
        assert data["affected_wiki_pages"][0]["title"] == "Server Module"
        assert data["affected_wiki_pages"][0]["path"] == "files/src/server.md"


class TestImpactAnalysisFileNotFound:
    """Test nonexistent file."""

    async def test_impact_analysis_file_not_found(
        self, tmp_path, mock_access_control, mock_index_status, mock_config
    ):
        # tmp_path exists but has no src/nonexistent.py
        wiki_dir = tmp_path / ".deepwiki"
        wiki_dir.mkdir()

        with (
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
        ):
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "src/nonexistent.py",
                }
            )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text


class TestImpactAnalysisRepoNotFound:
    """Test nonexistent repo."""

    async def test_impact_analysis_repo_not_found(self, tmp_path, mock_access_control):
        nonexistent = tmp_path / "does_not_exist"

        result = await handle_impact_analysis(
            {
                "repo_path": str(nonexistent),
                "file_path": "src/server.py",
            }
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text


class TestImpactAnalysisRiskLevels:
    """Test low/medium/high risk level thresholds."""

    async def test_impact_analysis_risk_low(
        self, setup_repo, mock_access_control, mock_index_status, mock_config
    ):
        """0-2 affected files = low risk."""
        tmp_path, _src_dir, _target_file, wiki_dir = setup_repo
        _write_toc(wiki_dir, [])

        # No callers, no dependents -> 0 affected files
        mock_vector_store = AsyncMock()
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[])

        with (
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor.extract_from_file",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.inheritance.collect_class_hierarchy",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("local_deepwiki.handlers.get_embedding_provider"),
            patch(
                "local_deepwiki.handlers.VectorStore",
                return_value=mock_vector_store,
            ),
        ):
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "src/server.py",
                }
            )

        data = json.loads(result[0].text)
        assert data["impact_summary"]["risk_level"] == "low"

    async def test_impact_analysis_risk_medium(
        self, setup_repo, mock_access_control, mock_index_status, mock_config
    ):
        """3-10 affected files = medium risk."""
        tmp_path, _src_dir, _target_file, wiki_dir = setup_repo
        _write_toc(wiki_dir, [])

        # Create callers from 5 different file prefixes
        reverse_graph = {
            "func": [
                "mod_a.caller1",
                "mod_b.caller2",
                "mod_c.caller3",
                "mod_d.caller4",
                "mod_e.caller5",
            ]
        }

        mock_vector_store = AsyncMock()
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[])

        with (
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor.extract_from_file",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value=reverse_graph,
            ),
            patch(
                "local_deepwiki.generators.inheritance.collect_class_hierarchy",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("local_deepwiki.handlers.get_embedding_provider"),
            patch(
                "local_deepwiki.handlers.VectorStore",
                return_value=mock_vector_store,
            ),
        ):
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "src/server.py",
                }
            )

        data = json.loads(result[0].text)
        assert data["impact_summary"]["total_affected_files"] >= 3
        assert data["impact_summary"]["risk_level"] == "medium"

    async def test_impact_analysis_risk_high(
        self, setup_repo, mock_access_control, mock_index_status, mock_config
    ):
        """11+ affected files = high risk."""
        tmp_path, _src_dir, _target_file, wiki_dir = setup_repo
        _write_toc(wiki_dir, [])

        # Create callers from 12 different file prefixes
        callers = [f"mod_{i}.caller{i}" for i in range(12)]
        reverse_graph = {"func": callers}

        mock_vector_store = AsyncMock()
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[])

        with (
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor.extract_from_file",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value=reverse_graph,
            ),
            patch(
                "local_deepwiki.generators.inheritance.collect_class_hierarchy",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("local_deepwiki.handlers.get_embedding_provider"),
            patch(
                "local_deepwiki.handlers.VectorStore",
                return_value=mock_vector_store,
            ),
        ):
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "src/server.py",
                }
            )

        data = json.loads(result[0].text)
        assert data["impact_summary"]["total_affected_files"] >= 11
        assert data["impact_summary"]["risk_level"] == "high"


class TestImpactAnalysisValidationError:
    """Test validation errors."""

    async def test_impact_analysis_missing_required_fields(self, mock_access_control):
        """Missing repo_path and file_path should error."""
        result = await handle_impact_analysis({})

        assert len(result) == 1
        assert "Error" in result[0].text

    async def test_impact_analysis_empty_file_path(self, mock_access_control):
        """Empty file_path should fail min_length validation."""
        result = await handle_impact_analysis(
            {
                "repo_path": "/some/path",
                "file_path": "",
            }
        )

        assert len(result) == 1
        assert "Error" in result[0].text

    async def test_impact_analysis_path_traversal(
        self, tmp_path, mock_access_control, mock_index_status, mock_config
    ):
        """Path traversal in file_path should be rejected."""
        wiki_dir = tmp_path / ".deepwiki"
        wiki_dir.mkdir()

        with patch("local_deepwiki.handlers._load_index_status") as mock_load:
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "../../etc/passwd",
                }
            )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "traversal" in result[0].text


class TestImpactAnalysisTocFormats:
    """Test handling of different toc.json formats."""

    async def test_toc_as_dict_with_pages_key(
        self, setup_repo, mock_access_control, mock_index_status, mock_config
    ):
        """toc.json can be {'pages': [...]} instead of a plain list."""
        tmp_path, _src_dir, _target_file, wiki_dir = setup_repo

        toc_data = {
            "pages": [
                {
                    "title": "Server Module",
                    "path": "files/src/server.md",
                    "source_file": "src/server.py",
                },
            ]
        }
        (wiki_dir / "toc.json").write_text(json.dumps(toc_data))

        with patch("local_deepwiki.handlers._load_index_status") as mock_load:
            mock_load.return_value = (mock_index_status, wiki_dir, mock_config)

            result = await handle_impact_analysis(
                {
                    "repo_path": str(tmp_path),
                    "file_path": "src/server.py",
                    "include_reverse_calls": False,
                    "include_dependents": False,
                    "include_inheritance": False,
                    "include_wiki_pages": True,
                }
            )

        data = json.loads(result[0].text)
        assert len(data["affected_wiki_pages"]) == 1
        assert data["affected_wiki_pages"][0]["title"] == "Server Module"
