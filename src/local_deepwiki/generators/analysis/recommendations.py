"""Architecture recommendations generator.

Maps architecture health findings to actionable, prioritized recommendations
using template-based rules.  Optionally enriches each recommendation with
LLM-generated descriptions.

No LLM calls in the default path -- ``generate_recommendations`` is a pure
function.  ``enrich_recommendations`` adds an async LLM enrichment pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Weight constants
# ---------------------------------------------------------------------------
_WEIGHT = {"high": 3, "medium": 2, "low": 1}

# ---------------------------------------------------------------------------
# Recommendation templates keyed by finding type
# ---------------------------------------------------------------------------
_TEMPLATES: list[dict[str, str]] = [
    {
        "finding_type": "god_class",
        "category": "smells",
        "title_template": "Split {entity} into focused components",
        "effort": "medium",
        "impact": "high",
    },
    {
        "finding_type": "long_method",
        "category": "complexity",
        "title_template": "Extract helpers from {entity}",
        "effort": "low",
        "impact": "high",
    },
    {
        "finding_type": "long_parameter_list",
        "category": "smells",
        "title_template": "Introduce parameter object for {entity}",
        "effort": "low",
        "impact": "medium",
    },
    {
        "finding_type": "feature_envy",
        "category": "smells",
        "title_template": "Move {entity} to the class it envies",
        "effort": "medium",
        "impact": "medium",
    },
    {
        "finding_type": "large_file",
        "category": "smells",
        "title_template": "Split {file} into focused modules",
        "effort": "medium",
        "impact": "high",
    },
    {
        "finding_type": "deep_nesting",
        "category": "complexity",
        "title_template": "Flatten nesting in {entity}",
        "effort": "low",
        "impact": "medium",
    },
]

# Build a lookup for quick access by finding type.
_TEMPLATE_BY_TYPE: dict[str, dict[str, str]] = {
    t["finding_type"]: t for t in _TEMPLATES
}


# ---------------------------------------------------------------------------
# Priority helpers
# ---------------------------------------------------------------------------
def _priority(impact: str, effort: str) -> float:
    """Higher impact and lower effort yield a higher priority score."""
    return _WEIGHT[impact] * (1.0 / _WEIGHT[effort])


# ---------------------------------------------------------------------------
# Internal mapping helpers
# ---------------------------------------------------------------------------


def _recommendations_from_smells(
    smells: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map design smell findings to recommendations."""
    recs: list[dict[str, Any]] = []
    for smell in smells:
        smell_type = smell.get("type", "")
        template = _TEMPLATE_BY_TYPE.get(smell_type)
        if template is None:
            continue

        entity = smell.get("entity", smell.get("file", "unknown"))
        file_path = smell.get("file", "")
        line = smell.get("line", 0)

        # For large_file, use {file} in the template; others use {entity}.
        title = template["title_template"].format(
            entity=entity,
            file=file_path,
        )

        recs.append(
            {
                "title": title,
                "category": template["category"],
                "description": smell.get("description", ""),
                "file": file_path,
                "line": line,
                "effort": template["effort"],
                "impact": template["impact"],
                "priority": _priority(template["impact"], template["effort"]),
            }
        )
    return recs


