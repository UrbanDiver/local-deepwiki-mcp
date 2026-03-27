"""Composite architecture analysis orchestrator.

Runs multiple sub-analyses and delegates to the narrative formatter.
No LLM calls — all synthesis is template-based.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.generators.analysis.architecture_report import (
    format_architecture_report,
)


def analyze_architecture_composite(
    repo_path: Path,
    project_name: str,
    *,
    detail_level: str = "standard",
    focus: str = "all",
) -> dict[str, Any]:
    """Run composite architecture analysis and return narrative report.

    Args:
        repo_path: Path to the repository.
        project_name: Name for display.
        detail_level: "summary", "standard", or "full".
        focus: "all", "complexity", "coupling", or "smells".

    Returns:
        Dict with status, report (markdown string), and raw data.
    """
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )
    from local_deepwiki.generators.analysis.module_dependencies import (
        analyze_cross_module_dependencies,
    )

    top_n_map = {"summary": 3, "standard": 5, "full": 10}
    top_findings = top_n_map.get(detail_level, 5)

    health = analyze_architecture_health(
        repo_path,
        project_name,
        top_findings=top_findings,
    )

    if focus != "all":
        health = _apply_focus_filter(health, focus)

    deps: dict[str, Any] | None = None
    if detail_level != "summary" and focus in ("all", "coupling"):
        deps = analyze_cross_module_dependencies(
            repo_path=repo_path,
            min_edge_weight=3,
        )

    # Generate template-only recommendations (no LLM)
    recs_count = {"summary": 0, "standard": 5, "full": 10}.get(detail_level, 5)
    recommendations: list[dict[str, Any]] = []
    if recs_count > 0:
        from local_deepwiki.generators.analysis.recommendations import (
            generate_recommendations,
        )

        recs_result = generate_recommendations(
            repo_path,
            health_data=health,
            max_items=recs_count,
        )
        recommendations = recs_result.get("recommendations", [])

    report = format_architecture_report(
        health,
        deps,
        detail_level=detail_level,
        recommendations=recommendations,
    )

    return {
        "status": "success",
        "project_name": project_name,
        "report": report,
        "overall": health.get("overall", {}),
        "tool": "analyze_architecture",
    }


def _apply_focus_filter(
    health: dict[str, Any],
    focus: str,
) -> dict[str, Any]:
    """Filter health results to only the focused dimension.

    Keeps overall scores but trims top_findings to the relevant category.
    """
    focus_to_findings = {
        "complexity": ["hotspots"],
        "coupling": [],
        "smells": ["high_severity_smells", "god_classes"],
    }
    keep_keys = focus_to_findings.get(focus, [])

    findings = health.get("top_findings", {})
    filtered_findings = {k: v for k, v in findings.items() if k in keep_keys}
    return {**health, "top_findings": filtered_findings}
