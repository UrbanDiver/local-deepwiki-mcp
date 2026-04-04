"""Tests for agentic workflow runner functions."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_handler_result():
    """Return a mock handler result matching TextContent shape."""
    return [MagicMock(text='{"status":"success"}')]


# ---------------------------------------------------------------------------
# _run_onboarding — wiki exists (4 parallel steps)
# ---------------------------------------------------------------------------


async def test_run_onboarding_wiki_exists(tmp_path: Path):
    """When wiki_path exists, all four steps run in parallel."""
    from local_deepwiki.handlers.agentic_workflows import _run_onboarding

    # Create the wiki directory so the exists() check passes
    wiki_dir = tmp_path / ".deepwiki"
    wiki_dir.mkdir()

    mock_result = _mock_handler_result()

    mock_config = MagicMock()
    mock_config.get_wiki_path.return_value = wiki_dir

    with (
        patch(
            "local_deepwiki.handlers.analysis_metadata.handle_get_project_manifest",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "local_deepwiki.handlers.core.handle_read_wiki_structure",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "local_deepwiki.handlers.analysis_metadata.handle_get_wiki_stats",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "local_deepwiki.handlers.codemap.handle_suggest_codemap_topics",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "local_deepwiki.config.get_config",
            return_value=mock_config,
        ),
    ):
        results = await _run_onboarding(str(tmp_path))

    assert len(results) == 4
    step_names = [r["step"] for r in results]
    assert "get_project_manifest" in step_names
    assert "read_wiki_structure" in step_names
    assert "get_wiki_stats" in step_names
    assert "suggest_codemap_topics" in step_names
    assert all(r["status"] == "success" for r in results)


# ---------------------------------------------------------------------------
# _run_onboarding — wiki does NOT exist (manifest only + skipped)
# ---------------------------------------------------------------------------


async def test_run_onboarding_wiki_missing(tmp_path: Path):
    """When wiki_path does not exist, only manifest runs and wiki steps are skipped."""
    from local_deepwiki.handlers.agentic_workflows import _run_onboarding

    # Point to a directory that does NOT exist
    wiki_dir = tmp_path / ".deepwiki"
    assert not wiki_dir.exists()

    mock_result = _mock_handler_result()

    mock_config = MagicMock()
    mock_config.get_wiki_path.return_value = wiki_dir

    with (
        patch(
            "local_deepwiki.handlers.analysis_metadata.handle_get_project_manifest",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "local_deepwiki.config.get_config",
            return_value=mock_config,
        ),
    ):
        results = await _run_onboarding(str(tmp_path))

    assert len(results) == 2
    assert results[0]["step"] == "get_project_manifest"
    assert results[0]["status"] == "success"
    assert results[1]["step"] == "read_wiki_structure"
    assert results[1]["status"] == "skipped"
    assert "reason" in results[1]


# ---------------------------------------------------------------------------
# _run_security_audit
# ---------------------------------------------------------------------------


async def test_run_security_audit():
    """Security audit runs detect_secrets + per-file complexity in parallel."""
    from local_deepwiki.handlers.agentic_workflows import _run_security_audit

    mock_result = _mock_handler_result()

    # Create a temp directory with a Python file so rglob finds something
    with tempfile.TemporaryDirectory() as td:
        src_file = Path(td) / "app.py"
        src_file.write_text("print('hello')")

        with (
            patch(
                "local_deepwiki.handlers.generators.handle_detect_secrets",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "local_deepwiki.handlers.analysis_metadata.handle_get_complexity_metrics",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            results = await _run_security_audit(td)

    assert any(s["step"] == "detect_secrets" for s in results)
    # At least one complexity step for the .py file we created
    complexity_steps = [s for s in results if s["step"].startswith("complexity:")]
    assert len(complexity_steps) >= 1
    assert all(s["status"] == "success" for s in results)


async def test_run_security_audit_no_source_files():
    """Security audit with no source files still runs detect_secrets."""
    from local_deepwiki.handlers.agentic_workflows import _run_security_audit

    mock_result = _mock_handler_result()

    with tempfile.TemporaryDirectory() as td:
        with patch(
            "local_deepwiki.handlers.generators.handle_detect_secrets",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            results = await _run_security_audit(td)

    assert len(results) == 1
    assert results[0]["step"] == "detect_secrets"
    assert results[0]["status"] == "success"


# ---------------------------------------------------------------------------
# _run_full_analysis
# ---------------------------------------------------------------------------


async def test_run_full_analysis():
    """Full analysis runs wiki_stats, coverage, stale_docs, secrets in parallel."""
    from local_deepwiki.handlers.agentic_workflows import _run_full_analysis

    mock_result = _mock_handler_result()

    with (
        patch(
            "local_deepwiki.handlers.analysis_metadata.handle_get_wiki_stats",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "local_deepwiki.handlers.generators.handle_get_coverage",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "local_deepwiki.handlers.generators.handle_detect_stale_docs",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "local_deepwiki.handlers.generators.handle_detect_secrets",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
    ):
        results = await _run_full_analysis("/tmp/fake-repo")

    assert len(results) == 4
    step_names = [r["step"] for r in results]
    assert "get_wiki_stats" in step_names
    assert "get_coverage" in step_names
    assert "detect_stale_docs" in step_names
    assert "detect_secrets" in step_names
    assert all(r["status"] == "success" for r in results)


# ---------------------------------------------------------------------------
# _run_quick_refresh
# ---------------------------------------------------------------------------


async def test_run_quick_refresh():
    """Quick refresh runs stale_docs and changelog in parallel."""
    from local_deepwiki.handlers.agentic_workflows import _run_quick_refresh

    mock_result = _mock_handler_result()

    with (
        patch(
            "local_deepwiki.handlers.generators.handle_detect_stale_docs",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "local_deepwiki.handlers.generators.handle_get_changelog",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
    ):
        results = await _run_quick_refresh("/tmp/fake-repo")

    assert len(results) == 2
    step_names = [r["step"] for r in results]
    assert "detect_stale_docs" in step_names
    assert "get_changelog" in step_names
    assert all(r["status"] == "success" for r in results)


# ---------------------------------------------------------------------------
# Error handling — verify failed steps produce error entries
# ---------------------------------------------------------------------------


async def test_run_quick_refresh_step_failure():
    """A failing step produces an error entry but does not break the workflow."""
    from local_deepwiki.handlers.agentic_workflows import _run_quick_refresh

    mock_result = _mock_handler_result()

    with (
        patch(
            "local_deepwiki.handlers.generators.handle_detect_stale_docs",
            new_callable=AsyncMock,
            side_effect=RuntimeError("stale docs exploded"),
        ),
        patch(
            "local_deepwiki.handlers.generators.handle_get_changelog",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
    ):
        results = await _run_quick_refresh("/tmp/fake-repo")

    assert len(results) == 2
    stale = next(r for r in results if r["step"] == "detect_stale_docs")
    changelog = next(r for r in results if r["step"] == "get_changelog")
    assert stale["status"] == "error"
    assert "stale docs exploded" in stale["error"]
    assert changelog["status"] == "success"


async def test_run_full_analysis_partial_failure():
    """Full analysis continues when one step fails."""
    from local_deepwiki.handlers.agentic_workflows import _run_full_analysis

    mock_result = _mock_handler_result()

    with (
        patch(
            "local_deepwiki.handlers.analysis_metadata.handle_get_wiki_stats",
            new_callable=AsyncMock,
            side_effect=ValueError("stats broke"),
        ),
        patch(
            "local_deepwiki.handlers.generators.handle_get_coverage",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "local_deepwiki.handlers.generators.handle_detect_stale_docs",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "local_deepwiki.handlers.generators.handle_detect_secrets",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
    ):
        results = await _run_full_analysis("/tmp/fake-repo")

    assert len(results) == 4
    wiki_stats = next(r for r in results if r["step"] == "get_wiki_stats")
    assert wiki_stats["status"] == "error"
    assert "stats broke" in wiki_stats["error"]
    # Other three succeeded
    successes = [r for r in results if r["status"] == "success"]
    assert len(successes) == 3
