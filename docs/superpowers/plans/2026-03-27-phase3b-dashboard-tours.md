# Phase 3b: Architecture Dashboard + Guided Tours — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an interactive web architecture explorer at `/architecture` with vis.js dependency graph, health stats footer, module detail slide-out panel, and guided tours (both as MCP tool and integrated into the dashboard).

**Architecture:** Flask blueprint (`routes_architecture.py`) with JSON API endpoints that call existing generators. Jinja template loads vis.js + Chart.js from CDN. Tour generator (`tours.py`) is a pure function following the recommendations/onboarding pattern. Tours integrate into the dashboard via a "Tours" tab in the slide-out panel.

**Tech Stack:** Python 3.11+, Flask, Jinja2, vis.js (CDN), Chart.js (CDN), Pydantic, pytest

**Spec:** `docs/superpowers/specs/2026-03-27-phase3b-dashboard-tours-design.md`

---

### Task 1: Create architecture blueprint with API endpoints

**Files:**
- Create: `src/local_deepwiki/web/routes_architecture.py`
- Modify: `src/local_deepwiki/web/app.py` (register blueprint)
- Create: `tests/test_routes_architecture.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_routes_architecture.py
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

    app = flask.Flask(__name__, template_folder=str(
        Path(__file__).parent.parent / "src" / "local_deepwiki" / "web" / "templates"
    ))
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
        "local_deepwiki.web.routes_architecture.analyze_cross_module_dependencies",
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
    with patch(
        "local_deepwiki.web.routes_architecture.analyze_architecture_health",
        return_value=mock_health,
    ), patch(
        "local_deepwiki.web.routes_architecture.load_snapshots",
        return_value=[],
    ), patch(
        "local_deepwiki.web.routes_architecture.get_cached_manifest",
        return_value=MagicMock(name="test-project"),
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
        "local_deepwiki.web.routes_architecture.analyze_module_health",
        return_value=mock_result,
    ):
        resp = client.get(f"/architecture/api/module/core?repo_path={tmp_path}")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["status"] == "success"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_routes_architecture.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement blueprint**

Create `src/local_deepwiki/web/routes_architecture.py`:

```python
"""Architecture dashboard routes for the DeepWiki web UI.

Provides the interactive architecture visualization page and JSON API
endpoints for graph data, health scores, module details, and tours.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

architecture_bp = Blueprint("architecture", __name__)

_DISTANCE_COLORS = {
    "healthy": "#2d6a4f",   # green — D < 0.3
    "warning": "#f4a261",   # yellow — 0.3 <= D <= 0.7
    "danger": "#e76f51",    # red — D > 0.7
}

_HIGH_DISTANCE = 0.7
_WARNING_DISTANCE = 0.3


def _get_repo_path():
    """Extract and validate repo_path from query params."""
    repo_path = request.args.get("repo_path")
    if not repo_path:
        return None, jsonify({"error": "repo_path query parameter required"}), 400
    path = Path(repo_path).resolve()
    if not path.is_dir():
        return None, jsonify({"error": f"Not a directory: {repo_path}"}), 400
    return path, None, None


def _node_color(distance: float) -> str:
    """Map coupling distance to a color."""
    if distance > _HIGH_DISTANCE:
        return _DISTANCE_COLORS["danger"]
    if distance > _WARNING_DISTANCE:
        return _DISTANCE_COLORS["warning"]
    return _DISTANCE_COLORS["healthy"]


@architecture_bp.route("/architecture")
def architecture_page():
    """Render the architecture dashboard page."""
    return render_template("architecture.html")


@architecture_bp.route("/architecture/api/graph")
def graph_api():
    """Return module dependency graph formatted for vis.js."""
    repo_path, error, status = _get_repo_path()
    if error:
        return error, status

    from local_deepwiki.generators.analysis.module_dependencies import (
        analyze_cross_module_dependencies,
    )

    try:
        result = analyze_cross_module_dependencies(repo_path=repo_path)
    except Exception as e:
        logger.error("Graph API error: %s", e)
        return jsonify({"error": str(e)}), 500

    # Also get coupling metrics for node coloring
    distances = {}
    try:
        from local_deepwiki.generators.analysis.coupling import (
            analyze_coupling_metrics,
        )

        coupling = analyze_coupling_metrics(repo_path=repo_path)
        distances = {
            m["module"]: m.get("distance", 0)
            for m in coupling.get("metrics", [])
        }
    except Exception:
        pass  # Coupling data is optional for coloring

    nodes = []
    for mod in result.get("modules", []):
        name = mod.get("name", "")
        dist = distances.get(name, 0)
        nodes.append({
            "id": name,
            "label": name,
            "file_count": mod.get("file_count", 0),
            "line_count": mod.get("line_count", 0),
            "distance": round(dist, 2),
            "color": _node_color(dist),
        })

    edges = []
    for edge in result.get("edges", []):
        edges.append({
            "from": edge.get("source", ""),
            "to": edge.get("target", ""),
            "weight": edge.get("weight", 1),
            "label": str(edge.get("weight", "")),
        })

    return jsonify({"nodes": nodes, "edges": edges})


@architecture_bp.route("/architecture/api/health")
def health_api():
    """Return current architecture health scores and trend data."""
    repo_path, error, status = _get_repo_path()
    if error:
        return error, status

    from local_deepwiki.core.health_history import load_snapshots
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )
    from local_deepwiki.generators.manifest import get_cached_manifest

    try:
        manifest = get_cached_manifest(repo_path)
        project_name = manifest.name or repo_path.name
        health = analyze_architecture_health(repo_path, project_name)
    except Exception as e:
        logger.error("Health API error: %s", e)
        return jsonify({"error": str(e)}), 500

    overall = health.get("overall", {})
    dims = overall.get("dimensions", {})
    stats = health.get("stats", {})

    # Load trend data
    wiki_path = repo_path / ".deepwiki"
    snapshots = load_snapshots(wiki_path)
    trend = [
        {"timestamp": s.get("timestamp", ""), "score": s.get("score", 0)}
        for s in snapshots[-30:]  # last 30 snapshots
    ]

    # Count high-coupling modules
    high_coupling = sum(
        1 for d in dims.get("coupling", {}).get("factors", {}).values()
        if isinstance(d, (int, float)) and d > _HIGH_DISTANCE
    )

    return jsonify({
        "overall": {"score": overall.get("score"), "grade": overall.get("grade")},
        "dimensions": {
            name: {"score": d.get("score"), "grade": d.get("grade")}
            for name, d in dims.items()
        },
        "stats": {
            "total_modules": stats.get("total_modules", 0),
            "high_coupling": high_coupling,
            "total_smells": stats.get("total_smells", 0),
        },
        "trend": trend,
    })


@architecture_bp.route("/architecture/api/module/<name>")
def module_api(name):
    """Return health details for a specific module."""
    repo_path, error, status = _get_repo_path()
    if error:
        return error, status

    from local_deepwiki.generators.analysis.module_health import (
        analyze_module_health,
    )

    try:
        result = analyze_module_health(repo_path, name)
    except Exception as e:
        logger.error("Module API error for %s: %s", name, e)
        return jsonify({"error": str(e)}), 500

    return jsonify(result)


@architecture_bp.route("/architecture/api/tour/<topic>")
def tour_api(topic):
    """Return guided tour stops for a topic."""
    repo_path, error, status = _get_repo_path()
    if error:
        return error, status

    from local_deepwiki.generators.analysis.tours import generate_tour

    try:
        result = generate_tour(repo_path, topic=topic)
    except Exception as e:
        logger.error("Tour API error for %s: %s", topic, e)
        return jsonify({"error": str(e)}), 500

    return jsonify(result)
```

- [ ] **Step 4: Register blueprint in app.py**

In `src/local_deepwiki/web/app.py`, add after the codemap blueprint registration (~line 85):

```python
    from local_deepwiki.web.routes_architecture import architecture_bp  # noqa: E402

    app.register_blueprint(architecture_bp)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_routes_architecture.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/local_deepwiki/web/routes_architecture.py src/local_deepwiki/web/app.py tests/test_routes_architecture.py
git commit -m "feat: add architecture dashboard blueprint with API endpoints"
```

---

### Task 2: Create architecture dashboard template

**Files:**
- Create: `src/local_deepwiki/web/templates/architecture.html`

This is the largest single file — the interactive dashboard with vis.js graph, Chart.js sparkline, stats footer, and slide-out panel. No Python tests for this task (tested manually via `deepwiki serve`).

- [ ] **Step 1: Create the template**

Create `src/local_deepwiki/web/templates/architecture.html` — a full Jinja template extending `base.html` that:

1. Loads vis.js and Chart.js from CDN
2. On page load, fetches `/architecture/api/graph` and `/architecture/api/health`
3. Renders the vis.js network graph (full width, ~85vh)
4. Renders the stats footer (grade badge, module count, coupling count, smell count, sparkline)
5. On node click, fetches `/architecture/api/module/<name>` and shows slide-out panel
6. Has a "Tours" button in the footer that shows tour topics in the panel
7. Tour stop navigation highlights graph nodes

The template should be self-contained (all JS inline in `<script>` tags, all CSS inline in `<style>` tags within the `{% block content %}` section).

Key vis.js options:
- Physics: `barnesHut` with moderate gravity
- Interaction: click to select, hover for tooltip
- Node sizing: `value` property mapped from `file_count`
- Edge arrows: `to` direction

**Note for implementer:** This is a large HTML file (~400-500 lines). Focus on getting the graph rendering and stats footer working first. The slide-out panel and tour integration are wired up in subsequent steps. The template MUST extend `base.html` using `{% extends "base.html" %}` and `{% block content %}`.

- [ ] **Step 2: Verify manually**

Run: `uv run deepwiki serve .deepwiki` and visit `http://localhost:8080/architecture`

- [ ] **Step 3: Commit**

```bash
git add src/local_deepwiki/web/templates/architecture.html
git commit -m "feat: add architecture dashboard template with vis.js graph"
```

---

### Task 3: Create guided tour generator

**Files:**
- Create: `src/local_deepwiki/generators/analysis/tours.py`
- Create: `tests/test_tours.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_tours.py
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
        "from src.models.item import Item\n\n"
        "def index():\n    return Item()\n"
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tours.py -v`
Expected: FAIL

- [ ] **Step 3: Implement tour generator**

Create `src/local_deepwiki/generators/analysis/tours.py`:

```python
"""Guided tour generator for codebase exploration.

