"""Tests for the GitHub Action entrypoint (deepwiki-analyze)."""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Import the entrypoint module
ACTION_DIR = Path(__file__).parent.parent / ".github" / "actions" / "deepwiki-analyze"


@pytest.fixture
def entrypoint():
    """Import entrypoint module dynamically."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "entrypoint", ACTION_DIR / "entrypoint.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mock_env(tmp_path, monkeypatch):
    """Set up environment variables for the action."""
    monkeypatch.setenv("INPUT_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("INPUT_BASE_REF", "HEAD~1")
    monkeypatch.setenv("INPUT_HEAD_REF", "HEAD")
    monkeypatch.setenv("INPUT_STALE_THRESHOLD", "0")
    monkeypatch.setenv("INPUT_INCLUDE_CONTENT", "false")
    return tmp_path


class TestRunAnalysis:
    """Tests for the run_analysis async function."""

    async def test_returns_dict_with_expected_keys(self, entrypoint, mock_env):
        diff_result = json.dumps(
            {
                "status": "success",
                "summary": {
                    "total_changed_files": 2,
                    "added": 1,
                    "modified": 1,
                    "deleted": 0,
                },
                "changed_files": [],
                "affected_wiki_pages": [],
                "affected_entities": [],
            }
        )
        stale_result = json.dumps({"status": "success", "stale_pages": []})

        mock_diff = AsyncMock(return_value=[_text_content(diff_result)])
        mock_stale = AsyncMock(return_value=[_text_content(stale_result)])

        with (
            patch(
                "local_deepwiki.handlers.analysis_diff.handle_analyze_diff",
                mock_diff,
            ),
            patch(
                "local_deepwiki.handlers.generators.handle_detect_stale_docs",
                mock_stale,
            ),
        ):
            results = await entrypoint.run_analysis()

        assert "diff_analysis" in results
        assert "stale_docs" in results
        assert "errors" in results
        assert results["diff_analysis"]["status"] == "success"
        assert results["stale_docs"]["status"] == "success"
        assert results["errors"] == []

    async def test_captures_diff_error(self, entrypoint, mock_env):
        mock_diff = AsyncMock(side_effect=RuntimeError("git not found"))
        mock_stale = AsyncMock(
            return_value=[
                _text_content(json.dumps({"status": "success", "stale_pages": []}))
            ]
        )

        with (
            patch(
                "local_deepwiki.handlers.analysis_diff.handle_analyze_diff",
                mock_diff,
            ),
            patch(
                "local_deepwiki.handlers.generators.handle_detect_stale_docs",
                mock_stale,
            ),
        ):
            results = await entrypoint.run_analysis()

        assert results["diff_analysis"] is None
        assert len(results["errors"]) == 1
        assert "git not found" in results["errors"][0]

    async def test_captures_stale_error(self, entrypoint, mock_env):
        diff_result = json.dumps(
            {
                "status": "success",
                "summary": {"total_changed_files": 0},
                "changed_files": [],
                "affected_wiki_pages": [],
                "affected_entities": [],
            }
        )
        mock_diff = AsyncMock(return_value=[_text_content(diff_result)])
        mock_stale = AsyncMock(side_effect=FileNotFoundError("no index"))

        with (
            patch(
                "local_deepwiki.handlers.analysis_diff.handle_analyze_diff",
                mock_diff,
            ),
            patch(
                "local_deepwiki.handlers.generators.handle_detect_stale_docs",
                mock_stale,
            ),
        ):
            results = await entrypoint.run_analysis()

        assert results["stale_docs"] is None
        assert len(results["errors"]) == 1
        assert "no index" in results["errors"][0]

    async def test_passes_correct_args_to_handlers(self, entrypoint, mock_env):
        mock_diff = AsyncMock(
            return_value=[
                _text_content(
                    json.dumps(
                        {"status": "success", "summary": {}, "changed_files": []}
                    )
                )
            ]
        )
        mock_stale = AsyncMock(
            return_value=[
                _text_content(json.dumps({"status": "success", "stale_pages": []}))
            ]
        )

        with (
            patch(
                "local_deepwiki.handlers.analysis_diff.handle_analyze_diff",
                mock_diff,
            ),
            patch(
                "local_deepwiki.handlers.generators.handle_detect_stale_docs",
                mock_stale,
            ),
        ):
            await entrypoint.run_analysis()

        diff_args = mock_diff.call_args[0][0]
        assert diff_args["base_ref"] == "HEAD~1"
        assert diff_args["head_ref"] == "HEAD"
        assert diff_args["include_content"] is False

        stale_args = mock_stale.call_args[0][0]
        assert stale_args["threshold_days"] == 0


class TestBuildComment:
    """Tests for the build_comment function."""

    def test_empty_results(self, entrypoint):
        results = {"diff_analysis": None, "stale_docs": None, "errors": []}
        comment = entrypoint.build_comment(results)
        assert "## DeepWiki PR Analysis" in comment
        assert "local-deepwiki-mcp" in comment

    def test_diff_with_changes(self, entrypoint):
        results = {
            "diff_analysis": {
                "status": "success",
                "summary": {
                    "total_changed_files": 3,
                    "added": 1,
                    "modified": 2,
                    "deleted": 0,
                    "affected_wiki_pages": 2,
                    "affected_entities": 5,
                },
                "affected_wiki_pages": [
                    {"title": "Parser Module", "source_file": "src/parser.py"},
                    {"title": "Config", "source_file": "src/config.py"},
                ],
                "affected_entities": [
                    {"name": "parse_file", "type": "function", "file": "src/parser.py"},
                ],
            },
            "stale_docs": {"status": "success", "stale_pages": []},
            "errors": [],
        }
        comment = entrypoint.build_comment(results)
        assert "### Changes: 3 files" in comment
        assert "+1 added" in comment
        assert "~2 modified" in comment
        assert "Parser Module" in comment
        assert "`parse_file`" in comment
        assert "Stale Documentation: None" in comment

    def test_stale_pages(self, entrypoint):
        results = {
            "diff_analysis": {
                "status": "success",
                "summary": {
                    "total_changed_files": 1,
                    "added": 0,
                    "modified": 1,
                    "deleted": 0,
                    "affected_wiki_pages": 0,
                    "affected_entities": 0,
                },
                "affected_wiki_pages": [],
                "affected_entities": [],
            },
            "stale_docs": {
                "status": "success",
                "stale_pages": [
                    {
                        "wiki_page": "Old Module",
                        "source_file": "src/old.py",
                        "days_since_source_changed": 45,
                    }
                ],
            },
            "errors": [],
        }
        comment = entrypoint.build_comment(results)
        assert "Stale Documentation (1 pages)" in comment
        assert "Old Module" in comment
        assert "45" in comment

    def test_diff_error(self, entrypoint):
        results = {
            "diff_analysis": {"status": "error", "error": "git failed"},
            "stale_docs": None,
            "errors": [],
        }
        comment = entrypoint.build_comment(results)
        assert "git failed" in comment

    def test_not_indexed_message(self, entrypoint):
        results = {
            "diff_analysis": None,
            "stale_docs": {
                "status": "error",
                "error": "Repository not indexed",
            },
            "errors": [],
        }
        comment = entrypoint.build_comment(results)
        assert "not indexed" in comment.lower()

    def test_warnings_section(self, entrypoint):
        results = {
            "diff_analysis": None,
            "stale_docs": None,
            "errors": ["Something went wrong", "Another issue"],
        }
        comment = entrypoint.build_comment(results)
        assert "### Warnings" in comment
        assert "Something went wrong" in comment
        assert "Another issue" in comment

    def test_large_entity_list_truncated(self, entrypoint):
        entities = [
            {"name": f"entity_{i}", "type": "function", "file": f"src/f{i}.py"}
            for i in range(50)
        ]
        results = {
            "diff_analysis": {
                "status": "success",
                "summary": {
                    "total_changed_files": 50,
                    "added": 0,
                    "modified": 50,
                    "deleted": 0,
                    "affected_wiki_pages": 0,
                    "affected_entities": 50,
                },
                "affected_wiki_pages": [],
                "affected_entities": entities,
            },
            "stale_docs": None,
            "errors": [],
        }
        comment = entrypoint.build_comment(results)
        assert "... and 20 more" in comment


class TestSetOutput:
    """Tests for the set_output function."""

    def test_writes_to_github_output(self, entrypoint, tmp_path):
        output_file = tmp_path / "github_output"
        output_file.touch()
        os.environ["GITHUB_OUTPUT"] = str(output_file)

        try:
            entrypoint.set_output("my_key", "my_value")
            content = output_file.read_text()
            assert "my_key=my_value" in content
        finally:
            del os.environ["GITHUB_OUTPUT"]

    def test_no_github_output_env(self, entrypoint, monkeypatch):
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        # Should not raise
        entrypoint.set_output("key", "value")


class TestMain:
    """Tests for the main function."""

    def test_main_writes_comment_file(
        self, entrypoint, mock_env, tmp_path, monkeypatch
    ):
        output_file = tmp_path / "github_output"
        output_file.touch()
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        diff_result = json.dumps(
            {
                "status": "success",
                "summary": {
                    "total_changed_files": 1,
                    "added": 0,
                    "modified": 1,
                    "deleted": 0,
                    "affected_wiki_pages": 0,
                    "affected_entities": 0,
                },
                "changed_files": [],
                "affected_wiki_pages": [],
                "affected_entities": [],
            }
        )
        stale_result = json.dumps({"status": "success", "stale_pages": []})

        with (
            patch(
                "local_deepwiki.handlers.analysis_diff.handle_analyze_diff",
                AsyncMock(return_value=[_text_content(diff_result)]),
            ),
            patch(
                "local_deepwiki.handlers.generators.handle_detect_stale_docs",
                AsyncMock(return_value=[_text_content(stale_result)]),
            ),
        ):
            entrypoint.main()

        comment_path = Path("/tmp/deepwiki-comment.md")
        assert comment_path.exists()
        content = comment_path.read_text()
        assert "## DeepWiki PR Analysis" in content

        outputs = output_file.read_text()
        assert "changed_files=1" in outputs
        assert "stale_pages=0" in outputs


# --- Helpers ---


def _text_content(text: str):
    """Create a mock TextContent-like object."""
    from types import SimpleNamespace

    return SimpleNamespace(type="text", text=text)
