"""Tests for the guided tour generator."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a repo with recognizable structure for tour detection."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "server.py").write_text(
        "from src.handlers import api\n\n"
        "def main():\n    app = create_app()\n    app.run()\n"
    )
    handlers = src / "handlers"
    handlers.mkdir()
    (handlers / "__init__.py").write_text("")
    (handlers / "api.py").write_text(
        "from src.core.indexer import index\n\n"
        "def handle_request():\n    return index()\n"
    )
    core = src / "core"
    core.mkdir()
    (core / "__init__.py").write_text("")
    (core / "indexer.py").write_text(
        "from src.models.item import Item\n\ndef index():\n    return Item()\n"
    )
    models = src / "models"
    models.mkdir()
    (models / "__init__.py").write_text("")
    (models / "item.py").write_text("class Item:\n    pass\n")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "conftest.py").write_text("# fixtures\n")
    (tests_dir / "test_api.py").write_text("def test_handle():\n    pass\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
    return tmp_path


def test_generate_tour_architecture(sample_repo):
    """Architecture tour returns ordered stops."""
    from local_deepwiki.generators.analysis.tours import generate_tour

    result = generate_tour(sample_repo, topic="architecture")
    assert result["status"] == "success"
    assert result["topic"] == "architecture"
    assert len(result["stops"]) > 0
    for stop in result["stops"]:
        assert "file" in stop
        assert "module" in stop
        assert "explanation" in stop


def test_generate_tour_testing(sample_repo):
    """Testing tour identifies test directory and conftest."""
    from local_deepwiki.generators.analysis.tours import generate_tour

    result = generate_tour(sample_repo, topic="testing")
    files = [s["file"] for s in result["stops"]]
    assert any("conftest" in f or "test_" in f for f in files)


def test_generate_tour_max_stops(sample_repo):
    """max_stops limits the number of stops."""
    from local_deepwiki.generators.analysis.tours import generate_tour

    result = generate_tour(sample_repo, topic="architecture", max_stops=2)
    assert len(result["stops"]) <= 2


def test_generate_tour_empty_repo(tmp_path):
    """Empty repo returns minimal tour."""
    from local_deepwiki.generators.analysis.tours import generate_tour

    result = generate_tour(tmp_path, topic="architecture")
    assert result["status"] == "success"
    assert "summary" in result


def test_generate_tour_request_handling(sample_repo):
    """Request handling tour identifies server and handler files."""
    from local_deepwiki.generators.analysis.tours import generate_tour

    result = generate_tour(sample_repo, topic="request_handling")
    files = [s["file"] for s in result["stops"]]
    assert any("server" in f for f in files)


def test_generate_tour_data_flow(sample_repo):
    """Data flow tour identifies processing pipeline files."""
    from local_deepwiki.generators.analysis.tours import generate_tour

    result = generate_tour(sample_repo, topic="data_flow")
    files = [s["file"] for s in result["stops"]]
    assert any("indexer" in f or "core" in f for f in files)


def test_generate_tour_custom_topic(sample_repo):
    """Custom topic scans with user-provided keywords."""
    from local_deepwiki.generators.analysis.tours import generate_tour

    result = generate_tour(sample_repo, topic="custom:handler api")
    assert result["status"] == "success"
    files = [s["file"] for s in result["stops"]]
    assert any("handler" in f or "api" in f for f in files)


def test_generate_tour_unknown_topic_falls_back(sample_repo):
    """Unknown topic falls back to architecture patterns."""
    from local_deepwiki.generators.analysis.tours import generate_tour

    result = generate_tour(sample_repo, topic="nonexistent_topic")
    assert result["status"] == "success"
    assert len(result["stops"]) > 0
