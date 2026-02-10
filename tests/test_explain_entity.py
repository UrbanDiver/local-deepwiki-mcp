"""Tests for the explain_entity MCP tool."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.handlers import handle_explain_entity
from local_deepwiki.models import ExplainEntityArgs


# ── Fixtures ────────────────────────────────────────────────────────


def _make_index_status(repo_path="/tmp/repo"):
    """Create a mock IndexStatus."""
    status = MagicMock()
    status.repo_path = repo_path
    status.indexed_at = 1700000000.0
    status.total_files = 10
    status.total_chunks = 50
    status.languages = ["python"]
    status.schema_version = 2
    status.file_hashes = {}
    status.files = []
    return status


def _make_config(tmp_path):
    """Create a mock config."""
    config = MagicMock()
    config.embedding = MagicMock()
    config.get_vector_db_path.return_value = tmp_path / "vectordb"
    config.get_wiki_path.return_value = tmp_path / ".deepwiki"
    return config


def _make_search_json(wiki_path, entities=None):
    """Create a search.json file in the wiki directory."""
    if entities is None:
        entities = [
            {
                "type": "entity",
                "entity_type": "function",
                "name": "parse_config",
                "display_name": "parse_config",
                "path": "files/src/config.md",
                "file": "src/config.py",
                "signature": "(path: str) -> Config",
                "description": "Parse configuration from a YAML file.",
                "is_async": False,
                "raises": [],
                "keywords": ["parse", "config"],
            },
            {
                "type": "entity",
                "entity_type": "class",
                "name": "Config",
                "display_name": "Config",
                "path": "files/src/config.md",
                "file": "src/config.py",
                "signature": "",
                "description": "Configuration container class.",
                "is_async": False,
                "raises": [],
                "keywords": ["config"],
            },
            {
                "type": "entity",
                "entity_type": "method",
                "name": "get_value",
                "display_name": "Config.get_value",
                "path": "files/src/config.md",
                "file": "src/config.py",
                "signature": "(key: str) -> Any",
                "description": "Get a configuration value by key.",
                "is_async": False,
                "raises": ["KeyError"],
                "keywords": ["get", "value"],
            },
        ]

    search_data = {
        "pages": [],
        "entities": entities,
        "meta": {"total_pages": 0, "total_entities": len(entities)},
    }
    (wiki_path / "search.json").write_text(json.dumps(search_data))


@pytest.fixture
def mock_access_control():
    with patch("local_deepwiki.handlers.analysis.get_access_controller") as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def wiki_env(tmp_path):
    """Create a minimal wiki environment with search.json."""
    wiki_path = tmp_path / ".deepwiki"
    wiki_path.mkdir()
    _make_search_json(wiki_path)

    # Create a dummy source file so file existence checks pass
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "config.py").write_text(
        'def parse_config(path: str):\n    """Parse configuration."""\n    pass\n\n'
        'class Config:\n    """Configuration container."""\n    pass\n'
    )

    index_status = _make_index_status(str(tmp_path))
    config = _make_config(tmp_path)

    return {
        "tmp_path": tmp_path,
        "wiki_path": wiki_path,
        "index_status": index_status,
        "config": config,
    }


# ── Args Model Tests ────────────────────────────────────────────────


class TestExplainEntityArgs:
    def test_valid_minimal_args(self):
        args = ExplainEntityArgs(repo_path="/tmp/repo", entity_name="foo")
        assert args.entity_name == "foo"
        assert args.include_call_graph is True
        assert args.include_inheritance is True
        assert args.include_test_examples is True
        assert args.include_api_docs is True
        assert args.max_test_examples == 3

    def test_empty_entity_name_rejected(self):
        with pytest.raises(Exception):
            ExplainEntityArgs(repo_path="/tmp/repo", entity_name="")

    def test_max_test_examples_bounds(self):
        args = ExplainEntityArgs(
            repo_path="/tmp/repo", entity_name="foo", max_test_examples=10
        )
        assert args.max_test_examples == 10
        with pytest.raises(Exception):
            ExplainEntityArgs(
                repo_path="/tmp/repo", entity_name="foo", max_test_examples=0
            )
        with pytest.raises(Exception):
            ExplainEntityArgs(
                repo_path="/tmp/repo", entity_name="foo", max_test_examples=11
            )

    def test_disable_all_sections(self):
        args = ExplainEntityArgs(
            repo_path="/tmp/repo",
            entity_name="foo",
            include_call_graph=False,
            include_inheritance=False,
            include_test_examples=False,
            include_api_docs=False,
        )
        assert args.include_call_graph is False
        assert args.include_inheritance is False
        assert args.include_test_examples is False
        assert args.include_api_docs is False


# ── Handler Tests ───────────────────────────────────────────────────


class TestHandleExplainEntityBasic:
    """test_explain_entity_basic - entity found, all sections included."""

    async def test_entity_found_all_sections(self, mock_access_control, wiki_env):
        env = wiki_env
        mock_call_graph = {"parse_config": ["open", "yaml_load"]}
        mock_reverse = {"parse_config": ["main", "test_parse"]}

        mock_extractor_instance = MagicMock()
        mock_extractor_instance.extract_from_file.return_value = mock_call_graph

        mock_example = MagicMock()
        mock_example.code = "result = parse_config('config.yaml')"
        mock_example.test_file = "tests/test_config.py"
        mock_example.description = "Test basic parsing"

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_function = AsyncMock(
            return_value=[mock_example]
        )

        mock_func_sig = MagicMock()
        mock_func_sig.name = "parse_config"
        mock_func_sig.parameters = []
        mock_func_sig.return_type = "Config"
        mock_func_sig.docstring = "Parse configuration from a YAML file."
        mock_func_sig.is_async = False
        mock_func_sig.decorators = []

        mock_api_extractor = MagicMock()
        mock_api_extractor.extract_from_file.return_value = ([mock_func_sig], [])

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_extractor_instance,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value=mock_reverse,
            ),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
        ):
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {"repo_path": str(env["tmp_path"]), "entity_name": "parse_config"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["entity_found"] is True
        assert data["entity_info"]["type"] == "function"
        assert data["entity_info"]["file"] == "src/config.py"
        assert "call_graph" in data
        assert "test_examples" in data
        assert "api_docs" in data


class TestHandleExplainEntityNotFound:
    """test_explain_entity_not_found - entity not in search.json."""

    async def test_entity_not_in_search_index(self, mock_access_control, wiki_env):
        env = wiki_env

        with patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load:
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {"repo_path": str(env["tmp_path"]), "entity_name": "nonexistent_func"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["entity_found"] is False
        assert "nonexistent_func" in data["message"]


class TestHandleExplainEntityClassInheritance:
    """test_explain_entity_class_with_inheritance - class entity includes inheritance."""

    async def test_class_includes_inheritance(self, mock_access_control, wiki_env):
        env = wiki_env

        mock_class_node = MagicMock()
        mock_class_node.parents = ["BaseConfig"]
        mock_class_node.children = ["SpecialConfig"]
        mock_class_node.is_abstract = False

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_class = AsyncMock(return_value=[])

        mock_api_extractor = MagicMock()
        mock_cls_sig = MagicMock()
        mock_cls_sig.name = "Config"
        mock_cls_sig.bases = ["BaseConfig"]
        mock_cls_sig.docstring = "Configuration container."
        mock_cls_sig.description = "Configuration container."
        mock_cls_sig.methods = []
        mock_cls_sig.class_variables = []
        mock_api_extractor.extract_from_file.return_value = ([], [mock_cls_sig])

        mock_cg_extractor = MagicMock()
        mock_cg_extractor.extract_from_file.return_value = {}

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.inheritance.collect_class_hierarchy",
                new_callable=AsyncMock,
                return_value={"Config": mock_class_node},
            ),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_cg_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
        ):
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {"repo_path": str(env["tmp_path"]), "entity_name": "Config"}
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        assert data["entity_info"]["type"] == "class"
        assert "inheritance" in data
        assert data["inheritance"]["parents"] == ["BaseConfig"]
        assert data["inheritance"]["children"] == ["SpecialConfig"]
        assert data["inheritance"]["is_abstract"] is False


class TestHandleExplainEntityFunctionNoInheritance:
    """test_explain_entity_function_no_inheritance - function entity skips inheritance."""

    async def test_function_skips_inheritance(self, mock_access_control, wiki_env):
        env = wiki_env

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_function = AsyncMock(
            return_value=[]
        )
        mock_example_extractor.extract_examples_for_class = AsyncMock(return_value=[])

        mock_func_sig = MagicMock()
        mock_func_sig.name = "parse_config"
        mock_func_sig.parameters = []
        mock_func_sig.return_type = "Config"
        mock_func_sig.docstring = "Parse configuration."
        mock_func_sig.is_async = False
        mock_func_sig.decorators = []

        mock_api_extractor = MagicMock()
        mock_api_extractor.extract_from_file.return_value = ([mock_func_sig], [])

        mock_cg_extractor = MagicMock()
        mock_cg_extractor.extract_from_file.return_value = {}

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_cg_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
        ):
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {"repo_path": str(env["tmp_path"]), "entity_name": "parse_config"}
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        assert data["entity_info"]["type"] == "function"
        # Inheritance should NOT be present for a function
        assert "inheritance" not in data


class TestHandleExplainEntityDisableCallGraph:
    """test_explain_entity_disable_call_graph - include_call_graph=False."""

    async def test_call_graph_excluded(self, mock_access_control, wiki_env):
        env = wiki_env

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_function = AsyncMock(
            return_value=[]
        )
        mock_example_extractor.extract_examples_for_class = AsyncMock(return_value=[])

        mock_api_extractor = MagicMock()
        mock_func_sig = MagicMock()
        mock_func_sig.name = "parse_config"
        mock_func_sig.parameters = []
        mock_func_sig.return_type = "Config"
        mock_func_sig.docstring = "Parse."
        mock_func_sig.is_async = False
        mock_func_sig.decorators = []
        mock_api_extractor.extract_from_file.return_value = ([mock_func_sig], [])

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
        ):
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {
                    "repo_path": str(env["tmp_path"]),
                    "entity_name": "parse_config",
                    "include_call_graph": False,
                }
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        assert "call_graph" not in data


class TestHandleExplainEntityDisableTestExamples:
    """test_explain_entity_disable_test_examples - include_test_examples=False."""

    async def test_test_examples_excluded(self, mock_access_control, wiki_env):
        env = wiki_env

        mock_cg_extractor = MagicMock()
        mock_cg_extractor.extract_from_file.return_value = {}

        mock_api_extractor = MagicMock()
        mock_func_sig = MagicMock()
        mock_func_sig.name = "parse_config"
        mock_func_sig.parameters = []
        mock_func_sig.return_type = "Config"
        mock_func_sig.docstring = "Parse."
        mock_func_sig.is_async = False
        mock_func_sig.decorators = []
        mock_api_extractor.extract_from_file.return_value = ([mock_func_sig], [])

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_cg_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
        ):
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {
                    "repo_path": str(env["tmp_path"]),
                    "entity_name": "parse_config",
                    "include_test_examples": False,
                }
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        assert "test_examples" not in data


class TestHandleExplainEntityRepoNotFound:
    """test_explain_entity_repo_not_found - nonexistent repo path."""

    async def test_nonexistent_repo(self, mock_access_control):
        result = await handle_explain_entity(
            {"repo_path": "/nonexistent/repo/path", "entity_name": "foo"}
        )

        data_text = result[0].text
        assert "Error" in data_text


class TestHandleExplainEntityValidationError:
    """test_explain_entity_validation_error - missing required fields."""

    async def test_missing_entity_name(self, mock_access_control):
        result = await handle_explain_entity({"repo_path": "/tmp/repo"})

        data_text = result[0].text
        assert "Error" in data_text

    async def test_missing_repo_path(self, mock_access_control):
        result = await handle_explain_entity({"entity_name": "foo"})

        data_text = result[0].text
        assert "Error" in data_text

    async def test_empty_args(self, mock_access_control):
        result = await handle_explain_entity({})

        data_text = result[0].text
        assert "Error" in data_text

    async def test_max_examples_out_of_range(self, mock_access_control):
        result = await handle_explain_entity(
            {
                "repo_path": "/tmp/repo",
                "entity_name": "foo",
                "max_test_examples": 99,
            }
        )

        data_text = result[0].text
        assert "Error" in data_text


# ── Additional Coverage Tests ──────────────────────────────────────


class TestExplainEntityMultipleMatches:
    """Test entity found in multiple files (first match wins)."""

    async def test_entity_in_multiple_files(self, mock_access_control, tmp_path):
        """When an entity name appears in multiple files, the first match is used."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        entities = [
            {
                "type": "entity",
                "entity_type": "function",
                "name": "process",
                "display_name": "process",
                "path": "files/src/moduleA.md",
                "file": "src/moduleA.py",
                "signature": "(data: list) -> list",
                "description": "Process data in module A.",
                "is_async": False,
                "raises": [],
                "keywords": ["process"],
            },
            {
                "type": "entity",
                "entity_type": "function",
                "name": "process",
                "display_name": "process",
                "path": "files/src/moduleB.md",
                "file": "src/moduleB.py",
                "signature": "(item: dict) -> dict",
                "description": "Process data in module B.",
                "is_async": False,
                "raises": [],
                "keywords": ["process"],
            },
        ]
        _make_search_json(wiki_path, entities)

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "moduleA.py").write_text("def process(data): pass\n")
        (src_dir / "moduleB.py").write_text("def process(item): pass\n")

        index_status = _make_index_status(str(tmp_path))
        config = _make_config(tmp_path)

        mock_cg_extractor = MagicMock()
        mock_cg_extractor.extract_from_file.return_value = {}

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_function = AsyncMock(
            return_value=[]
        )

        mock_func_sig = MagicMock()
        mock_func_sig.name = "process"
        mock_func_sig.parameters = []
        mock_func_sig.return_type = "list"
        mock_func_sig.docstring = "Process data."
        mock_func_sig.is_async = False
        mock_func_sig.decorators = []

        mock_api_extractor = MagicMock()
        mock_api_extractor.extract_from_file.return_value = ([mock_func_sig], [])

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_cg_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
        ):
            mock_load.return_value = (index_status, wiki_path, config)

            result = await handle_explain_entity(
                {"repo_path": str(tmp_path), "entity_name": "process"}
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        # First match is moduleA
        assert data["entity_info"]["file"] == "src/moduleA.py"


class TestExplainEntityMethodEntity:
    """Test method entity includes parent class context."""

    async def test_method_shows_class_context(self, mock_access_control, wiki_env):
        """A method entity should have its class_name in api_docs."""
        env = wiki_env

        mock_method_sig = MagicMock()
        mock_method_sig.name = "get_value"
        mock_method_sig.parameters = []
        mock_method_sig.return_type = "Any"
        mock_method_sig.docstring = "Get a configuration value."
        mock_method_sig.is_async = False
        mock_method_sig.decorators = []

        mock_cls_sig = MagicMock()
        mock_cls_sig.name = "Config"
        mock_cls_sig.methods = [mock_method_sig]
        mock_cls_sig.bases = []
        mock_cls_sig.class_variables = []

        mock_api_extractor = MagicMock()
        mock_api_extractor.extract_from_file.return_value = ([], [mock_cls_sig])

        mock_cg_extractor = MagicMock()
        mock_cg_extractor.extract_from_file.return_value = {}

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_function = AsyncMock(
            return_value=[]
        )
        mock_example_extractor.extract_examples_for_class = AsyncMock(return_value=[])

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_cg_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
        ):
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {"repo_path": str(env["tmp_path"]), "entity_name": "get_value"}
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        assert data["entity_info"]["type"] == "method"
        assert "api_docs" in data
        assert data["api_docs"]["class_name"] == "Config"