Generates topic-focused reading guides with ordered file stops
and explanations. Template-based by default; optional LLM enrichment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# File name patterns for topic detection
_TOPIC_PATTERNS: dict[str, list[str]] = {
    "data_flow": [
        "indexer", "pipeline", "processor", "store", "database",
        "ingest", "transform", "loader", "import", "export",
    ],
    "request_handling": [
        "server", "handler", "route", "app", "middleware",
        "api", "endpoint", "view", "controller",
    ],
    "testing": [
        "conftest", "fixture", "test_", "mock", "factory",
    ],
    "architecture": [
        "server", "handler", "core", "model", "provider",
        "generator", "cli", "web", "plugin",
    ],
}

_TOPIC_TITLES: dict[str, str] = {
    "architecture": "Architecture Overview",
    "data_flow": "How Data Flows Through the System",
    "request_handling": "Request Handling Lifecycle",
    "testing": "Testing Organization and Patterns",
}

_MODULE_EXPLANATIONS: dict[str, str] = {
    "server": "Entry point where requests arrive and are dispatched.",
    "handler": "Request handlers that orchestrate business logic.",
    "core": "Core domain logic and shared utilities.",
    "model": "Data models and domain objects.",
    "provider": "External service integrations (LLM, embedding, etc.).",
    "generator": "Content and analysis generators.",
    "cli": "Command-line interface entry points.",
    "web": "Web UI routes and templates.",
    "plugin": "Extension points and plugin interfaces.",
    "test": "Test infrastructure and fixtures.",
    "conftest": "Shared test fixtures and configuration.",
}


