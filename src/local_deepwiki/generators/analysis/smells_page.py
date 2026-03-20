"""Render design smells analysis as a wiki markdown page.

Pure computation -- no LLM calls, no async, no external dependencies.
Takes the dict returned by ``analyze_design_smells()`` and produces
a self-contained markdown page with smells grouped by type, severity
summary, and refactoring suggestions.
"""

from __future__ import annotations

from collections import defaultdict

# Ordered list of recognised smell types for consistent section ordering.
_SMELL_TYPE_ORDER = [
    "god_class",
    "long_method",
    "long_parameter_list",
    "feature_envy",
    "large_file",
    "deep_nesting",
    "data_clump",
]


def _format_type_name(raw: str) -> str:
    """Convert a snake_case smell type to Title Case.

    ``"god_class"`` -> ``"God Class"``,
    ``"long_parameter_list"`` -> ``"Long Parameter List"``.
    """
    return raw.replace("_", " ").title()


def generate_smells_page(smells_data: dict) -> str | None:
    """Render design smells dict as markdown.

    Args:
        smells_data: Dict returned by ``analyze_design_smells()``.

    Returns:
        Markdown string, or ``None`` if the data is empty / unusable.
    """
    smells = smells_data.get("smells", [])
    if not smells:
        return None

    lines: list[str] = []
    lines.append("# Design Smells")
    lines.append("")

    summary = smells_data.get("summary", {})
    grouped = _group_by_type(smells)

    _render_type_summary_table(lines, grouped)
    _render_severity_summary(lines, summary)

    for smell_type in _SMELL_TYPE_ORDER:
        if smell_type in grouped:
            _render_type_section(lines, smell_type, grouped[smell_type])

    # Handle any unexpected types not in the ordered list
    for smell_type in sorted(grouped):
        if smell_type not in _SMELL_TYPE_ORDER:
            _render_type_section(lines, smell_type, grouped[smell_type])

    return "\n".join(lines)


def _group_by_type(smells: list[dict]) -> dict[str, list[dict]]:
    """Group smell dicts by their ``type`` field."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for smell in smells:
        grouped[smell["type"]].append(smell)
    return dict(grouped)


def _render_type_summary_table(
    lines: list[str], grouped: dict[str, list[dict]]
) -> None:
    """Append a summary table showing count per smell type."""
    lines.append("## Summary by Type")
    lines.append("")
    lines.append("| Type | Count |")
    lines.append("|------|-------|")

    for smell_type in _SMELL_TYPE_ORDER:
        if smell_type in grouped:
            lines.append(
                f"| {_format_type_name(smell_type)} | {len(grouped[smell_type])} |"
            )
    for smell_type in sorted(grouped):
        if smell_type not in _SMELL_TYPE_ORDER:
            lines.append(
                f"| {_format_type_name(smell_type)} | {len(grouped[smell_type])} |"
            )
    lines.append("")


def _render_severity_summary(lines: list[str], summary: dict) -> None:
    """Append severity breakdown."""
    if not summary:
        return

    total = summary.get("total", 0)
    by_severity = summary.get("by_severity", {})

    lines.append("## Severity Summary")
    lines.append("")
    lines.append(f"- **Total smells:** {total}")
    for level in ("high", "medium", "low"):
        count = by_severity.get(level, 0)
        if count > 0:
            lines.append(f"- **{level.title()}:** {count}")
    lines.append("")


def _render_type_section(lines: list[str], smell_type: str, smells: list[dict]) -> None:
    """Append a section for a single smell type with a detail table."""
    title = _format_type_name(smell_type)
    lines.append(f"## {title}")
    lines.append("")
    lines.append("| Entity | File | Severity | Description | Suggestion |")
    lines.append("|--------|------|----------|-------------|------------|")
    for s in smells:
        entity = s.get("entity", "")
        file_loc = f"{s.get('file', '')}:{s.get('line', '')}"
        severity = s.get("severity", "")
        description = s.get("description", "")
        suggestion = s.get("suggestion", "")
        lines.append(
            f"| `{entity}` | `{file_loc}` | {severity} | {description} | {suggestion} |"
        )
    lines.append("")