class TestExplainEntityNoDocstring:
    """Test entity with no docstring still works."""

    async def test_entity_no_docstring(self, mock_access_control, wiki_env):
        env = wiki_env

        mock_func_sig = MagicMock()
        mock_func_sig.name = "parse_config"
        mock_func_sig.parameters = []
        mock_func_sig.return_type = "Config"
        mock_func_sig.docstring = None
        mock_func_sig.is_async = False
        mock_func_sig.decorators = []

        mock_api_extractor = MagicMock()
        mock_api_extractor.extract_from_file.return_value = ([mock_func_sig], [])

        mock_cg_extractor = MagicMock()
        mock_cg_extractor.extract_from_file.return_value = {}

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_function = AsyncMock(
            return_value=[]
        )

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_cg_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
        ):
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {"repo_path": str(env["tmp_path"]), "entity_name": "parse_config"}
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        assert data["api_docs"]["docstring"] is None


class TestExplainEntityAsyncFunction:
    """Test async entity shows is_async in api_docs."""

    async def test_async_entity(self, mock_access_control, tmp_path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        entities = [
            {
                "type": "entity",
                "entity_type": "function",
                "name": "async_fetch",
                "display_name": "async_fetch",
                "path": "files/src/fetcher.md",
                "file": "src/fetcher.py",
                "signature": "(url: str) -> bytes",
                "description": "Fetch data asynchronously.",
                "is_async": True,
                "raises": [],
                "keywords": ["fetch", "async"],
            },
        ]
        _make_search_json(wiki_path, entities)

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "fetcher.py").write_text("async def async_fetch(url): pass\n")

        index_status = _make_index_status(str(tmp_path))
        config = _make_config(tmp_path)

        mock_func_sig = MagicMock()
        mock_func_sig.name = "async_fetch"
        mock_func_sig.parameters = []
        mock_func_sig.return_type = "bytes"
        mock_func_sig.docstring = "Fetch data."
        mock_func_sig.is_async = True
        mock_func_sig.decorators = []

        mock_api_extractor = MagicMock()
        mock_api_extractor.extract_from_file.return_value = ([mock_func_sig], [])

        mock_cg_extractor = MagicMock()
        mock_cg_extractor.extract_from_file.return_value = {}

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_function = AsyncMock(
            return_value=[]
        )

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_cg_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
        ):
            mock_load.return_value = (index_status, wiki_path, config)

            result = await handle_explain_entity(
                {"repo_path": str(tmp_path), "entity_name": "async_fetch"}
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        assert data["api_docs"]["is_async"] is True


class TestExplainEntityNoCallersCallees:
    """Test entity with no callers or callees returns empty lists."""

    async def test_empty_call_graph(self, mock_access_control, wiki_env):
        env = wiki_env

        mock_cg_extractor = MagicMock()
        mock_cg_extractor.extract_from_file.return_value = {}

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_function = AsyncMock(
            return_value=[]
        )

        mock_func_sig = MagicMock()
        mock_func_sig.name = "parse_config"
        mock_func_sig.parameters = []
        mock_func_sig.return_type = "Config"
        mock_func_sig.docstring = "Parse."
        mock_func_sig.is_async = False
        mock_func_sig.decorators = []

        mock_api_extractor = MagicMock()
        mock_api_extractor.extract_from_file.return_value = ([mock_func_sig], [])

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_cg_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
        ):
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {"repo_path": str(env["tmp_path"]), "entity_name": "parse_config"}
            )

        data = json.loads(result[0].text)
        assert data["call_graph"]["calls"] == []
        assert data["call_graph"]["called_by"] == []


