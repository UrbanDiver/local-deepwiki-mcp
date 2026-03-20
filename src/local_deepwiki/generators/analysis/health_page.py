"""Render architecture health analysis as a wiki markdown page.

Pure computation -- no LLM calls, no async, no external dependencies.
Takes the dict returned by ``analyze_architecture_health()`` and produces
a self-contained markdown page with grade, dimension scores, and top findings.
"""

from __future__ import annotations

# Maximum hotspot rows shown in the table
_MAX_HOTSPOT_ROWS = 10


def generate_health_page(health_data: dict) -> str | None:
    """Render architecture health dict as markdown.

    Args:
        health_data: Dict returned by ``analyze_architecture_health()``.

    Returns:
        Markdown string, or ``None`` if the data is empty / unusable.
    """
    overall = health_data.get("overall")
    if not overall:
        return None

    lines: list[str] = []
    lines.append("# Architecture Health")
    lines.append("")
    lines.append(f"**Overall Grade: {overall['grade']} ({overall['score']:.0f}/100)**")
    lines.append("")

    _render_dimension_table(lines, overall.get("dimensions", {}))
    _render_stats(lines, health_data.get("stats", {}))

    findings = health_data.get("top_findings", {})
    _render_hotspots(lines, findings.get("hotspots", []))
    _render_high_severity_smells(lines, findings.get("high_severity_smells", []))
    _render_god_classes(lines, findings.get("god_classes", []))
    _render_layer_section(lines, findings.get("layer_violations", []))

    return "\n".join(lines)


def _render_dimension_table(lines: list[str], dims: dict) -> None:
    """Append a scores-by-dimension markdown table."""
    if not dims:
        return

    lines.append("## Scores by Dimension")
    lines.append("")
    lines.append("| Dimension | Score | Grade |")
    lines.append("|-----------|-------|-------|")
    for name, dim in dims.items():
        lines.append(f"| {name.title()} | {dim['score']:.1f} | {dim['grade']} |")
    lines.append("")


def _render_stats(lines: list[str], stats: dict) -> None:
    """Append codebase statistics."""
    if not stats:
        return

    lines.append("## Codebase Stats")
    lines.append("")
    lines.append(f"- **Total lines:** {stats.get('total_lines', 0):,}")
    lines.append(f"- **Total functions:** {stats.get('total_functions', 0):,}")
    lines.append(f"- **Files scanned:** {stats.get('files_scanned', 0):,}")
    lines.append("")


def _render_hotspots(lines: list[str], hotspots: list[dict]) -> None:
    """Append complexity hotspot table."""
    if not hotspots:
        return

    lines.append("## Complexity Hotspots")
    lines.append("")
    lines.append("| Function | File | CC | Lines | Params |")
    lines.append("|----------|------|----|-------|--------|")
    for h in hotspots[:_MAX_HOTSPOT_ROWS]:
        d = h.get("details", {})
        lines.append(
            f"| `{h['function']}` | `{h['file']}:{h['line']}` "
            f"| {d.get('cyclomatic', '')} | {d.get('length', '')} "
            f"| {d.get('params', '')} |"
        )
    lines.append("")


def _render_high_severity_smells(lines: list[str], smells: list[dict]) -> None:
    """Append high-severity design smell list."""
    if not smells:
        return

    lines.append("## High-Severity Design Smells")
    lines.append("")
    for s in smells:
        lines.append(
            f"- **{s['entity']}** in `{s['file']}:{s['line']}` "
            f"({s['type']}) -- {s['description']}"
        )
    lines.append("")


def _render_god_classes(lines: list[str], god_classes: list[dict]) -> None:
    """Append god class list."""
    if not god_classes:
        return

    lines.append("## God Classes")
    lines.append("")
    for gc in god_classes:
        lines.append(
            f"- **{gc['entity']}** in `{gc['file']}:{gc['line']}` "
            f"-- {gc['description']}"
        )
    lines.append("")


def _render_layer_section(lines: list[str], violations: list) -> None:
    """Append layer architecture section."""
    if violations:
        lines.append("## Layer Violations")
        lines.append("")
        for v in violations:
            lines.append(f"- {v}")
        lines.append("")
    else:
        lines.append("## Layer Architecture")
        lines.append("")
        lines.append("No layer violations detected.")
        lines.append("")
