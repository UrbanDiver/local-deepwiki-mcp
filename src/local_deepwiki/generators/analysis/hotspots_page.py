"""Render complexity hotspots analysis as a wiki markdown page.

Pure computation -- no LLM calls, no async, no external dependencies.
Takes the dict returned by ``analyze_hotspots()`` and produces
a self-contained markdown page with a ranked table of the top hotspots.
"""

from __future__ import annotations

# Maximum hotspot rows shown in the table
_MAX_ROWS = 20


def generate_hotspots_page(hotspots_data: dict) -> str | None:
    """Render hotspots dict as markdown.

    Args:
        hotspots_data: Dict returned by ``analyze_hotspots()``.

    Returns:
        Markdown string, or ``None`` if the data is empty / unusable.
    """
    hotspots = hotspots_data.get("hotspots", [])
    if not hotspots:
        return None

    lines: list[str] = []
    lines.append("# Complexity Hotspots")
    lines.append("")

    _render_stats(lines, hotspots_data.get("stats", {}))
    _render_hotspot_table(lines, hotspots)

    return "\n".join(lines)


def _render_stats(lines: list[str], stats: dict) -> None:
    """Append summary statistics."""
    if not stats:
        return

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total functions scanned:** {stats.get('total_functions', 0):,}")
    lines.append(f"- **Files scanned:** {stats.get('files_scanned', 0):,}")
    lines.append(f"- **Metric used:** {stats.get('metric_used', 'complexity')}")
    lines.append("")


def _render_hotspot_table(lines: list[str], hotspots: list[dict]) -> None:
    """Append ranked hotspot table, limited to top ``_MAX_ROWS``."""
    lines.append("## Top Hotspots")
    lines.append("")
    lines.append("| Rank | Function | File | CC | Lines | Params | Nesting |")
    lines.append("|------|----------|------|----|-------|--------|---------|")
    for rank, h in enumerate(hotspots[:_MAX_ROWS], start=1):
        d = h.get("details", {})
        lines.append(
            f"| {rank} | `{h['function']}` | `{h['file']}:{h['line']}` "
            f"| {d.get('cyclomatic', '')} | {d.get('length', '')} "
            f"| {d.get('params', '')} | {d.get('nesting', '')} |"
        )
    lines.append("")
