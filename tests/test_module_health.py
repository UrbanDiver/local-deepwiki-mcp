"""Tests for the get_module_health per-module analysis tool."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture()
def module_repo(tmp_path: Path) -> Path:
    """Repo with a core/ and web/ package so module filtering has real data."""
    _write(
        tmp_path / "src" / "core" / "indexer.py",
        "def index_repo(path):\n    return {}\n",
    )
    _write(
        tmp_path / "src" / "core" / "parser.py",
        "def parse(text):\n    return []\n",
    )
    _write(
        tmp_path / "src" / "web" / "app.py",
        "from core.indexer import index_repo\n\ndef run():\n    return index_repo('.')\n",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests for _refactoring_risk
# ---------------------------------------------------------------------------


def test_refactoring_risk_high() -> None:
    from local_deepwiki.generators.analysis.module_health import _refactoring_risk

    assert _refactoring_risk(15) == "high"
    assert _refactoring_risk(20) == "high"


def test_refactoring_risk_medium() -> None:
    from local_deepwiki.generators.analysis.module_health import _refactoring_risk

    assert _refactoring_risk(5) == "medium"
    assert _refactoring_risk(14) == "medium"


def test_refactoring_risk_low() -> None:
    from local_deepwiki.generators.analysis.module_health import _refactoring_risk

    assert _refactoring_risk(0) == "low"
    assert _refactoring_risk(4) == "low"


# ---------------------------------------------------------------------------
# Integration tests for analyze_module_health
# ---------------------------------------------------------------------------


def test_analyze_module_health_returns_required_keys(module_repo: Path) -> None:
    from local_deepwiki.generators.analysis.module_health import analyze_module_health

    result = analyze_module_health(module_repo, "core")

    assert result["status"] == "success"
    assert result["module"] == "core"
    assert "health" in result
    assert "coupling" in result
    assert "refactoring_risk" in result
    assert "hotspots" in result
    assert "smells" in result
    assert "dependents" in result
    assert "dependencies" in result
    assert "stats" in result


def test_analyze_module_health_score_in_range(module_repo: Path) -> None:
    from local_deepwiki.generators.analysis.module_health import analyze_module_health

    result = analyze_module_health(module_repo, "core")
    health = result["health"]

    assert 0 <= health["score"] <= 100
    assert health["grade"] in ("A", "B", "C", "D", "F")


def test_analyze_module_health_refactoring_risk_values(module_repo: Path) -> None:
    from local_deepwiki.generators.analysis.module_health import analyze_module_health

    result = analyze_module_health(module_repo, "core")
    assert result["refactoring_risk"] in ("low", "medium", "high")


def test_analyze_module_health_coupling_keys(module_repo: Path) -> None:
    from local_deepwiki.generators.analysis.module_health import analyze_module_health

    result = analyze_module_health(module_repo, "core")
    coupling = result["coupling"]

    # Should always have the coupling fields (either real or defaults)
    assert "afferent_coupling" in coupling
    assert "efferent_coupling" in coupling


def test_analyze_module_health_stats_keys(module_repo: Path) -> None:
    from local_deepwiki.generators.analysis.module_health import analyze_module_health

    result = analyze_module_health(module_repo, "core")
    stats = result["stats"]

    assert "functions" in stats
    assert "smells_count" in stats
    assert "dependents_count" in stats
    assert "dependencies_count" in stats
    assert isinstance(stats["functions"], int)
    assert stats["functions"] >= 0


def test_analyze_module_health_nonexistent_module_graceful(
    module_repo: Path,
) -> None:
    """A module that has no matching files should return empty results gracefully."""
    from local_deepwiki.generators.analysis.module_health import analyze_module_health

    result = analyze_module_health(module_repo, "nonexistent.module")

    assert result["status"] == "success"
    assert result["module"] == "nonexistent.module"
    assert result["stats"]["functions"] == 0
    assert result["stats"]["smells_count"] == 0
    # Grade should still be a valid letter
    assert result["health"]["grade"] in ("A", "B", "C", "D", "F")


def test_analyze_module_health_hotspots_filtered(module_repo: Path) -> None:
    """Hotspots should only contain entries from the requested module."""
    from local_deepwiki.generators.analysis.module_health import analyze_module_health

    result = analyze_module_health(module_repo, "core")

    for hotspot in result["hotspots"]:
        assert "core" in hotspot.get("file", ""), (
            f"Expected 'core' in file path, got: {hotspot.get('file')}"
        )


def test_analyze_module_health_smells_filtered(module_repo: Path) -> None:
    """Smells should only contain entries from the requested module."""
    from local_deepwiki.generators.analysis.module_health import analyze_module_health

    result = analyze_module_health(module_repo, "core")

    for smell in result["smells"]:
        assert "core" in smell.get("file", ""), (
            f"Expected 'core' in file path, got: {smell.get('file')}"
        )


def test_analyze_module_health_dependents_and_dependencies_are_lists(
    module_repo: Path,
) -> None:
    from local_deepwiki.generators.analysis.module_health import analyze_module_health

    result = analyze_module_health(module_repo, "core")

    assert isinstance(result["dependents"], list)
    assert isinstance(result["dependencies"], list)


def test_analyze_module_health_empty_repo(tmp_path: Path) -> None:
    """Empty repo should not raise — returns zero-result success."""
    from local_deepwiki.generators.analysis.module_health import analyze_module_health

    result = analyze_module_health(tmp_path, "some.module")

    assert result["status"] == "success"
    assert result["stats"]["functions"] == 0


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_get_module_health_handler(module_repo: Path) -> None:
    """Handler should return valid JSON with health data."""
    import json

    from local_deepwiki.handlers.analysis_architecture import handle_get_module_health

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None

    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_module_health(
            {"repo_path": str(module_repo), "module_name": "core"}
        )

    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["module"] == "core"
    assert "health" in data
    assert "refactoring_risk" in data


@pytest.mark.asyncio
async def test_handle_get_module_health_missing_repo() -> None:
    """Handler returns error for nonexistent repo."""
    from local_deepwiki.handlers.analysis_architecture import handle_get_module_health

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None

    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_module_health(
            {"repo_path": "/nonexistent/xyz", "module_name": "core"}
        )

    assert len(result) == 1
    assert "error" in result[0].text.lower() or "not found" in result[0].text.lower()


@pytest.mark.asyncio
async def test_handle_get_module_health_missing_module_name() -> None:
    """Handler returns validation error when module_name is absent."""
    import json

    from local_deepwiki.handlers.analysis_architecture import handle_get_module_health

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None

    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_module_health({"repo_path": "/some/path"})

    assert len(result) == 1
    # Should be an error response (missing required field)
    text = result[0].text
    assert (
        "error" in text.lower()
        or "validation" in text.lower()
        or "module_name" in text.lower()
    )
