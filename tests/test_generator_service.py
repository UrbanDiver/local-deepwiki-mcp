"""Tests for GeneratorService business logic."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.services.generator_service import GeneratorService


def _make_service() -> tuple[GeneratorService, MagicMock, MagicMock]:
    """Create a GeneratorService with mock dependencies."""
    mock_vs = MagicMock()
    mock_config = MagicMock()
    return GeneratorService(mock_vs, mock_config), mock_vs, mock_config


def _make_entity(
    name: str = "foo",
    entity_type: str = "function",
    file_path: str = "src/foo.py",
    docstring: str | None = "does stuff",
) -> MagicMock:
    """Create a mock EntityEntry."""
    entity = MagicMock()
    entity.name = name
    entity.entity_type = entity_type
    entity.file_path = file_path
    entity.docstring = docstring
    return entity


# ---------------------------------------------------------------------------
# generate_glossary
# ---------------------------------------------------------------------------


async def test_generate_glossary_basic():
    svc, _vs, _cfg = _make_service()
    entities = [_make_entity(), _make_entity(name="bar", file_path="src/bar.py")]

    with patch(
        "local_deepwiki.generators.analysis.glossary.collect_all_entities",
        new_callable=AsyncMock,
        return_value=entities,
    ):
        result = await svc.generate_glossary(MagicMock())

    assert result["status"] == "success"
    assert result["total_entities"] == 2
    assert result["returned"] == 2
    assert result["has_more"] is False
    assert len(result["entities"]) == 2
    assert result["entities"][0]["name"] == "foo"


async def test_generate_glossary_search_filter():
    svc, _vs, _cfg = _make_service()
    entities = [
        _make_entity(name="process_data", docstring="process incoming data"),
        _make_entity(name="render_view", docstring="render the UI"),
    ]

    with patch(
        "local_deepwiki.generators.analysis.glossary.collect_all_entities",
        new_callable=AsyncMock,
        return_value=entities,
    ):
        result = await svc.generate_glossary(MagicMock(), search="process")

    assert result["total_entities"] == 1
    assert result["entities"][0]["name"] == "process_data"


async def test_generate_glossary_file_path_filter():
    svc, _vs, _cfg = _make_service()
    entities = [
        _make_entity(name="a", file_path="src/utils/helpers.py"),
        _make_entity(name="b", file_path="src/core/engine.py"),
    ]

    with patch(
        "local_deepwiki.generators.analysis.glossary.collect_all_entities",
        new_callable=AsyncMock,
        return_value=entities,
    ):
        result = await svc.generate_glossary(MagicMock(), file_path="helpers.py")

    assert result["total_entities"] == 1
    assert result["entities"][0]["name"] == "a"


async def test_generate_glossary_pagination():
    svc, _vs, _cfg = _make_service()
    entities = [_make_entity(name=f"entity_{i}") for i in range(5)]

    with patch(
        "local_deepwiki.generators.analysis.glossary.collect_all_entities",
        new_callable=AsyncMock,
        return_value=entities,
    ):
        result = await svc.generate_glossary(MagicMock(), offset=1, limit=2)

    assert result["total_entities"] == 5
    assert result["returned"] == 2
    assert result["offset"] == 1
    assert result["limit"] == 2
    assert result["has_more"] is True


# ---------------------------------------------------------------------------
# generate_diagrams
# ---------------------------------------------------------------------------


async def test_generate_diagrams_class():
    svc, vs, _cfg = _make_service()
    vs.get_all_chunks.return_value = iter([MagicMock()])

    with patch(
        "local_deepwiki.generators.diagrams.generate_class_diagram",
        return_value="classDiagram\n  A --> B",
    ):
        result = await svc.generate_diagrams(MagicMock(), Path("/repo"), "class")

    assert result["status"] == "success"
    assert result["diagram_type"] == "class"
    assert "classDiagram" in result["mermaid"]


async def test_generate_diagrams_returns_message_on_none():
    svc, vs, _cfg = _make_service()
    vs.get_all_chunks.return_value = iter([])

    with patch(
        "local_deepwiki.generators.diagrams.generate_class_diagram",
        return_value=None,
    ):
        result = await svc.generate_diagrams(MagicMock(), Path("/repo"), "class")

    assert "message" in result
    assert "class" in result["message"]


async def test_generate_diagrams_dependency():
    svc, vs, _cfg = _make_service()
    vs.get_all_chunks.return_value = iter([MagicMock()])

    with patch(
        "local_deepwiki.generators.diagrams.generate_dependency_graph",
        return_value="graph TD\n  A --> B",
    ):
        result = await svc.generate_diagrams(
            MagicMock(), Path("/my-repo"), "dependency"
        )

    assert result["status"] == "success"
    assert result["diagram_type"] == "dependency"


async def test_generate_diagrams_module():
    svc, vs, _cfg = _make_service()
    vs.get_all_chunks.return_value = iter([])

    with patch(
        "local_deepwiki.generators.diagrams.generate_module_overview",
        return_value="graph TD\n  mod_a --> mod_b",
    ):
        result = await svc.generate_diagrams(MagicMock(), Path("/repo"), "module")

    assert result["status"] == "success"
    assert result["diagram_type"] == "module"


async def test_generate_diagrams_language_pie():
    svc, vs, _cfg = _make_service()
    vs.get_all_chunks.return_value = iter([])

    with patch(
        "local_deepwiki.generators.diagrams.generate_language_pie_chart",
        return_value="pie\n  Python: 80",
    ):
        result = await svc.generate_diagrams(MagicMock(), Path("/repo"), "language_pie")

    assert result["status"] == "success"
    assert result["diagram_type"] == "language_pie"


async def test_generate_diagrams_sequence():
    svc, vs, _cfg = _make_service()
    vs.get_all_chunks.return_value = iter([])

    mock_index = MagicMock()
    file_info = MagicMock()
    file_info.path = "src/main.py"
    mock_index.files = [file_info]

    mock_extractor = MagicMock()
    mock_extractor.extract_from_file.return_value = {"main": ["helper"]}

    with (
        patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor",
            return_value=mock_extractor,
        ),
        patch(
            "local_deepwiki.generators.diagrams.generate_sequence_diagram",
            return_value="sequenceDiagram\n  main->>helper: call",
        ),
        patch("pathlib.Path.exists", return_value=True),
    ):
        result = await svc.generate_diagrams(
            mock_index, Path("/repo"), "sequence", entry_point="main"
        )

    assert result["status"] == "success"
    assert result["diagram_type"] == "sequence"


async def test_generate_diagrams_sequence_missing_entry_point():
    from local_deepwiki.errors import ValidationError

    svc, vs, _cfg = _make_service()
    vs.get_all_chunks.return_value = iter([])

    with pytest.raises(ValidationError):
        await svc.generate_diagrams(MagicMock(), Path("/repo"), "sequence")


async def test_generate_diagrams_unknown_type():
    svc, vs, _cfg = _make_service()
    vs.get_all_chunks.return_value = iter([])

    result = await svc.generate_diagrams(MagicMock(), Path("/repo"), "nonexistent_type")

    assert "message" in result
    assert "nonexistent_type" in result["message"]


# ---------------------------------------------------------------------------
# generate_inheritance
# ---------------------------------------------------------------------------


async def test_generate_inheritance_basic():
    svc, _vs, _cfg = _make_service()

    node = MagicMock()
    node.name = "Animal"
    node.file_path = "src/models.py"
    node.parents = []
    node.children = ["Dog", "Cat"]
    node.is_abstract = True
    node.docstring = "Base animal class"

    classes = {"Animal": node}

    with (
        patch(
            "local_deepwiki.generators.analysis.inheritance.collect_class_hierarchy",
            new_callable=AsyncMock,
            return_value=classes,
        ),
        patch(
            "local_deepwiki.generators.analysis.inheritance.generate_inheritance_diagram",
            return_value="classDiagram\n  Animal <|-- Dog",
        ),
    ):
        result = await svc.generate_inheritance(MagicMock())

    assert result["status"] == "success"
    assert result["total_classes"] == 1
    assert result["classes"][0]["name"] == "Animal"
    assert result["classes"][0]["is_abstract"] is True
    assert result["mermaid_diagram"] is not None


async def test_generate_inheritance_empty():
    svc, _vs, _cfg = _make_service()

    with patch(
        "local_deepwiki.generators.analysis.inheritance.collect_class_hierarchy",
        new_callable=AsyncMock,
        return_value={},
    ):
        result = await svc.generate_inheritance(MagicMock())

    assert result["message"] == "No class hierarchies found in the codebase"
    assert result["classes"] == []


async def test_generate_inheritance_search_filter():
    svc, _vs, _cfg = _make_service()

    node_a = MagicMock()
    node_a.name = "BaseHandler"
    node_a.file_path = "src/handler.py"
    node_a.parents = []
    node_a.children = []
    node_a.is_abstract = False
    node_a.docstring = None

    node_b = MagicMock()
    node_b.name = "UserService"
    node_b.file_path = "src/service.py"
    node_b.parents = []
    node_b.children = []
    node_b.is_abstract = False
    node_b.docstring = None

    classes = {"BaseHandler": node_a, "UserService": node_b}

    with (
        patch(
            "local_deepwiki.generators.analysis.inheritance.collect_class_hierarchy",
            new_callable=AsyncMock,
            return_value=classes,
        ),
        patch(
            "local_deepwiki.generators.analysis.inheritance.generate_inheritance_diagram",
            return_value="classDiagram",
        ),
    ):
        result = await svc.generate_inheritance(MagicMock(), search="handler")

    assert result["total_classes"] == 1
    assert result["classes"][0]["name"] == "BaseHandler"


# ---------------------------------------------------------------------------
# generate_call_graph
# ---------------------------------------------------------------------------


async def test_generate_call_graph_with_file_path():
    svc, _vs, _cfg = _make_service()

    with (
        patch(
            "local_deepwiki.core.path_utils.validate_file_in_repo",
            return_value=Path("/repo/src/main.py"),
        ),
        patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as mock_cls,
        patch(
            "local_deepwiki.generators.analysis.callgraph.generate_call_graph_diagram",
            return_value="graph TD\n  main --> helper",
        ),
    ):
        mock_cls.return_value.extract_from_file.return_value = {"main": ["helper"]}
        result = await svc.generate_call_graph(Path("/repo"), file_path="src/main.py")

    assert result["status"] == "success"
    assert result["scope"] == "src/main.py"
    assert "mermaid" in result


async def test_generate_call_graph_full_repo():
    svc, _vs, _cfg = _make_service()

    mock_index = MagicMock()
    file_info = MagicMock()
    file_info.path = "src/app.py"
    mock_index.files = [file_info]

    with (
        patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as mock_cls,
        patch(
            "local_deepwiki.generators.analysis.callgraph.generate_call_graph_diagram",
            return_value="graph TD\n  app --> util",
        ),
        patch("pathlib.Path.exists", return_value=True),
    ):
        mock_cls.return_value.extract_from_file.return_value = {"app": ["util"]}
        result = await svc.generate_call_graph(Path("/repo"), index_status=mock_index)

    assert result["status"] == "success"
    assert result["scope"] == "full_repository"


async def test_generate_call_graph_no_relationships():
    svc, _vs, _cfg = _make_service()

    with (
        patch(
            "local_deepwiki.core.path_utils.validate_file_in_repo",
            return_value=Path("/repo/empty.py"),
        ),
        patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as mock_cls,
        patch(
            "local_deepwiki.generators.analysis.callgraph.generate_call_graph_diagram",
            return_value=None,
        ),
    ):
        mock_cls.return_value.extract_from_file.return_value = {}
        result = await svc.generate_call_graph(Path("/repo"), file_path="empty.py")

    assert result["message"] == "No call relationships found"


# ---------------------------------------------------------------------------
# generate_coverage
# ---------------------------------------------------------------------------


async def test_generate_coverage():
    svc, _vs, _cfg = _make_service()

    mock_stats = MagicMock()
    mock_stats.total_entities = 10
    mock_stats.documented_entities = 7
    mock_stats.coverage_percent = 70.0

    mock_fc = MagicMock()
    mock_fc.file_path = "src/bad.py"
    mock_fc.stats.coverage_percent = 40.0
    mock_fc.undocumented = ["func_a", "func_b"]

    mock_fc_clean = MagicMock()
    mock_fc_clean.file_path = "src/good.py"
    mock_fc_clean.stats.coverage_percent = 100.0
    mock_fc_clean.undocumented = []

    with patch(
        "local_deepwiki.generators.analysis.coverage.analyze_project_coverage",
        new_callable=AsyncMock,
        return_value=(mock_stats, [mock_fc, mock_fc_clean]),
    ):
        result = await svc.generate_coverage(MagicMock())

    assert result["status"] == "success"
    assert result["overall"]["total_entities"] == 10
    assert result["overall"]["documented"] == 7
    assert result["overall"]["undocumented"] == 3
    assert result["overall"]["coverage_percent"] == 70.0
    # Only files with undocumented entities are included
    assert len(result["files"]) == 1
    assert result["files"][0]["file_path"] == "src/bad.py"


# ---------------------------------------------------------------------------
# detect_stale_docs
# ---------------------------------------------------------------------------


async def test_detect_stale_docs_no_wiki_status():
    svc, _vs, _cfg = _make_service()

    mock_manager = MagicMock()
    mock_manager.load_status = AsyncMock(return_value=None)

    with patch(
        "local_deepwiki.generators.wiki.status.WikiStatusManager",
        return_value=mock_manager,
    ):
        result = await svc.detect_stale_docs(Path("/repo"), Path("/wiki"))

    assert "No wiki generation status found" in result["message"]
    assert result["stale_pages"] == []


async def test_detect_stale_docs_with_stale_pages():
    svc, _vs, _cfg = _make_service()

    now = datetime.now(tz=timezone.utc)
    mock_stale_info = MagicMock()
    mock_stale_info.page_path = "files/src/old.md"
    mock_stale_info.days_stale = 45
    mock_stale_info.source_files = ["src/old.py"]
    mock_stale_info.newest_source_date = now
    mock_stale_info.generated_at = now

    mock_report = MagicMock()
    mock_report.total_pages = 10
    mock_report.stale_pages = 1
    mock_report.stale_info = [mock_stale_info]

    mock_manager = MagicMock()
    mock_manager.load_status = AsyncMock(return_value=MagicMock())

    with (
        patch(
            "local_deepwiki.generators.wiki.status.WikiStatusManager",
            return_value=mock_manager,
        ),
        patch(
            "local_deepwiki.generators.analysis.stale_detection.analyze_staleness",
            return_value=mock_report,
        ),
    ):
        result = await svc.detect_stale_docs(Path("/repo"), Path("/wiki"))

    assert result["status"] == "success"
    assert result["total_pages"] == 10
    assert result["stale_count"] == 1
    assert len(result["stale_pages"]) == 1
    assert result["stale_pages"][0]["page_path"] == "files/src/old.md"
    assert result["stale_pages"][0]["days_stale"] == 45


# ---------------------------------------------------------------------------
# generate_changelog
# ---------------------------------------------------------------------------


async def test_generate_changelog():
    svc, _vs, _cfg = _make_service()

    with patch(
        "local_deepwiki.generators.changelog.generate_changelog_content",
        return_value="# Changelog\n\n## 2026-04-01\n- feat: add widget",
    ):
        result = await svc.generate_changelog(Path("/repo"))

    assert result["status"] == "success"
    assert "Changelog" in result["changelog"]


async def test_generate_changelog_no_git_history():
    svc, _vs, _cfg = _make_service()

    with patch(
        "local_deepwiki.generators.changelog.generate_changelog_content",
        return_value=None,
    ):
        result = await svc.generate_changelog(Path("/repo"))

    assert "No git history found" in result["message"]


# ---------------------------------------------------------------------------
# detect_secrets
# ---------------------------------------------------------------------------


async def test_detect_secrets_with_findings():
    svc, _vs, _cfg = _make_service()

    mock_finding = MagicMock()
    mock_finding.secret_type.value = "api_key"
    mock_finding.line_number = 42
    mock_finding.confidence = 0.95
    mock_finding.recommendation = "Move to env var"

    findings_by_file = {"src/config.py": [mock_finding]}

    with (
        patch(
            "local_deepwiki.core.secret_detector.scan_repository_for_secrets",
            return_value=findings_by_file,
        ),
        patch(
            "local_deepwiki.core.path_utils.is_test_file",
            return_value=False,
        ),
    ):
        result = await svc.detect_secrets(Path("/repo"))

    assert result["status"] == "success"
    assert result["files_with_secrets"] == 1
    assert result["total_findings"] == 1
    assert result["exclude_tests"] is True
    assert result["findings"][0]["file_path"] == "src/config.py"
    assert result["findings"][0]["secrets"][0]["type"] == "api_key"
    assert result["findings"][0]["secrets"][0]["confidence"] == 0.95


async def test_detect_secrets_exclude_tests_filters():
    svc, _vs, _cfg = _make_service()

    mock_finding = MagicMock()
    mock_finding.secret_type.value = "generic_token"
    mock_finding.line_number = 10
    mock_finding.confidence = 0.5
    mock_finding.recommendation = "Review"

    findings_by_file = {
        "tests/test_auth.py": [mock_finding],
        "src/auth.py": [mock_finding],
    }

    call_count = 0

    def is_test_file_side_effect(path, check_filename=False):
        return "test" in str(path)

    with (
        patch(
            "local_deepwiki.core.secret_detector.scan_repository_for_secrets",
            return_value=findings_by_file,
        ),
        patch(
            "local_deepwiki.core.path_utils.is_test_file",
            side_effect=is_test_file_side_effect,
        ),
    ):
        result = await svc.detect_secrets(Path("/repo"), exclude_tests=True)

    assert result["files_with_secrets"] == 1
    assert result["total_findings"] == 1


async def test_detect_secrets_include_tests():
    svc, _vs, _cfg = _make_service()

    mock_finding = MagicMock()
    mock_finding.secret_type.value = "api_key"
    mock_finding.line_number = 5
    mock_finding.confidence = 0.8
    mock_finding.recommendation = "Rotate"

    findings_by_file = {"tests/test_config.py": [mock_finding]}

    with (
        patch(
            "local_deepwiki.core.secret_detector.scan_repository_for_secrets",
            return_value=findings_by_file,
        ),
        patch(
            "local_deepwiki.core.path_utils.is_test_file",
            return_value=True,
        ),
    ):
        result = await svc.detect_secrets(Path("/repo"), exclude_tests=False)

    assert result["files_with_secrets"] == 1
    assert result["exclude_tests"] is False


# ---------------------------------------------------------------------------
# generate_test_examples
# ---------------------------------------------------------------------------


async def test_generate_test_examples_found():
    svc, _vs, _cfg = _make_service()

    mock_example = MagicMock()
    mock_example.source = "test"
    mock_example.code = "assert foo() == 42"
    mock_example.description = "test for foo"
    mock_example.test_file = "tests/test_foo.py"
    mock_example.language = "python"

    mock_extractor = MagicMock()
    mock_extractor.extract_examples_for_function = AsyncMock(
        return_value=[mock_example]
    )
    mock_extractor.extract_examples_for_class = AsyncMock(return_value=[])

    with patch(
        "local_deepwiki.generators.examples.extractor.CodeExampleExtractor",
        return_value=mock_extractor,
    ):
        result = await svc.generate_test_examples(Path("/repo"), "foo")

    assert result["status"] == "success"
    assert result["entity_name"] == "foo"
    assert result["total_examples"] == 1
    assert result["examples"][0]["source"] == "test"
    assert result["examples"][0]["code"] == "assert foo() == 42"


async def test_generate_test_examples_found_via_class():
    svc, _vs, _cfg = _make_service()

    mock_example = MagicMock()
    mock_example.source = "test"
    mock_example.code = "MyClass().run()"
    mock_example.description = "test for MyClass"
    mock_example.test_file = "tests/test_myclass.py"
    mock_example.language = "python"

    mock_extractor = MagicMock()
    mock_extractor.extract_examples_for_function = AsyncMock(return_value=[])
    mock_extractor.extract_examples_for_class = AsyncMock(return_value=[mock_example])

    with patch(
        "local_deepwiki.generators.examples.extractor.CodeExampleExtractor",
        return_value=mock_extractor,
    ):
        result = await svc.generate_test_examples(Path("/repo"), "MyClass")

    assert result["status"] == "success"
    assert result["total_examples"] == 1


async def test_generate_test_examples_not_found():
    svc, _vs, _cfg = _make_service()

    mock_extractor = MagicMock()
    mock_extractor.extract_examples_for_function = AsyncMock(return_value=[])
    mock_extractor.extract_examples_for_class = AsyncMock(return_value=[])

    with patch(
        "local_deepwiki.generators.examples.extractor.CodeExampleExtractor",
        return_value=mock_extractor,
    ):
        result = await svc.generate_test_examples(Path("/repo"), "nonexistent")

    assert "No test examples found" in result["message"]
    assert result["examples"] == []


# ---------------------------------------------------------------------------
# get_api_docs
# ---------------------------------------------------------------------------


async def test_get_api_docs_found():
    svc, _vs, _cfg = _make_service()

    with (
        patch(
            "local_deepwiki.core.path_utils.validate_file_in_repo",
            return_value=Path("/repo/src/api.py"),
        ),
        patch(
            "local_deepwiki.generators.analysis.api_docs.get_file_api_docs",
            return_value={"functions": [{"name": "handler"}]},
        ),
    ):
        result = await svc.get_api_docs(Path("/repo"), "src/api.py")

    assert result["status"] == "success"
    assert result["file_path"] == "src/api.py"
    assert result["api_docs"]["functions"][0]["name"] == "handler"


async def test_get_api_docs_not_found():
    svc, _vs, _cfg = _make_service()

    with (
        patch(
            "local_deepwiki.core.path_utils.validate_file_in_repo",
            return_value=Path("/repo/src/empty.py"),
        ),
        patch(
            "local_deepwiki.generators.analysis.api_docs.get_file_api_docs",
            return_value=None,
        ),
    ):
        result = await svc.get_api_docs(Path("/repo"), "src/empty.py")

    assert "No API documentation" in result["message"]


# ---------------------------------------------------------------------------
# list_indexed_repos
# ---------------------------------------------------------------------------


async def test_list_indexed_repos():
    svc, _vs, _cfg = _make_service()

    mock_status = MagicMock()
    mock_status.repo_path = "/projects/my-repo"
    mock_status.total_files = 50
    mock_status.total_chunks = 200
    mock_status.languages = {"python": 40, "javascript": 10}
    mock_status.indexed_at = 1700000000.0

    mock_manager = MagicMock()
    mock_manager.load.return_value = mock_status

    with (
        patch(
            "local_deepwiki.core.index_manager.IndexStatusManager",
            return_value=mock_manager,
        ),
        patch(
            "local_deepwiki.core.path_utils.find_deepwiki_dirs",
            return_value=[Path("/projects/my-repo/.deepwiki")],
        ),
    ):
        result = await svc.list_indexed_repos(Path("/projects"))

    assert result["status"] == "success"
    assert result["total_repos"] == 1
    assert result["repos"][0]["repo_path"] == "/projects/my-repo"
    assert result["repos"][0]["total_files"] == 50


async def test_list_indexed_repos_empty():
    svc, _vs, _cfg = _make_service()

    with (
        patch(
            "local_deepwiki.core.index_manager.IndexStatusManager",
            return_value=MagicMock(),
        ),
        patch(
            "local_deepwiki.core.path_utils.find_deepwiki_dirs",
            return_value=[],
        ),
    ):
        result = await svc.list_indexed_repos(Path("/empty"))

    assert result["status"] == "success"
    assert result["total_repos"] == 0
    assert result["repos"] == []


# ---------------------------------------------------------------------------
# get_index_status
# ---------------------------------------------------------------------------


async def test_get_index_status():
    svc, _vs, _cfg = _make_service()

    mock_index = MagicMock()
    mock_index.repo_path = "/projects/repo"
    mock_index.indexed_at = 1700000000.0
    mock_index.total_files = 100
    mock_index.total_chunks = 500
    mock_index.languages = {"python": 80, "go": 20}
    mock_index.schema_version = 2

    result = await svc.get_index_status(mock_index, Path("/wiki"))

    assert result["status"] == "success"
    assert result["repo_path"] == "/projects/repo"
    assert result["wiki_path"] == "/wiki"
    assert result["total_files"] == 100
    assert result["total_chunks"] == 500
    assert result["schema_version"] == 2
    assert "indexed_at_human" in result
