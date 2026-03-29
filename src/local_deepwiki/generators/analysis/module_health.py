"""Per-module health analysis.

Zooms into a single module and reports its coupling, complexity
distribution, smells, and dependents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.generators.analysis.coupling import analyze_coupling_metrics
from local_deepwiki.generators.analysis.design_smells import analyze_design_smells
from local_deepwiki.generators.analysis.health_scoring import (
    letter_grade,
    score_complexity,
    score_smells,
)
from local_deepwiki.generators.analysis.hotspots import analyze_hotspots
from local_deepwiki.generators.analysis.module_dependencies import (
    analyze_cross_module_dependencies,
)
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


def _refactoring_risk(afferent_coupling: int) -> str:
    """Estimate risk of refactoring based on how many modules depend on this one."""
    if afferent_coupling >= 15:
        return "high"
    if afferent_coupling >= 5:
        return "medium"
    return "low"


def _aggregate_coupling(
    coupling_result: dict[str, Any],
    module_name: str,
) -> dict[str, Any] | None:
    """Aggregate afferent/efferent coupling for a module and its sub-modules.

    Performs an exact match first; if not found, aggregates all sub-modules
    by prefix (e.g. ``module_name="core"`` aggregates ``"core.indexer"``, etc.).

    Returns ``None`` when no coupling data is found for the module.
    """
    prefix = module_name + "."
    aggregate_ca = 0
    aggregate_ce = 0
    matched_any = False
    for m in coupling_result.get("metrics", []):
        mname = m.get("module", "")
        if mname == module_name or mname.startswith(prefix):
            aggregate_ca += m.get("afferent_coupling", 0)
            aggregate_ce += m.get("efferent_coupling", 0)
            matched_any = True
    if not matched_any:
        return None
    total = aggregate_ca + aggregate_ce
    instability = round(aggregate_ce / total, 4) if total > 0 else 0.0
    return {
        "afferent_coupling": aggregate_ca,
        "efferent_coupling": aggregate_ce,
        "instability": instability,
        "abstractness": 0.0,
        "distance": 0.0,
    }


def _build_dependency_lists(
    deps_result: dict[str, Any],
    module_name: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build sorted dependents and dependencies lists from the dependency edge list."""
    dependents: list[dict[str, Any]] = []
    dependencies: list[dict[str, Any]] = []
    for edge in deps_result.get("edges", []):
        if edge.get("target") == module_name:
            dependents.append({"module": edge["source"], "weight": edge["weight"]})
        elif edge.get("source") == module_name:
            dependencies.append({"module": edge["target"], "weight": edge["weight"]})
    dependents.sort(key=lambda d: d["weight"], reverse=True)
    dependencies.sort(key=lambda d: d["weight"], reverse=True)
    return dependents, dependencies


def analyze_module_health(
    repo_path: Path,
    module_name: str,
) -> dict[str, Any]:
    """Analyze health of a single module.

    Args:
        repo_path: Repository root.
        module_name: Module identifier (e.g., 'core.indexer', 'generators.wiki').

    Returns:
        Dict with module coupling, complexity, smells, dependents, and health score.
    """
    # Run analyses filtered/scoped to this module
    hotspot_result = analyze_hotspots(repo_path, metric="complexity", top_n=100)
    smell_result = analyze_design_smells(repo_path, severity_threshold="low")
    coupling_result = analyze_coupling_metrics(repo_path)
    deps_result = analyze_cross_module_dependencies(
        repo_path, module_filter=module_name
    )

    # Filter hotspots and smells to this module's files
    module_path_prefix = module_name.replace(".", "/")
    module_hotspots = [
        h
        for h in hotspot_result.get("hotspots", [])
        if module_path_prefix in h.get("file", "")
    ]
    module_smells = [
        s
        for s in smell_result.get("smells", [])
        if module_path_prefix in s.get("file", "")
    ]

    module_coupling = _aggregate_coupling(coupling_result, module_name)

    # Compute module-level scores
    total_functions = len(module_hotspots)
    complexity_score = score_complexity(module_hotspots, total_functions)

    total_lines = sum(h.get("details", {}).get("length", 0) for h in module_hotspots)
    smell_score = score_smells(module_smells, max(total_lines, 1))

    avg_score = (complexity_score["score"] + smell_score["score"]) / 2
    ca = module_coupling.get("afferent_coupling", 0) if module_coupling else 0

    dependents, dependencies = _build_dependency_lists(deps_result, module_name)

    logger.info("Module health for %s: score=%.1f", module_name, avg_score)

    default_coupling: dict[str, Any] = {
        "afferent_coupling": 0,
        "efferent_coupling": 0,
        "instability": 0,
        "abstractness": 0,
        "distance": 0,
    }

    return {
        "status": "success",
        "module": module_name,
        "health": {
            "score": round(avg_score, 1),
            "grade": letter_grade(avg_score),
            "complexity": complexity_score,
            "smells": smell_score,
        },
        "coupling": module_coupling or default_coupling,
        "refactoring_risk": _refactoring_risk(ca),
        "hotspots": module_hotspots[:10],
        "smells": module_smells,
        "dependents": dependents,
        "dependencies": dependencies,
        "stats": {
            "functions": total_functions,
            "smells_count": len(module_smells),
            "dependents_count": len(dependents),
            "dependencies_count": len(dependencies),
        },
    }
