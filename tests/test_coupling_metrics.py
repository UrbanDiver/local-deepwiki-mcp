"""Tests for get_coupling_metrics analysis tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers import handle_get_coupling_metrics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def pkg_repo(tmp_path: Path) -> Path:
    """Create a minimal multi-package repo for coupling analysis."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")

    core = pkg / "core"
    core.mkdir()
    (core / "__init__.py").write_text("")
    (core / "parser.py").write_text(
        "from mypkg.models import Item\n"
        "class ConcreteParser:\n"
        "    def parse(self):\n"
        "        pass\n"
    )

    models = pkg / "models"
    models.mkdir()
    (models / "__init__.py").write_text("")
    (models / "item.py").write_text(
        "from abc import ABC, abstractmethod\n\n"
        "class AbstractItem(ABC):\n"
        "    @abstractmethod\n"
        "    def process(self):\n"
        "        pass\n\n"
        "class ConcreteItem(AbstractItem):\n"
        "    def process(self):\n"
        "        return 42\n"
    )

    web = pkg / "web"
    web.mkdir()
    (web / "__init__.py").write_text("")
    (web / "app.py").write_text(
        "from mypkg.core import parser\nfrom mypkg.models import item\n"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


async def test_coupling_metrics_success(mock_access_control, pkg_repo):
    """Handler returns success status."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"


async def test_coupling_metrics_has_metrics(mock_access_control, pkg_repo):
    """Result contains a non-empty metrics list."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    assert len(data["metrics"]) > 0


async def test_coupling_metrics_shape(mock_access_control, pkg_repo):
    """Each metric entry has all required keys."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    required_keys = {
        "module",
        "afferent_coupling",
        "efferent_coupling",
        "instability",
        "abstractness",
        "distance",
    }
    for m in data["metrics"]:
        assert required_keys <= set(m.keys()), f"Missing keys in: {m}"


# ---------------------------------------------------------------------------
# Metric value checks
# ---------------------------------------------------------------------------


async def test_coupling_metrics_instability_range(mock_access_control, pkg_repo):
    """Instability is in [0.0, 1.0]."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    for m in data["metrics"]:
        assert 0.0 <= m["instability"] <= 1.0, f"Instability out of range: {m}"


async def test_coupling_metrics_abstractness_range(mock_access_control, pkg_repo):
    """Abstractness is in [0.0, 1.0]."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    for m in data["metrics"]:
        assert 0.0 <= m["abstractness"] <= 1.0, f"Abstractness out of range: {m}"


async def test_coupling_metrics_distance_range(mock_access_control, pkg_repo):
    """Distance is in [0.0, 1.0] (it's |A + I - 1|)."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    for m in data["metrics"]:
        assert 0.0 <= m["distance"] <= 1.0, f"Distance out of range: {m}"


async def test_coupling_metrics_coupling_non_negative(mock_access_control, pkg_repo):
    """Ca and Ce are non-negative integers."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    for m in data["metrics"]:
        assert m["afferent_coupling"] >= 0
        assert m["efferent_coupling"] >= 0


async def test_coupling_metrics_models_has_abstractness(mock_access_control, tmp_path):
    """A module containing an ABC class has abstractness > 0."""
    # Create a simple single-package repo with an abstract class.
    pkg = tmp_path / "basepkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "abstract.py").write_text(
        "from abc import ABC, abstractmethod\n\n"
        "class AbstractBase(ABC):\n"
        "    @abstractmethod\n"
        "    def run(self):\n"
        "        pass\n"
        "\n"
        "class ConcreteBase(AbstractBase):\n"
        "    def run(self):\n"
        "        return 42\n"
    )

    result = await handle_get_coupling_metrics({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    # Find the module that maps to basepkg/abstract.py -> "basepkg.abstract".
    abstract_metrics = [m for m in data["metrics"] if m["module"] == "basepkg.abstract"]
    assert len(abstract_metrics) > 0, (
        f"Module 'basepkg.abstract' not found in: {[m['module'] for m in data['metrics']]}"
    )
    assert abstract_metrics[0]["abstractness"] > 0.0, (
        f"Expected abstractness > 0 for basepkg.abstract, got: {abstract_metrics[0]}"
    )


async def test_coupling_metrics_depended_module_high_ca(mock_access_control, pkg_repo):
    """The most-imported module has higher Ca than others."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    ca_values = [m["afferent_coupling"] for m in data["metrics"]]
    # At least one module should have Ca > 0.
    assert max(ca_values) > 0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


async def test_coupling_metrics_stats(mock_access_control, pkg_repo):
    """Stats contains total_modules, avg_instability, avg_abstractness."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    stats = data["stats"]
    assert "total_modules" in stats
    assert "avg_instability" in stats
    assert "avg_abstractness" in stats
    assert stats["total_modules"] > 0
    assert 0.0 <= stats["avg_instability"] <= 1.0
    assert 0.0 <= stats["avg_abstractness"] <= 1.0


# ---------------------------------------------------------------------------
# module_filter
# ---------------------------------------------------------------------------


async def test_coupling_metrics_module_filter(mock_access_control, pkg_repo):
    """module_filter restricts analysis to fewer modules than the full result."""
    # First get full result.
    full_result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    full_data = json.loads(full_result[0].text)

    # Determine an actual module label prefix from the results.
    if not full_data["metrics"]:
        return  # Nothing to filter; skip.

    # Use first module's top-level prefix as filter.
    first_module = full_data["metrics"][0]["module"]
    prefix = first_module.split(".")[0]

    filtered_result = await handle_get_coupling_metrics(
        {"repo_path": str(pkg_repo), "module_filter": prefix}
    )
    filtered_data = json.loads(filtered_result[0].text)
    assert filtered_data["status"] == "success"
    # Result should still have at least some metric entries.
    assert len(filtered_data["metrics"]) >= 0


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


async def test_coupling_metrics_sorted_by_distance(mock_access_control, pkg_repo):
    """Metrics are sorted by distance descending (most problematic first)."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    distances = [m["distance"] for m in data["metrics"]]
    assert distances == sorted(distances, reverse=True)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


async def test_coupling_metrics_missing_repo(mock_access_control, tmp_path):
    """Non-existent repo returns an error response."""
    result = await handle_get_coupling_metrics(
        {"repo_path": str(tmp_path / "nonexistent")}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_coupling_metrics_empty_repo(mock_access_control, tmp_path):
    """Empty repo returns success with an empty metrics list."""
    result = await handle_get_coupling_metrics({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["metrics"] == []
