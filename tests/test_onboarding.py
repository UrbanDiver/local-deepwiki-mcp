"""Tests for the onboarding guide generator and handler."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.generators.analysis.onboarding import (
    format_onboarding_guide,
    generate_onboarding_guide,
)


@pytest.fixture
def synthetic_repo(tmp_path):
    """Create a synthetic repository structure for testing."""
    repo = tmp_path / "myproject"
    repo.mkdir()

    # pyproject.toml
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "1.0.0"\n'
        'description = "A test application"\n'
    )

    # Source package
    src = repo / "src" / "myapp"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text('"""My application."""\n')
    (src / "__main__.py").write_text(
        '"""Entry point."""\nif __name__ == "__main__":\n    pass\n'
    )
    (src / "cli.py").write_text('"""CLI interface."""\n')
    (src / "server.py").write_text('"""Server entry point."""\n')
    (src / "utils.py").write_text('"""Utilities."""\n')

    # Core subpackage
    core = src / "core"
    core.mkdir()
    (core / "__init__.py").write_text("")
    (core / "engine.py").write_text('"""Core engine."""\n')

    # Tests directory
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("")
    (tests_dir / "test_utils.py").write_text('"""Tests for utils."""\n')

    # CI/CD and config files
    workflows = repo / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI\n")

    (repo / "Dockerfile").write_text("FROM python:3.12\n")

    return repo


def test_generate_onboarding_guide_standard(synthetic_repo):
    """Standard detail level returns all main sections."""
    data = generate_onboarding_guide(synthetic_repo, detail_level="standard")

    assert "manifest" in data
    assert "directory_tree" in data
    assert "entry_points" in data
    assert "key_modules" in data
    assert "test_layout" in data
    assert "detail_level" in data
    assert data["detail_level"] == "standard"


def test_generate_onboarding_guide_has_entry_points(synthetic_repo):
    """Detects __main__.py and server.py as entry points."""
    data = generate_onboarding_guide(synthetic_repo, detail_level="standard")

    entry_point_paths = [str(ep) for ep in data["entry_points"]]
    # Should find __main__.py and server.py (and cli.py)
    assert any("__main__.py" in p for p in entry_point_paths)
    assert any("server.py" in p for p in entry_point_paths)


def test_format_onboarding_guide_standard(synthetic_repo):
    """Formatted markdown has expected section headers for standard level."""
    data = generate_onboarding_guide(synthetic_repo, detail_level="standard")
    md = format_onboarding_guide(data, detail_level="standard")

    assert "# Onboarding Guide" in md
    assert "## Project Overview" in md
    assert "## Getting Started" in md
    assert "## Repository Layout" in md
    assert "## Entry Points" in md
    assert "## Key Modules" in md
    assert "## Testing" in md


def test_format_onboarding_guide_summary(synthetic_repo):
    """Summary level only includes overview, getting started, and layout."""
    data = generate_onboarding_guide(synthetic_repo, detail_level="summary")
    md = format_onboarding_guide(data, detail_level="summary")

    assert "## Project Overview" in md
    assert "## Getting Started" in md
    assert "## Repository Layout" in md
    # Should NOT include detailed sections
    assert "## Entry Points" not in md
    assert "## Key Modules" not in md
    assert "## Testing" not in md
    assert "## Configuration" not in md


def test_format_onboarding_guide_full(synthetic_repo):
    """Full level includes configuration section."""
    data = generate_onboarding_guide(synthetic_repo, detail_level="full")
    md = format_onboarding_guide(data, detail_level="full")

    assert "## Configuration" in md
    assert "## Entry Points" in md
    assert "## Key Modules" in md
    assert "## Testing" in md


def test_generate_onboarding_guide_empty_repo(tmp_path):
    """Empty repo returns graceful minimal data without errors."""
    empty_repo = tmp_path / "empty"
    empty_repo.mkdir()

    data = generate_onboarding_guide(empty_repo, detail_level="standard")

    assert data["entry_points"] == []
    assert data["key_modules"] == []
    assert data["test_layout"] == []
    assert data["directory_tree"]  # Should still have a tree (just the root)
    assert data["manifest"] is not None

    # Formatting should also work gracefully
    md = format_onboarding_guide(data, detail_level="standard")
    assert "# Onboarding Guide" in md


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@patch("local_deepwiki.generators.analysis.onboarding.generate_rich_onboarding")
async def test_handler_returns_success(mock_rich, mock_access_control, synthetic_repo):
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_onboarding_guide,
    )

    # Rich onboarding fails -> falls back to basic generator
    mock_rich.side_effect = Exception("No vector store")

    result = await handle_get_onboarding_guide({"repo_path": str(synthetic_repo)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "## Project Overview" in data["guide"]


async def test_handler_missing_repo(mock_access_control, tmp_path):
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_onboarding_guide,
    )

    result = await handle_get_onboarding_guide(
        {"repo_path": str(tmp_path / "nonexistent")}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


@patch("local_deepwiki.generators.analysis.onboarding.generate_rich_onboarding")
async def test_handler_invalid_detail_level(
    mock_rich, mock_access_control, synthetic_repo
):
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_onboarding_guide,
    )

    # Rich onboarding fails -> falls back to basic generator
    mock_rich.side_effect = Exception("No vector store")

    result = await handle_get_onboarding_guide(
        {"repo_path": str(synthetic_repo), "detail_level": "verbose"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"


class TestGenerateRichOnboarding:
    """Tests for generate_rich_onboarding."""

    @pytest.fixture
    def mock_vector_store(self):
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        mock.get_chunks_by_file = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_llm(self):
        mock = MagicMock()
        # Flow selection returns valid JSON
        mock.generate = AsyncMock(
            side_effect=[
                # Call 1: flow selection
                json.dumps(
                    [
                        {
                            "entry_point": "main",
                            "query": "How does the CLI work?",
                            "title": "CLI Pipeline",
                        },
                        {
                            "entry_point": "server",
                            "query": "How does the server work?",
                            "title": "Server Lifecycle",
                        },
                        {
                            "entry_point": "index",
                            "query": "How does indexing work?",
                            "title": "Indexing Pipeline",
                        },
                    ]
                ),
                # Call 2: synthesis
                "# Developer Onboarding Guide\n\n## What This Project Does\n\nA test project.\n",
            ]
        )
        return mock

    @pytest.fixture
    def mock_codemap_result(self):
        from local_deepwiki.generators.codemap.models import CodemapResult

        return CodemapResult(
            query="How does the CLI work?",
            focus="execution_flow",
            entry_point="main",
            mermaid_diagram="flowchart TD\n    A[main] --> B[run]",
            narrative="## Summary\nThe CLI dispatches commands.\n",
            nodes=[],
            edges=[],
            files_involved=["src/cli.py"],
            total_nodes=2,
            total_edges=1,
            cross_file_edges=0,
        )

    @patch("local_deepwiki.generators.codemap.generator.generate_codemap")
    async def test_rich_onboarding_produces_markdown(
        self,
        mock_gen_codemap,
        synthetic_repo,
        mock_vector_store,
        mock_llm,
        mock_codemap_result,
    ):
        from local_deepwiki.generators.analysis.onboarding import (
            generate_rich_onboarding,
        )

        mock_gen_codemap.return_value = mock_codemap_result

        result = await generate_rich_onboarding(
            repo_path=synthetic_repo,
            vector_store=mock_vector_store,
            llm=mock_llm,
        )

        assert result["status"] == "success"
        assert "guide" in result
        assert isinstance(result["guide"], str)
        assert "Onboarding" in result["guide"]
        # LLM was called twice: flow selection + synthesis
        assert mock_llm.generate.call_count == 2
        # Codemap was called 3 times (one per flow)
        assert mock_gen_codemap.call_count == 3

    @patch("local_deepwiki.generators.codemap.generator.generate_codemap")
    async def test_rich_onboarding_handles_bad_flow_json(
        self,
        mock_gen_codemap,
        synthetic_repo,
        mock_vector_store,
        mock_llm,
        mock_codemap_result,
    ):
        from local_deepwiki.generators.analysis.onboarding import (
            generate_rich_onboarding,
        )

        # LLM returns invalid JSON for flow selection
        mock_llm.generate = AsyncMock(
            side_effect=[
                "not valid json at all",
                "# Developer Onboarding Guide\n\nFallback guide.\n",
            ]
        )
        mock_gen_codemap.return_value = mock_codemap_result

        result = await generate_rich_onboarding(
            repo_path=synthetic_repo,
            vector_store=mock_vector_store,
            llm=mock_llm,
        )

        assert result["status"] == "success"
        # Still produced a guide via fallback
        assert "guide" in result

    @patch("local_deepwiki.generators.codemap.generator.generate_codemap")
    async def test_rich_onboarding_handles_codemap_failure(
        self, mock_gen_codemap, synthetic_repo, mock_vector_store, mock_llm
    ):
        from local_deepwiki.generators.analysis.onboarding import (
            generate_rich_onboarding,
        )

        mock_gen_codemap.side_effect = RuntimeError("codemap failed")
        mock_llm.generate = AsyncMock(
            side_effect=[
                json.dumps(
                    [
                        {"entry_point": "main", "query": "How?", "title": "Flow 1"},
                    ]
                ),
                "# Developer Onboarding Guide\n\nGuide without codemaps.\n",
            ]
        )

        result = await generate_rich_onboarding(
            repo_path=synthetic_repo,
            vector_store=mock_vector_store,
            llm=mock_llm,
        )

        assert result["status"] == "success"
        assert "guide" in result


class TestEnsureTocEntry:
    """Tests for the _ensure_toc_entry helper."""

    def test_inserts_onboarding_entry_at_position_1(self, tmp_path):
        from local_deepwiki.generators.toc import TocEntry, TableOfContents, write_toc
        from local_deepwiki.handlers.analysis_architecture import _ensure_toc_entry

        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create a TOC with Overview and Architecture
        toc = TableOfContents(
            entries=[
                TocEntry(number="1", title="Overview", path="overview.md"),
                TocEntry(number="2", title="Architecture", path="architecture.md"),
            ]
        )
        write_toc(toc, wiki_path)

        _ensure_toc_entry(wiki_path)

        from local_deepwiki.generators.toc import read_toc

        updated = read_toc(wiki_path)
        assert updated is not None
        assert len(updated.entries) == 3
        assert updated.entries[0].title == "Overview"
        assert updated.entries[1].title == "Onboarding Guide"
        assert updated.entries[1].path == "onboarding.md"
        assert updated.entries[2].title == "Architecture"
        # Renumbered
        assert updated.entries[0].number == "1"
        assert updated.entries[1].number == "2"
        assert updated.entries[2].number == "3"

    def test_skips_if_already_present(self, tmp_path):
        from local_deepwiki.generators.toc import TocEntry, TableOfContents, write_toc
        from local_deepwiki.handlers.analysis_architecture import _ensure_toc_entry

        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        toc = TableOfContents(
            entries=[
                TocEntry(number="1", title="Overview", path="overview.md"),
                TocEntry(number="2", title="Onboarding Guide", path="onboarding.md"),
            ]
        )
        write_toc(toc, wiki_path)

        _ensure_toc_entry(wiki_path)

        from local_deepwiki.generators.toc import read_toc

        updated = read_toc(wiki_path)
        assert updated is not None
        assert len(updated.entries) == 2  # No duplicate

    def test_no_toc_file_is_noop(self, tmp_path):
        from local_deepwiki.handlers.analysis_architecture import _ensure_toc_entry

        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        # No toc.json
        _ensure_toc_entry(wiki_path)  # Should not raise


class TestHandleGetOnboardingGuide:
    """Tests for the updated MCP handler."""

    @patch("local_deepwiki.generators.analysis.onboarding.generate_rich_onboarding")
    @patch("local_deepwiki.handlers.analysis_architecture.get_access_controller")
    async def test_handler_calls_rich_onboarding(self, mock_acl, mock_rich, tmp_path):
        from local_deepwiki.handlers.analysis_architecture import (
            handle_get_onboarding_guide,
        )

        mock_acl.return_value = MagicMock()
        mock_rich.return_value = {
            "status": "success",
            "guide": "# Developer Onboarding Guide\n\nTest guide.",
            "codemaps": [],
        }

        # Create repo dir and .deepwiki dir
        (tmp_path / ".deepwiki").mkdir()

        result = await handle_get_onboarding_guide(
            {"repo_path": str(tmp_path), "detail_level": "full"}
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "Onboarding" in data["guide"]
        # Verify it was saved to disk
        onboarding_path = tmp_path / ".deepwiki" / "onboarding.md"
        assert onboarding_path.exists()
        assert "Onboarding" in onboarding_path.read_text()

    @patch("local_deepwiki.generators.analysis.onboarding.generate_rich_onboarding")
    @patch("local_deepwiki.handlers.analysis_architecture.get_access_controller")
    async def test_handler_falls_back_on_missing_index(
        self, mock_acl, mock_rich, tmp_path
    ):
        from local_deepwiki.handlers.analysis_architecture import (
            handle_get_onboarding_guide,
        )

        mock_acl.return_value = MagicMock()
        mock_rich.side_effect = Exception("No vector store")

        # Fallback should use the basic generator
        result = await handle_get_onboarding_guide(
            {"repo_path": str(tmp_path), "detail_level": "standard"}
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "guide" in data
