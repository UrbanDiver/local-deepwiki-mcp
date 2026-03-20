"""Composite architecture health analysis.

Runs hotspots, coupling, design smells, and layer dependency analysis
in a single pass, then scores each dimension and computes an overall
health grade.

No LLM calls — composes existing pure-analysis functions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.generators.analysis.coupling import analyze_coupling_metrics
from local_deepwiki.generators.analysis.design_smells import analyze_design_smells
from local_deepwiki.generators.analysis.health_scoring import (
    compute_overall,
    score_complexity,
    score_coupling,
    score_layers,
    score_smells,
)
from local_deepwiki.generators.analysis.hotspots import analyze_hotspots
from local_deepwiki.generators.analysis.layer_analysis import analyze_layer_dependencies
from local_deepwiki.generators.analysis.source_filter import iter_python_files
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# How many top findings to include per category in the summary.
_TOP_FINDINGS = 5


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
    # Count total lines for density calculations
    total_lines = 0
    for full_path, _rel in iter_python_files(repo_path, exclude_tests=True):
        try:
            total_lines += full_path.read_text(
                encoding="utf-8", errors="replace"
            ).count("\n")
        except OSError:
            continue

    # Run all analyses
    hotspot_result = analyze_hotspots(repo_path, metric="complexity", top_n=50)
    coupling_result = analyze_coupling_metrics(repo_path)
    smell_result = analyze_design_smells(repo_path, severity_threshold="medium")
    layer_result = analyze_layer_dependencies(repo_path, project_name)

    # Filter smells to source-only (exclude test/generated)
    src_smells = [
        s
        for s in smell_result.get("smells", [])
        if s.get("file", "").startswith("src/")
    ]

    # Score each dimension
    complexity_score = score_complexity(
        hotspot_result.get("hotspots", []),
        hotspot_result.get("stats", {}).get("total_functions", 0),
    )
    coupling_score_result = score_coupling(coupling_result.get("metrics", []))
    smell_score = score_smells(src_smells, total_lines)
    layer_score = score_layers(layer_result.get("violations", []))

    dimensions = {
        "complexity": complexity_score,
        "coupling": coupling_score_result,
        "smells": smell_score,
        "layers": layer_score,
    }
    overall = compute_overall(dimensions)

    # Build top findings
    top_hotspots = hotspot_result.get("hotspots", [])[:top_findings]
    top_smells_high = [s for s in src_smells if s.get("severity") == "high"][
        :top_findings
    ]
    god_classes = [s for s in src_smells if s.get("type") == "god_class"]

    logger.info(
        "Architecture health: %s (%s) for %s",
        overall["grade"],
        overall["score"],
        repo_path,
    )

    return {
        "status": "success",
        "project_name": project_name,
        "overall": overall,
        "top_findings": {
            "hotspots": top_hotspots,
            "high_severity_smells": top_smells_high,
            "god_classes": god_classes,
            "layer_violations": layer_result.get("violations", [])[:top_findings],
        },
        "stats": {
            "total_lines": total_lines,
            "total_functions": hotspot_result.get("stats", {}).get(
                "total_functions", 0
            ),
            "files_scanned": hotspot_result.get("stats", {}).get("files_scanned", 0),
            "total_modules": coupling_result.get("stats", {}).get("total_modules", 0),
            "total_smells": len(src_smells),
        },
    }
