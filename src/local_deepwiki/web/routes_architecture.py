"""Architecture dashboard routes for the DeepWiki web UI.

Provides the interactive architecture visualization page and JSON API
endpoints for graph data, health scores, module details, and tours.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, jsonify, render_template, request

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

architecture_bp = Blueprint("architecture", __name__)

_DISTANCE_COLORS = {
    "healthy": "#2d6a4f",  # green — D < 0.3
    "warning": "#f4a261",  # yellow — 0.3 <= D <= 0.7
    "danger": "#e76f51",  # red — D > 0.7
}

_HIGH_DISTANCE = 0.7
_WARNING_DISTANCE = 0.3


def _get_repo_path() -> tuple[Path, None, None] | tuple[None, Response, int]:
    """Extract and validate repo_path from query params.

    Returns a tuple of (path, error_response, status_code). On success,
    error_response and status_code are None. On failure, path is None.
    """
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
        from local_deepwiki.errors import sanitize_error_message

        return jsonify({"error": sanitize_error_message(str(e))}), 500

    # Also get coupling metrics for node coloring
    distances = {}
    try:
        from local_deepwiki.generators.analysis.coupling import (
            analyze_coupling_metrics,
        )

        coupling = analyze_coupling_metrics(repo_path=repo_path)
        distances = {
            m["module"]: m.get("distance", 0) for m in coupling.get("metrics", [])
        }
    except Exception:
        logger.debug("Coupling metrics unavailable for node coloring")

    nodes = []
    for mod in result.get("modules", []):
        name = mod.get("name", "")
        dist = distances.get(name, 0)
        nodes.append(
            {
                "id": name,
                "label": name,
                "file_count": mod.get("file_count", 0),
                "line_count": mod.get("line_count", 0),
                "distance": round(dist, 2),
                "color": _node_color(dist),
            }
        )

    edges = []
    for edge in result.get("edges", []):
        edges.append(
            {
                "from": edge.get("source", ""),
                "to": edge.get("target", ""),
                "weight": edge.get("weight", 1),
                "label": str(edge.get("weight", "")),
            }
        )

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
        from local_deepwiki.errors import sanitize_error_message

        return jsonify({"error": sanitize_error_message(str(e))}), 500

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
        1
        for d in dims.get("coupling", {}).get("factors", {}).values()
        if isinstance(d, (int, float)) and d > _HIGH_DISTANCE
    )

    return jsonify(
        {
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
        }
    )


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
        from local_deepwiki.errors import sanitize_error_message

        return jsonify({"error": sanitize_error_message(str(e))}), 500

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
        from local_deepwiki.errors import sanitize_error_message

        return jsonify({"error": sanitize_error_message(str(e))}), 500

    return jsonify(result)