def _recommendations_from_hotspots(
    hotspots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map hotspot findings (CC > 15) to recommendations."""
    recs: list[dict[str, Any]] = []
    for spot in hotspots:
        cc = spot.get("details", {}).get("cyclomatic", 0)
        if cc <= 15:
            continue
        func_name = spot.get("function", "unknown")
        file_path = spot.get("file", "")
        line = spot.get("line", 0)
        recs.append(
            {
                "title": f"Reduce complexity in {func_name}",
                "category": "complexity",
                "description": f"Cyclomatic complexity is {cc} (threshold: 15).",
                "file": file_path,
                "line": line,
                "effort": "medium",
                "impact": "high",
                "priority": _priority("high", "medium"),
            }
        )
    return recs


def _recommendations_from_layer_violations(
    violations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map layer violations to recommendations."""
    recs: list[dict[str, Any]] = []
    for viol in violations:
        from_layer = viol.get("from_layer", "unknown")
        to_layer = viol.get("to_layer", "unknown")
        file_path = viol.get("file", "")
        recs.append(
            {
                "title": f"Fix upward dependency: {from_layer} -> {to_layer}",
                "category": "layers",
                "description": (
                    f"Module in {from_layer} imports from {to_layer}, "
                    f"violating the layered architecture."
                ),
                "file": file_path,
                "line": 0,
                "effort": "low",
                "impact": "high",
                "priority": _priority("high", "low"),
            }
        )
    return recs


def _recommendations_from_coupling(
    coupling_metrics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map high-distance coupling metrics (D > 0.7) to recommendations."""
    recs: list[dict[str, Any]] = []
    for metric in coupling_metrics:
        distance = metric.get("distance", 0.0)
        if distance <= 0.7:
            continue
        module_name = metric.get("module", "unknown")
        recs.append(
            {
                "title": f"Reduce coupling in module {module_name}",
                "category": "coupling",
                "description": (
                    f"Distance from main sequence is {distance:.2f} (threshold: 0.7)."
                ),
                "file": "",
                "line": 0,
                "effort": "high",
                "impact": "medium",
                "priority": _priority("medium", "high"),
            }
        )
    return recs


def _deduplicate(
    recs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove duplicate recommendations by (file, line, category)."""
    seen: set[tuple[str, int, str]] = set()
    unique: list[dict[str, Any]] = []
    for rec in recs:
        key = (rec["file"], rec["line"], rec["category"])
        if key not in seen:
            seen.add(key)
            unique.append(rec)
    return unique


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_recommendations(
    repo_path: Path,
    *,
    health_data: dict[str, Any] | None = None,
    max_items: int = 10,
    category_filter: str | None = None,
) -> dict[str, Any]:
    """Generate prioritized architecture recommendations.

    Args:
        repo_path: Repository root (used only when *health_data* is ``None``).
        health_data: Pre-computed output from ``analyze_architecture_health``.
            When ``None``, the function runs the analysis internally.
        max_items: Maximum number of recommendations to return.
        category_filter: If set, restrict to a single category
            (``"smells"``, ``"complexity"``, ``"coupling"``, ``"layers"``).

    Returns:
        Dict with ``status``, ``recommendations`` (sorted by priority desc),
        and ``stats``.
    """
    if health_data is None:
        from local_deepwiki.generators.analysis.architecture_health import (
            analyze_architecture_health,
        )

        health_data = analyze_architecture_health(repo_path, repo_path.name)

    findings = health_data.get("top_findings", {})

    # Collect all raw recommendations from each source.
    all_recs: list[dict[str, Any]] = []

    # God classes come in their own bucket; smells also includes them but
    # we process them uniformly via the smell template.
    god_classes = findings.get("god_classes", [])
    high_smells = findings.get("high_severity_smells", [])
    combined_smells = god_classes + high_smells
    all_recs.extend(_recommendations_from_smells(combined_smells))

    all_recs.extend(_recommendations_from_hotspots(findings.get("hotspots", [])))
    all_recs.extend(
        _recommendations_from_layer_violations(findings.get("layer_violations", []))
    )

    # Coupling metrics are optional -- passed via a private key.
    coupling_metrics = health_data.get("_coupling_metrics", [])
    all_recs.extend(_recommendations_from_coupling(coupling_metrics))

    # Deduplicate
    all_recs = _deduplicate(all_recs)

    # Category filter
    if category_filter is not None:
        all_recs = [r for r in all_recs if r["category"] == category_filter]

    # Sort by priority descending, then by title for stability.
    all_recs.sort(key=lambda r: (-r["priority"], r["title"]))

    total_findings = len(all_recs)
    returned = all_recs[:max_items]

    logger.info(
        "Generated %d recommendations (%d total findings) for %s",
        len(returned),
        total_findings,
        repo_path,
    )

    return {
        "status": "success",
        "recommendations": returned,
        "stats": {
            "total_findings": total_findings,
            "returned": len(returned),
            "category": category_filter or "all",
        },
    }


async def enrich_recommendations(
    recommendations: list[dict[str, Any]],
    llm_provider: Any,
) -> list[dict[str, Any]]:
    """Add LLM-generated enriched descriptions to recommendations.

    Each recommendation is independently enriched; failures are silently
    skipped (the original recommendation is kept without an
    ``enriched_description`` field).

    Args:
        recommendations: List of recommendation dicts from
            ``generate_recommendations``.
        llm_provider: An object with an ``async generate(prompt)`` method.

    Returns:
        A **new** list of recommendation dicts (no mutation of originals).
    """
    enriched: list[dict[str, Any]] = []
    for rec in recommendations:
        try:
            prompt = (
                f"Provide a concise, actionable suggestion for the following "
                f"architecture recommendation:\n\n"
                f"Title: {rec['title']}\n"
                f"Category: {rec['category']}\n"
                f"File: {rec.get('file', 'N/A')}\n"
                f"Description: {rec.get('description', 'N/A')}\n\n"
                f"Give a 2-3 sentence explanation of why this matters and "
                f"how to fix it."
            )
            enriched_text = await llm_provider.generate(prompt)
            enriched.append({**rec, "enriched_description": enriched_text})
        except Exception:
            logger.debug(
                "Failed to enrich recommendation %r, keeping original",
                rec.get("title", ""),
            )
            enriched.append({**rec})
    return enriched
