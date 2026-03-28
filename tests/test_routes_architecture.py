"""Tests for the architecture dashboard blueprint."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Skip all tests if Flask is not installed
flask = pytest.importorskip("flask")


@pytest.fixture
def app(tmp_path):
    """Create a test Flask app with the architecture blueprint."""
    from local_deepwiki.web.routes_architecture import architecture_bp

    app = flask.Flask(
        __name__,
        template_folder=str(
            Path(__file__).parent.parent
            / "src"
            / "local_deepwiki"
            / "web"
            / "templates"
        ),
    )
    app.config["TESTING"] = True
    app.register_blueprint(architecture_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_graph_api_returns_nodes_and_edges(client, tmp_path):
    """GET /architecture/api/graph returns vis.js format."""
    mock_result = {
        "modules": [
            {"name": "core", "file_count": 5, "line_count": 1000},
            {"name": "web", "file_count": 3, "line_count": 500},
        ],
        "edges": [
            {"source": "web", "target": "core", "weight": 10},
        ],
        "stats": {"total_modules": 2, "total_edges": 1},
    }
    with patch(
        "local_deepwiki.generators.analysis.module_dependencies.analyze_cross_module_dependencies",
        return_value=mock_result,
    ):
        resp = client.get(f"/architecture/api/graph?repo_path={tmp_path}")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 2
    assert data["nodes"][0]["id"] == "core"


def test_health_api_returns_scores(client, tmp_path):
    """GET /architecture/api/health returns grade and dimensions."""
    mock_health = {
        "overall": {
            "score": 72.5,
            "grade": "B",
            "dimensions": {
                "complexity": {"score": 77, "grade": "B"},
                "coupling": {"score": 44, "grade": "D"},
                "smells": {"score": 28, "grade": "F"},
                "layers": {"score": 100, "grade": "A"},
            },
        },
        "stats": {"total_lines": 10000, "total_functions": 200, "files_scanned": 50},
    }
    with (
        patch(
            "local_deepwiki.generators.analysis.architecture_health.analyze_architecture_health",
            return_value=mock_health,
        ),
        patch(
            "local_deepwiki.core.health_history.load_snapshots",
            return_value=[],
        ),
        patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=MagicMock(name="test-project"),
        ),
    ):
        resp = client.get(f"/architecture/api/health?repo_path={tmp_path}")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["overall"]["grade"] == "B"
    assert "dimensions" in data


def test_graph_api_missing_repo_path(client):
    """Missing repo_path returns 400."""
    resp = client.get("/architecture/api/graph")
    assert resp.status_code == 400


def test_module_api_returns_health(client, tmp_path):
    """GET /architecture/api/module/<name> returns module health."""
    mock_result = {
        "status": "success",
        "health": {"score": 75, "grade": "B"},
    }
    with patch(
        "local_deepwiki.generators.analysis.module_health.analyze_module_health",
        return_value=mock_result,
    ):
        resp = client.get(f"/architecture/api/module/core?repo_path={tmp_path}")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["status"] == "success"


def test_tour_api_returns_data(client, tmp_path):
    """GET /architecture/api/tour/<topic> returns tour stops."""
    mock_result = {
        "topic": "authentication",
        "stops": [
            {
                "title": "Entry point",
                "file": "auth.py",
                "line": 1,
                "description": "Start here",
            },
        ],
    }
    with patch.dict(
        "sys.modules",
        {
            "local_deepwiki.generators.analysis.tours": MagicMock(
                generate_tour=MagicMock(return_value=mock_result)
            )
        },
    ):
        resp = client.get(f"/architecture/api/tour/authentication?repo_path={tmp_path}")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["topic"] == "authentication"
    assert len(data["stops"]) == 1


def test_graph_api_error_returns_500(client, tmp_path):
    """Graph API returns 500 when analysis raises an exception."""
    with patch(
        "local_deepwiki.generators.analysis.module_dependencies.analyze_cross_module_dependencies",
        side_effect=RuntimeError("analysis failed"),
    ):
        resp = client.get(f"/architecture/api/graph?repo_path={tmp_path}")
    assert resp.status_code == 500
    data = json.loads(resp.data)
    assert "error" in data
