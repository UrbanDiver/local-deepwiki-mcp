"""Composite architecture health analysis.

Runs hotspots, coupling, design smells, and layer dependency analysis
in a single pass, then scores each dimension and computes an overall
health grade.

No LLM calls — composes existing pure-analysis functions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.generators.analysis.churn import analyze_churn
from local_deepwiki.generators.analysis.cohesion import analyze_cohesion
from local_deepwiki.generators.analysis.coupling import analyze_coupling_metrics
from local_deepwiki.generators.analysis.duplication import analyze_duplication
from local_deepwiki.generators.analysis.design_smells import analyze_design_smells
from local_deepwiki.generators.analysis.health_scoring import (
    compute_overall,
    score_churn,
    score_cohesion,
    score_complexity,
    score_coupling,
    score_duplication,
    score_layers,
    score_maintainability,
    score_smells,
    score_testability,
)
from local_deepwiki.generators.analysis.maintainability import analyze_maintainability
from local_deepwiki.generators.analysis.testability import analyze_testability
from local_deepwiki.generators.analysis.hotspots import analyze_hotspots
from local_deepwiki.generators.analysis.layer_analysis import analyze_layer_dependencies
from local_deepwiki.generators.analysis.source_filter import iter_python_files
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# How many top findings to include per category in the summary.
_TOP_FINDINGS = 5

# Maximum number of next_steps suggestions to return.
_MAX_NEXT_STEPS = 5

# Score threshold below which a dimension is flagged for follow-up.
_SCORE_WARN_THRESHOLD = 75

# Smell count thresholds for triggering recommendation steps.
_SMELL_THRESHOLD_MEDIUM = 10
_SMELL_THRESHOLD_HIGH = 50


def _generate_next_steps(
    overall: dict[str, Any],
    top_findings: dict[str, Any],
    stats: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate suggested drill-down tool calls based on findings.

    Args:
        overall: Overall score dict with ``dimensions`` sub-dict.
        top_findings: Top findings dict (hotspots, smells, etc.).
        stats: Aggregate stats dict including ``total_smells``.

    Returns:
        List of up to 5 step dicts, each with ``tool``, ``args``, and ``reason``.
    """
    steps: list[dict[str, Any]] = []

    dimensions = overall.get("dimensions", {})
    if dimensions:
        worst_dim = min(dimensions, key=lambda d: dimensions[d].get("score", 100))
        worst_score = dimensions[worst_dim].get("score", 100)
        if worst_score < _SCORE_WARN_THRESHOLD:
            if worst_dim == "smells":
                steps.append(
                    {
                        "tool": "get_design_smells",
                        "args": {"severity_threshold": "high"},
                        "reason": f"Smells dimension scored {worst_score:.0f}/100",
                    }
                )
            elif worst_dim == "coupling":
                steps.append(
                    {
                        "tool": "get_coupling_metrics",
                        "args": {},
                        "reason": f"Coupling dimension scored {worst_score:.0f}/100",
                    }
                )

    hotspot_count = len(top_findings.get("hotspots", []))
    if hotspot_count > 0:
        steps.append(
            {
                "tool": "get_hotspots",
                "args": {"metric": "complexity", "top_n": 20},
                "reason": f"{hotspot_count} complexity hotspots detected",
            }
        )

    total_smells = stats.get("total_smells", 0)
    if total_smells > _SMELL_THRESHOLD_MEDIUM:
        steps.append(
            {
                "tool": "get_recommendations",
                "args": {"enrich": True},
                "reason": (f"{total_smells} design smells found — get prioritized action items"),
            }
        )

    if total_smells > _SMELL_THRESHOLD_HIGH:
        steps.append(
            {
                "tool": "get_hotspots",
                "args": {"metric": "params", "top_n": 10},
                "reason": "High smell count — check for parameter bloat",
            }
        )

    return steps[:_MAX_NEXT_STEPS]


def _count_total_lines(repo_path: Path) -> int:
    """Count total source lines across all Python files (excluding tests)."""
    total = 0
    for full_path, _rel in iter_python_files(repo_path, exclude_tests=True):
        try:
            total += full_path.read_text(encoding="utf-8", errors="replace").count("\n")
        except OSError:
            continue
    return total