def generate_tour(
    repo_path: Path,
    *,
    topic: str = "architecture",
    max_stops: int = 10,
) -> dict[str, Any]:
    """Generate a guided tour of the codebase.

    Args:
        repo_path: Path to the repository root.
        topic: Tour topic (architecture, data_flow, request_handling, testing).
        max_stops: Maximum number of stops.

    Returns:
        Dict with status, topic, title, stops list, and summary.
    """
    # Resolve topic patterns
    if topic.startswith("custom:"):
        query = topic[7:].lower()
        patterns = query.split()
    else:
        patterns = _TOPIC_PATTERNS.get(topic, _TOPIC_PATTERNS["architecture"])

    title = _TOPIC_TITLES.get(topic, f"Tour: {topic}")

    # Scan for matching files
    stops = _find_tour_stops(repo_path, patterns, topic)
    stops = stops[:max_stops]

    summary = _generate_summary(topic, stops)

    return {
        "status": "success",
        "topic": topic,
        "title": title,
        "stops": stops,
        "summary": summary,
        "tool": "get_guided_tour",
    }


def _find_tour_stops(
    repo_path: Path,
    patterns: list[str],
    topic: str,
) -> list[dict[str, Any]]:
    """Find and order tour stops by relevance and dependency flow."""
    candidates: list[dict[str, Any]] = []

    for py_file in sorted(repo_path.rglob("*.py")):
        try:
            rel = py_file.relative_to(repo_path)
        except ValueError:
            continue
        parts = rel.parts
        if any(p.startswith(".") or p in ("node_modules", "__pycache__") for p in parts):
            continue

        file_str = str(rel)
        stem = py_file.stem
        module = _file_to_module(rel)

        # Score by pattern match
        score = 0
        for pattern in patterns:
            if pattern in stem.lower():
                score += 2
            if pattern in file_str.lower():
                score += 1

        if score > 0:
            explanation = _explain_file(stem, module, topic)
            candidates.append({
                "file": file_str,
                "module": module,
                "section": stem,
                "explanation": explanation,
                "line": 1,
                "_score": score,
            })

    # Sort by score descending, then by path for stability
    candidates.sort(key=lambda s: (-s["_score"], s["file"]))

    # Remove internal score field
    for c in candidates:
        del c["_score"]

    return candidates


