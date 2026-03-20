"""Render coupling metrics as a wiki markdown page.

Pure computation -- no LLM calls, no async, no external dependencies.
Takes the dict returned by ``analyze_coupling_metrics()`` and produces
a self-contained markdown page with a metrics table sorted by distance
from the main sequence, plus a highlight section for distant modules.
"""

from __future__ import annotations

# Distance threshold: modules with D above this are flagged as "far from main sequence".
_DISTANCE_THRESHOLD = 0.7


def generate_coupling_page(coupling_data: dict) -> str | None:
    """Render coupling metrics dict as markdown.

    Args:
        coupling_data: Dict returned by ``analyze_coupling_metrics()``.

    Returns:
        Markdown string, or ``None`` if the data is empty / unusable.
    """
    metrics = coupling_data.get("metrics", [])
    if not metrics:
        return None

    lines: list[str] = []
    lines.append("# Coupling Metrics")
    lines.append("")

    _render_explanation(lines)
    _render_summary(lines, coupling_data.get("stats", {}), metrics)
    _render_metrics_table(lines, metrics)
    _render_distant_modules(lines, metrics)

    return "\n".join(lines)


def _render_explanation(lines: list[str]) -> None:
    """Append explanation paragraph describing Martin coupling metrics."""
    lines.append(
        "Robert C. Martin's package coupling metrics measure the stability "
        "and abstractness of each module:"
    )
    lines.append("")
    lines.append(
        "- **Ca** (afferent coupling): number of modules that depend on this module"
    )
    lines.append(
        "- **Ce** (efferent coupling): number of modules this module depends on"
    )
    lines.append(
        "- **I** (instability): Ce / (Ca + Ce) -- 0 = maximally stable, "
        "1 = maximally unstable"
    )
    lines.append("- **A** (abstractness): fraction of abstract classes in the module")
    lines.append(
        "- **D** (distance from main sequence): |A + I - 1| -- "
        "0 = on the main sequence, 1 = maximally far"
    )
    lines.append("")


def _render_summary(lines: list[str], stats: dict, metrics: list[dict]) -> None:
    """Append summary statistics."""
    total = stats.get("total_modules", len(metrics))
    avg_distance = _compute_avg_distance(metrics)

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total modules:** {total}")
    lines.append(f"- **Average distance from main sequence:** {avg_distance:.3f}")

    avg_instability = stats.get("avg_instability")
    if avg_instability is not None:
        lines.append(f"- **Average instability:** {avg_instability:.3f}")

    avg_abstractness = stats.get("avg_abstractness")
    if avg_abstractness is not None:
        lines.append(f"- **Average abstractness:** {avg_abstractness:.3f}")

    lines.append("")


def _compute_avg_distance(metrics: list[dict]) -> float:
    """Compute average distance from the metrics list."""
    if not metrics:
        return 0.0
    total = sum(m.get("distance", 0.0) for m in metrics)
    return round(total / len(metrics), 4)


def _render_metrics_table(lines: list[str], metrics: list[dict]) -> None:
    """Append the main metrics table sorted by distance descending."""
    sorted_metrics = sorted(metrics, key=lambda m: m.get("distance", 0.0), reverse=True)

    lines.append("## Metrics by Module")
    lines.append("")
    lines.append("| Module | Ca | Ce | I | A | D |")
    lines.append("|--------|----|----|---|---|---|")

    for m in sorted_metrics:
        module = m.get("module", "")
        ca = m.get("afferent_coupling", 0)
        ce = m.get("efferent_coupling", 0)
        instability = m.get("instability", 0.0)
        abstractness = m.get("abstractness", 0.0)
        distance = m.get("distance", 0.0)
        lines.append(
            f"| `{module}` | {ca} | {ce} "
            f"| {instability:.3f} | {abstractness:.3f} | {distance:.3f} |"
        )

    lines.append("")


def _render_distant_modules(lines: list[str], metrics: list[dict]) -> None:
    """Append a highlight section for modules far from the main sequence."""
    distant = [m for m in metrics if m.get("distance", 0.0) > _DISTANCE_THRESHOLD]

    if not distant:
        return

    distant_sorted = sorted(distant, key=lambda m: m.get("distance", 0.0), reverse=True)

    lines.append("## Far from Main Sequence")
    lines.append("")
    lines.append(
        f"The following {len(distant_sorted)} module(s) have D > "
        f"{_DISTANCE_THRESHOLD}, indicating they may be either too "
        "concrete and stable (zone of pain) or too abstract and unstable "
        "(zone of uselessness):"
    )
    lines.append("")

    for m in distant_sorted:
        module = m.get("module", "")
        distance = m.get("distance", 0.0)
        instability = m.get("instability", 0.0)
        abstractness = m.get("abstractness", 0.0)
        lines.append(
            f"- **`{module}`** -- D={distance:.3f} "
            f"(I={instability:.3f}, A={abstractness:.3f})"
        )

    lines.append("")