class TestExplainEntityDisableApiDocs:
    """Test include_api_docs=False omits api_docs section."""

    async def test_api_docs_excluded(self, mock_access_control, wiki_env):
        env = wiki_env

        mock_cg_extractor = MagicMock()
        mock_cg_extractor.extract_from_file.return_value = {}

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_function = AsyncMock(
            return_value=[]
        )

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_cg_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
        ):
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {
                    "repo_path": str(env["tmp_path"]),
                    "entity_name": "parse_config",
                    "include_api_docs": False,
                }
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        assert "api_docs" not in data


class TestExplainEntityAllSectionsDisabled:
    """Test with all optional sections disabled."""

    async def test_all_disabled(self, mock_access_control, wiki_env):
        env = wiki_env

        with patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load:
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {
                    "repo_path": str(env["tmp_path"]),
                    "entity_name": "parse_config",
                    "include_call_graph": False,
                    "include_inheritance": False,
                    "include_test_examples": False,
                    "include_api_docs": False,
                }
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        assert "call_graph" not in data
        assert "inheritance" not in data
        assert "test_examples" not in data
        assert "api_docs" not in data
        # Basic info should still be present
        assert data["entity_info"]["type"] == "function"


class TestExplainEntityClassNotInHierarchy:
    """Test class entity not found in inheritance hierarchy."""

    async def test_class_not_in_hierarchy(self, mock_access_control, wiki_env):
        env = wiki_env

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_class = AsyncMock(return_value=[])

        mock_api_extractor = MagicMock()
        mock_cls_sig = MagicMock()
        mock_cls_sig.name = "Config"
        mock_cls_sig.bases = []
        mock_cls_sig.docstring = "Config."
        mock_cls_sig.description = "Config."
        mock_cls_sig.methods = []
        mock_cls_sig.class_variables = []
        mock_api_extractor.extract_from_file.return_value = ([], [mock_cls_sig])

        mock_cg_extractor = MagicMock()
        mock_cg_extractor.extract_from_file.return_value = {}

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.inheritance.collect_class_hierarchy",
                new_callable=AsyncMock,
                return_value={},  # Empty hierarchy
            ),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_cg_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value={},
            ),
        ):
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {"repo_path": str(env["tmp_path"]), "entity_name": "Config"}
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        assert data["entity_info"]["type"] == "class"
        assert data["inheritance"]["note"] == "Class not found in inheritance hierarchy"
        assert data["inheritance"]["parents"] == []
        assert data["inheritance"]["children"] == []