def _file_to_module(rel_path: Path) -> str:
    """Convert relative file path to a module name."""
    parts = list(rel_path.parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else "root"


def _explain_file(stem: str, module: str, topic: str) -> str:
    """Generate a template explanation for a file."""
    # Check known module explanations
    for key, explanation in _MODULE_EXPLANATIONS.items():
        if key in stem.lower() or key in module.lower():
            return explanation

    # Fallback
    return f"Part of the {module} module."


def _generate_summary(topic: str, stops: list[dict[str, Any]]) -> str:
    """Generate a summary sentence for the tour."""
    if not stops:
        return "No relevant files found for this topic."

    modules = list(dict.fromkeys(s["module"].split(".")[0] for s in stops))
    module_list = ", ".join(modules[:5])

    summaries = {
        "architecture": f"The codebase is organized around {len(modules)} key areas: {module_list}.",
        "data_flow": f"Data flows through {len(stops)} processing stages across {module_list}.",
        "request_handling": f"Requests are handled through a {len(stops)}-step pipeline: {module_list}.",
        "testing": f"Tests are organized across {len(stops)} files covering {module_list}.",
    }
    return summaries.get(topic, f"This tour covers {len(stops)} files in {module_list}.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tours.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/tours.py tests/test_tours.py
git commit -m "feat: add guided tour generator"
```

---

### Task 4: Create `get_guided_tour` MCP tool handler + registration

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py` (add `GetGuidedTourArgs`)
- Modify: `src/local_deepwiki/models/__init__.py` (export)
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (add tool def)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py` (add handler)
- Modify: `src/local_deepwiki/handlers/analysis.py` (export)
- Modify: `src/local_deepwiki/handlers/__init__.py` (export)
- Modify: `src/local_deepwiki/server.py` (register)
- Create: `tests/test_tour_handler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_tour_handler.py
"""Tests for the get_guided_tour MCP tool handler."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "server.py").write_text("def main():\n    pass\n")
    (src / "handler.py").write_text("def handle():\n    pass\n")
    return tmp_path


async def test_handler_returns_tour(mock_access_control, sample_repo):
    from local_deepwiki.handlers.analysis_architecture import handle_get_guided_tour

    result = await handle_get_guided_tour({"repo_path": str(sample_repo)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "stops" in data
    assert "summary" in data


async def test_handler_missing_repo(mock_access_control, tmp_path):
    from local_deepwiki.handlers.analysis_architecture import handle_get_guided_tour

    result = await handle_get_guided_tour(
        {"repo_path": str(tmp_path / "nonexistent")}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_handler_with_topic(mock_access_control, sample_repo):
    from local_deepwiki.handlers.analysis_architecture import handle_get_guided_tour

    result = await handle_get_guided_tour(
        {"repo_path": str(sample_repo), "topic": "testing"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["topic"] == "testing"
```

- [ ] **Step 2: Add args model**

In `src/local_deepwiki/models/tool_args.py`, add after `GetArchitectureTrendsArgs`:

```python
class GetGuidedTourArgs(BaseModel):
    """Arguments for the get_guided_tour tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    topic: str = Field(
        default="architecture",
        description="Tour topic: architecture, data_flow, request_handling, testing, or custom:<query>",
    )
    max_stops: int = Field(
        default=10, ge=1, le=30,
        description="Maximum tour stops (1-30)",
    )
    enrich: bool = Field(
        default=False,
        description="Use LLM for richer explanations (slower)",
    )
```

Export from `models/__init__.py`.

- [ ] **Step 3: Add tool definition**

In `tool_defs/analysis.py`, add the tool definition from the spec (Section 2.4).

- [ ] **Step 4: Add handler**

In `handlers/analysis_architecture.py`, add:

```python
@handle_tool_errors
async def handle_get_guided_tour(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_guided_tour tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetGuidedTourArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.tours import generate_tour

    result = generate_tour(
        repo_path,
        topic=validated.topic,
        max_stops=validated.max_stops,
    )

    logger.info(
        "Guided tour: %s (%d stops) in %s",
        validated.topic,
        len(result.get("stops", [])),
        repo_path,
    )
    return make_tool_text_content("get_guided_tour", result)
```

- [ ] **Step 5: Export and register**

Add `handle_get_guided_tour` to `handlers/analysis.py`, `handlers/__init__.py`, and `server.py`.
Add `GetGuidedTourArgs` to `models/__init__.py`.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_tour_handler.py tests/test_tours.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/models/__init__.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py src/local_deepwiki/handlers/analysis.py src/local_deepwiki/handlers/__init__.py src/local_deepwiki/server.py tests/test_tour_handler.py
git commit -m "feat: add get_guided_tour MCP tool handler"
```

---

### Task 5: Add tool keywords and update CLAUDE.md

**Files:**
- Modify: `src/local_deepwiki/handlers/agentic_data.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add tool keywords**

In `_TOOL_KEYWORDS`:

```python
"get_guided_tour": [
    "tour",
    "guide",
    "walkthrough",
    "explore",
    "learn",
    "onboard",
    "reading order",
],
```

- [ ] **Step 2: Update CLAUDE.md**

1. Update Analysis & Search Tools count from 14 to 15. Add `get_guided_tour`.
2. Add to Analysis & Search Tools table:
   ```
   | `get_guided_tour` | Topic-focused codebase tour with ordered file stops | No |
   ```
3. Add to generators/analysis component table:
   ```
   | Tours | `analysis/tours.py` | Guided tour generator with topic detection |
   ```
4. Add web route documentation noting `/architecture` dashboard.
5. Add workflow chains:
   ```
   - `get_guided_tour` -> `explain_entity` (tour stop, then deep-dive)
   - `get_guided_tour` -> `get_file_context` (tour stop, then explore file role)
   ```

- [ ] **Step 3: Commit**

```bash
git add src/local_deepwiki/handlers/agentic_data.py CLAUDE.md
git commit -m "docs: add tool keywords and update CLAUDE.md for Phase 3b"
```
