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
    with patch("local_deepwiki.handlers.get_access_controller") as mock:
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
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.get_embedding_provider") as mock_embed,
            patch("local_deepwiki.handlers.VectorStore") as mock_vs,
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

        with patch("local_deepwiki.handlers._load_index_status") as mock_load:
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
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.get_embedding_provider"),
            patch("local_deepwiki.handlers.VectorStore"),
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
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.get_embedding_provider"),
            patch("local_deepwiki.handlers.VectorStore"),
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
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
            patch("local_deepwiki.handlers.get_embedding_provider"),
            patch("local_deepwiki.handlers.VectorStore"),
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
            patch("local_deepwiki.handlers._load_index_status") as mock_load,
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