class TestExplainEntityEmptySearchJson:
    """Test with empty search.json (no entities at all)."""

    async def test_empty_search_index(self, mock_access_control, tmp_path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        _make_search_json(wiki_path, entities=[])

        index_status = _make_index_status(str(tmp_path))
        config = _make_config(tmp_path)

        with patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load:
            mock_load.return_value = (index_status, wiki_path, config)

            result = await handle_explain_entity(
                {"repo_path": str(tmp_path), "entity_name": "anything"}
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is False
        assert "anything" in data["message"]


class TestExplainEntityCallGraphWithCallersCallees:
    """Test entity with both callers and callees populated."""

    async def test_populated_call_graph(self, mock_access_control, wiki_env):
        env = wiki_env

        mock_call_graph = {
            "parse_config": ["read_file", "validate_yaml"],
        }
        mock_reverse_graph = {
            "parse_config": ["main", "test_parse_config", "cli_handler"],
        }

        mock_cg_extractor = MagicMock()
        mock_cg_extractor.extract_from_file.return_value = mock_call_graph

        mock_example_extractor = MagicMock()
        mock_example_extractor.extract_examples_for_function = AsyncMock(
            return_value=[]
        )

        mock_func_sig = MagicMock()
        mock_func_sig.name = "parse_config"
        mock_func_sig.parameters = []
        mock_func_sig.return_type = "Config"
        mock_func_sig.docstring = "Parse."
        mock_func_sig.is_async = False
        mock_func_sig.decorators = []

        mock_api_extractor = MagicMock()
        mock_api_extractor.extract_from_file.return_value = ([mock_func_sig], [])

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
            patch(
                "local_deepwiki.generators.callgraph.CallGraphExtractor",
                return_value=mock_cg_extractor,
            ),
            patch(
                "local_deepwiki.generators.callgraph.build_reverse_call_graph",
                return_value=mock_reverse_graph,
            ),
            patch(
                "local_deepwiki.generators.test_examples.CodeExampleExtractor",
                return_value=mock_example_extractor,
            ),
            patch(
                "local_deepwiki.generators.api_docs.APIDocExtractor",
                return_value=mock_api_extractor,
            ),
        ):
            mock_load.return_value = (
                env["index_status"],
                env["wiki_path"],
                env["config"],
            )

            result = await handle_explain_entity(
                {"repo_path": str(env["tmp_path"]), "entity_name": "parse_config"}
            )

        data = json.loads(result[0].text)
        assert data["call_graph"]["calls"] == ["read_file", "validate_yaml"]
        assert "main" in data["call_graph"]["called_by"]
        assert len(data["call_graph"]["called_by"]) == 3


class TestExplainEntitySourceFileNotFound:
    """Test when entity file does not exist on disk."""

    async def test_source_file_missing(self, mock_access_control, tmp_path):
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        entities = [
            {
                "type": "entity",
                "entity_type": "function",
                "name": "missing_func",
                "display_name": "missing_func",
                "path": "files/src/gone.md",
                "file": "src/gone.py",  # File does NOT exist
                "signature": "() -> None",
                "description": "Gone function.",
                "is_async": False,
                "raises": [],
                "keywords": [],
            },
        ]
        _make_search_json(wiki_path, entities)

        index_status = _make_index_status(str(tmp_path))
        config = _make_config(tmp_path)

        with (
            patch("local_deepwiki.handlers.analysis._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.analysis._create_vector_store"),
        ):
            mock_load.return_value = (index_status, wiki_path, config)

            result = await handle_explain_entity(
                {
                    "repo_path": str(tmp_path),
                    "entity_name": "missing_func",
                    "include_test_examples": False,
                }
            )

        data = json.loads(result[0].text)
        assert data["entity_found"] is True
        # Call graph should note source file not found
        assert data["call_graph"]["note"] == "Source file not found"


class TestExplainEntityArgsCustomValues:
    """Additional Pydantic model validation tests."""

    def test_custom_max_test_examples(self):
        args = ExplainEntityArgs(
            repo_path="/tmp/repo",
            entity_name="foo",
            max_test_examples=5,
        )
        assert args.max_test_examples == 5

    def test_entity_name_with_dots(self):
        """Entity names with dots (e.g., 'Config.get_value') should be accepted."""
        args = ExplainEntityArgs(repo_path="/tmp/repo", entity_name="Config.get_value")
        assert args.entity_name == "Config.get_value"
