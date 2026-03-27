"""Narrative formatter for composite architecture analysis reports.

Converts structured health check and dependency data into a human-readable
markdown report. Template-based (no LLM calls).
"""

from __future__ import annotations

from typing import Any

_STRENGTH_THRESHOLD = 80
_CONCERN_THRESHOLD = 70


def format_architecture_report(
    health: dict[str, Any],
    deps: dict[str, Any],
    *,
    detail_level: str = "standard",
) -> str:
    """Format architecture analysis data into a markdown narrative report."""
    sections: list[str] = []
    sections.append(_format_executive_summary(health))

    if detail_level == "summary":
        return "\n\n".join(sections)

    sections.append(_format_strengths(health))
    sections.append(_format_concerns(health))
    sections.append(_format_dependency_structure(deps))

    return "\n\n".join(s for s in sections if s)


def _format_executive_summary(health: dict[str, Any]) -> str:
    overall = health.get("overall", {})
    grade = overall.get("grade", "?")
    score = overall.get("score", 0)
    stats = health.get("stats", {})
    lines = stats.get("total_lines", 0)
    functions = stats.get("total_functions", 0)
    files = stats.get("files_scanned", 0)
    dims = overall.get("dimensions", {})

    dim_table = "| Dimension | Score | Grade |\n|-----------|-------|-------|\n"
    for dim_name in ("complexity", "coupling", "smells", "layers"):
        d = dims.get(dim_name, {})
        dim_table += (
            f"| {dim_name.title()} | {d.get('score', '?')} | {d.get('grade', '?')} |\n"
        )

    return (
        f"## Executive Summary\n\n"
        f"**Overall: {grade} ({score}/100)** — "
        f"{lines:,} lines, {functions:,} functions across {files} files.\n\n"
        f"{dim_table}"
    )


def _format_strengths(health: dict[str, Any]) -> str:
    overall = health.get("overall", {})
    dims = overall.get("dimensions", {})
    findings = health.get("top_findings", {})

    strengths: list[str] = []
    for dim_name, d in dims.items():
        if d.get("score", 0) >= _STRENGTH_THRESHOLD:
            strengths.append(
                f"- **{dim_name.title()}** ({d['grade']}): score {d['score']}/100"
            )

    if not findings.get("god_classes"):
        strengths.append("- **No god classes** detected")

    if not findings.get("layer_violations"):
        strengths.append("- **Zero layer violations** — clean architectural layering")

    if not strengths:
        return ""

    return "## Strengths\n\n" + "\n".join(strengths)


def _format_concerns(health: dict[str, Any]) -> str:
    overall = health.get("overall", {})
    dims = overall.get("dimensions", {})
    findings = health.get("top_findings", {})

    parts: list[str] = []

    for dim_name, d in dims.items():
        if d.get("score", 100) < _CONCERN_THRESHOLD:
            parts.append(
                f"- **{dim_name.title()}** ({d['grade']}): score {d['score']}/100"
            )

    hotspots = findings.get("hotspots", [])
    if hotspots:
        parts.append("\n### Complexity Hotspots\n")
        parts.append("| Function | File | CC | Lines |")
        parts.append("|----------|------|----|-------|")
        for h in hotspots[:5]:
            details = h.get("details", {})
            parts.append(
                f"| `{h['function']}` | `{h['file']}:{h['line']}` "
                f"| {details.get('cyclomatic', '?')} | {details.get('length', '?')} |"
            )

    smells = findings.get("high_severity_smells", [])
    if smells:
        parts.append("\n### High-Severity Design Smells\n")
        for s in smells[:5]:
            parts.append(
                f"- **{s['type']}** in `{s.get('file', '?')}:{s.get('line', '?')}` — {s.get('entity', '?')}"
            )

    if not parts:
        return ""

    return "## Concerns\n\n" + "\n".join(parts)


def _format_dependency_structure(deps: dict[str, Any]) -> str:
    stats = deps.get("stats", {})
    edges = deps.get("edges", [])

    parts: list[str] = [
        f"**{stats.get('total_modules', 0)} modules**, "
        f"**{stats.get('total_edges', 0)} dependency edges**"
    ]

    if edges:
        in_degree: dict[str, int] = {}
        for e in edges:
            tgt = e.get("target", "")
            in_degree[tgt] = in_degree.get(tgt, 0) + e.get("weight", 1)

        top_hubs = sorted(in_degree.items(), key=lambda x: -x[1])[:5]
        if top_hubs:
            parts.append("\n### Most-Depended-On Modules\n")
            parts.append("| Module | Inbound Imports |")
            parts.append("|--------|----------------|")
            for mod, count in top_hubs:
                parts.append(f"| `{mod}` | {count} |")

        heaviest = sorted(edges, key=lambda e: e.get("weight", 0), reverse=True)[:5]
        if heaviest:
            parts.append("\n### Heaviest Dependencies\n")
            for e in heaviest:
                parts.append(
                    f"- `{e.get('source', '?')}` → `{e.get('target', '?')}` "
                    f"(weight {e.get('weight', 0)})"
                )

    return "## Dependency Structure\n\n" + "\n".join(parts)