def _score_all_dimensions(
    hotspot_result: dict[str, Any],
    coupling_result: dict[str, Any],
    src_smells: list[dict[str, Any]],
    layer_result: dict[str, Any],
    churn_result: dict[str, Any],
    cohesion_result: dict[str, Any],
    duplication_result: dict[str, Any],
    testability_result: dict[str, Any],
    maintainability_result: dict[str, Any],
    total_lines: int,
) -> dict[str, Any]:
    """Compute scored dimension dict from raw analysis results."""
    return {
        "complexity": score_complexity(
            hotspot_result.get("hotspots", []),
            hotspot_result.get("stats", {}).get("total_functions", 0),
        ),
        "coupling": score_coupling(coupling_result.get("metrics", [])),
        "smells": score_smells(src_smells, total_lines),
        "layers": score_layers(layer_result.get("violations", [])),
        "churn": score_churn(
            churn_result.get("composite", []),
            stats=churn_result.get("stats", {}),
        ),
        "cohesion": score_cohesion(
            cohesion_result.get("class_cohesion", []),
            cohesion_result.get("module_cohesion", []),
            stats=cohesion_result.get("stats", {}),
        ),
        "duplication": score_duplication(
            stats=duplication_result.get("stats", {}),
        ),
        "testability": score_testability(
            stats=testability_result.get("stats", {}),
        ),
        "maintainability": score_maintainability(
            stats=maintainability_result.get("stats", {}),
        ),
    }


def analyze_architecture_health(
    repo_path: Path,
    project_name: str,
    *,
    top_findings: int = _TOP_FINDINGS,
) -> dict[str, Any]:
    """Run all architecture analyses and return a scored health report.

    Args:
        repo_path: Repository root.
        project_name: Project name for display.
        top_findings: Number of top findings per category.

    Returns:
        Dict with overall grade, dimension scores, and top findings.
    """
    total_lines = _count_total_lines(repo_path)

    # Run all analyses
    hotspot_result = analyze_hotspots(repo_path, metric="complexity", top_n=50)
    coupling_result = analyze_coupling_metrics(repo_path)
    smell_result = analyze_design_smells(repo_path, severity_threshold="medium")
    layer_result = analyze_layer_dependencies(repo_path, project_name)
    try:
        churn_result = analyze_churn(repo_path)
    except Exception:
        logger.debug("Churn analysis skipped (not a git repo or git error)")
        churn_result = {"composite": [], "stats": {}}

    cohesion_result = analyze_cohesion(repo_path)

    duplication_result = analyze_duplication(repo_path)

    testability_result = analyze_testability(repo_path)

    maintainability_result = analyze_maintainability(repo_path)

    # Filter smells to source-only (exclude test/generated)
    src_smells = [s for s in smell_result.get("smells", []) if s.get("file", "").startswith("src/")]

    dimensions = _score_all_dimensions(
        hotspot_result,
        coupling_result,
        src_smells,
        layer_result,
        churn_result,
        cohesion_result,
        duplication_result,
        testability_result,
        maintainability_result,
        total_lines,
    )
    overall = compute_overall(dimensions)

    # Build top findings
    top_hotspots = hotspot_result.get("hotspots", [])[:top_findings]
    top_smells_high = [s for s in src_smells if s.get("severity") == "high"][:top_findings]
    god_classes = [s for s in src_smells if s.get("type") == "god_class"]

    logger.info(
        "Architecture health: %s (%s) for %s",
        overall["grade"],
        overall["score"],
        repo_path,
    )

    top_findings_dict = {
        "hotspots": top_hotspots,
        "high_severity_smells": top_smells_high,
        "god_classes": god_classes,
        "layer_violations": layer_result.get("violations", [])[:top_findings],
    }
    stats_dict = {
        "total_lines": total_lines,
        "total_functions": hotspot_result.get("stats", {}).get("total_functions", 0),
        "files_scanned": hotspot_result.get("stats", {}).get("files_scanned", 0),
        "total_modules": coupling_result.get("stats", {}).get("total_modules", 0),
        "total_smells": len(src_smells),
    }
    next_steps = _generate_next_steps(overall, top_findings_dict, stats_dict)

    return {
        "status": "success",
        "project_name": project_name,
        "overall": overall,
        "top_findings": top_findings_dict,
        "stats": stats_dict,
        "next_steps": next_steps,
    }
