"""Documentation coverage analysis and reporting."""

from dataclasses import dataclass, field
from pathlib import Path

from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.models import ChunkType, IndexStatus


@dataclass
class CoverageStats:
    """Documentation coverage statistics."""

    total_classes: int = 0
    documented_classes: int = 0
    total_functions: int = 0
    documented_functions: int = 0
    total_methods: int = 0
    documented_methods: int = 0

    @property
    def total_entities(self) -> int:
        """Total number of documentable entities."""
        return self.total_classes + self.total_functions + self.total_methods

    @property
    def documented_entities(self) -> int:
        """Total number of documented entities."""
        return self.documented_classes + self.documented_functions + self.documented_methods

    @property
    def coverage_percent(self) -> float:
        """Overall documentation coverage percentage."""
        if self.total_entities == 0:
            return 100.0
        return (self.documented_entities / self.total_entities) * 100


@dataclass
class FileCoverage:
    """Coverage statistics for a single file."""

    file_path: str
    stats: CoverageStats = field(default_factory=CoverageStats)
    undocumented: list[str] = field(default_factory=list)  # List of undocumented entity names


def _has_meaningful_docstring(docstring: str | None) -> bool:
    """Check if a docstring is meaningful (not empty or trivial).

    Args:
        docstring: The docstring to check.

    Returns:
        True if the docstring is meaningful.
    """
    if not docstring:
        return False

    # Strip and check for minimal content
    cleaned = docstring.strip()
    if len(cleaned) < 10:  # Too short to be meaningful
        return False

    # Check for placeholder docstrings
    placeholders = ["todo", "fixme", "xxx", "pass", "..."]
    if cleaned.lower() in placeholders:
        return False

    return True


async def analyze_file_coverage(
    file_path: str,
    vector_store: VectorStore,
) -> FileCoverage:
    """Analyze documentation coverage for a single file.

    Args:
        file_path: Path to the source file.
        vector_store: Vector store with code chunks.

    Returns:
        FileCoverage object with statistics.
    """
    coverage = FileCoverage(file_path=file_path)
    chunks = await vector_store.get_chunks_by_file(file_path)

    for chunk in chunks:
        name = chunk.name or "Unknown"
        has_doc = _has_meaningful_docstring(chunk.docstring)

        if chunk.chunk_type == ChunkType.CLASS:
            coverage.stats.total_classes += 1
            if has_doc:
                coverage.stats.documented_classes += 1
            else:
                coverage.undocumented.append(f"class {name}")

        elif chunk.chunk_type == ChunkType.FUNCTION:
            coverage.stats.total_functions += 1
            if has_doc:
                coverage.stats.documented_functions += 1
            else:
                coverage.undocumented.append(f"function {name}")

        elif chunk.chunk_type == ChunkType.METHOD:
            coverage.stats.total_methods += 1
            if has_doc:
                coverage.stats.documented_methods += 1
            else:
                parent = chunk.parent_name or "Unknown"
                coverage.undocumented.append(f"method {parent}.{name}")

    return coverage


async def analyze_project_coverage(
    index_status: IndexStatus,
    vector_store: VectorStore,
) -> tuple[CoverageStats, list[FileCoverage]]:
    """Analyze documentation coverage for the entire project.

    Args:
        index_status: Index status with file information.
        vector_store: Vector store with code chunks.

    Returns:
        Tuple of (overall stats, list of per-file coverage).
    """
    overall = CoverageStats()
    file_coverages: list[FileCoverage] = []

    for file_info in index_status.files:
        file_coverage = await analyze_file_coverage(file_info.path, vector_store)
        file_coverages.append(file_coverage)

        # Aggregate stats
        overall.total_classes += file_coverage.stats.total_classes
        overall.documented_classes += file_coverage.stats.documented_classes
        overall.total_functions += file_coverage.stats.total_functions
        overall.documented_functions += file_coverage.stats.documented_functions
        overall.total_methods += file_coverage.stats.total_methods
        overall.documented_methods += file_coverage.stats.documented_methods

    # Sort by coverage (lowest first)
    file_coverages.sort(key=lambda f: f.stats.coverage_percent)

    return overall, file_coverages


def _get_coverage_emoji(percent: float) -> str:
    """Get an emoji indicator for coverage level.

    Args:
        percent: Coverage percentage.

    Returns:
        Emoji string.
    """
    if percent >= 90:
        return "🟢"
    elif percent >= 70:
        return "🟡"
    elif percent >= 50:
        return "🟠"
    else:
        return "🔴"


def _get_wiki_link(file_path: str) -> str:
    """Convert a source file path to a wiki link."""
    wiki_path = file_path.replace(".py", ".md")
    return f"files/{wiki_path}"


async def generate_coverage_page(
    index_status: IndexStatus,
    vector_store: VectorStore,
) -> str | None:
    """Generate the documentation coverage report page.

    Args:
        index_status: Index status with file information.
        vector_store: Vector store with code chunks.

    Returns:
        Markdown content for the coverage page, or None if no entities found.
    """
    overall, file_coverages = await analyze_project_coverage(index_status, vector_store)

    if overall.total_entities == 0:
        return None

    lines = [
        "# Documentation Coverage",
        "",
        "This report shows the documentation coverage for the codebase.",
        "",
    ]

    # Overall summary
    emoji = _get_coverage_emoji(overall.coverage_percent)
    lines.append("## Summary")
    lines.append("")
    lines.append(f"{emoji} **Overall Coverage: {overall.coverage_percent:.1f}%**")
    lines.append("")
    lines.append(f"- **{overall.documented_entities}** / **{overall.total_entities}** entities documented")
    lines.append("")

    # Breakdown by type
    lines.append("### By Type")
    lines.append("")
    lines.append("| Type | Documented | Total | Coverage |")
    lines.append("|------|------------|-------|----------|")

    if overall.total_classes > 0:
        class_pct = (overall.documented_classes / overall.total_classes) * 100
        lines.append(
            f"| Classes | {overall.documented_classes} | {overall.total_classes} | {class_pct:.1f}% |"
        )

    if overall.total_functions > 0:
        func_pct = (overall.documented_functions / overall.total_functions) * 100
        lines.append(
            f"| Functions | {overall.documented_functions} | {overall.total_functions} | {func_pct:.1f}% |"
        )

    if overall.total_methods > 0:
        method_pct = (overall.documented_methods / overall.total_methods) * 100
        lines.append(
            f"| Methods | {overall.documented_methods} | {overall.total_methods} | {method_pct:.1f}% |"
        )

    lines.append("")

    # Coverage by file
    lines.append("## Coverage by File")
    lines.append("")
    lines.append("| File | Documented | Total | Coverage |")
    lines.append("|------|------------|-------|----------|")

    for fc in file_coverages:
        if fc.stats.total_entities == 0:
            continue

        emoji = _get_coverage_emoji(fc.stats.coverage_percent)
        file_name = Path(fc.file_path).name
        wiki_link = _get_wiki_link(fc.file_path)

        lines.append(
            f"| {emoji} [{file_name}]({wiki_link}) | "
            f"{fc.stats.documented_entities} | {fc.stats.total_entities} | "
            f"{fc.stats.coverage_percent:.1f}% |"
        )

    lines.append("")

    # Files needing attention (lowest coverage)
    low_coverage_files = [fc for fc in file_coverages if fc.stats.coverage_percent < 50 and fc.stats.total_entities > 0]

    if low_coverage_files:
        lines.append("## Files Needing Attention")
        lines.append("")
        lines.append("Files with less than 50% documentation coverage:")
        lines.append("")

        for fc in low_coverage_files[:10]:  # Top 10 worst
            file_name = Path(fc.file_path).name
            wiki_link = _get_wiki_link(fc.file_path)
            lines.append(f"### [{file_name}]({wiki_link})")
            lines.append("")
            lines.append(f"Coverage: {fc.stats.coverage_percent:.1f}%")
            lines.append("")

            if fc.undocumented:
                lines.append("Undocumented:")
                for item in fc.undocumented[:20]:  # Limit to 20
                    lines.append(f"- `{item}`")
                if len(fc.undocumented) > 20:
                    lines.append(f"- ... and {len(fc.undocumented) - 20} more")
            lines.append("")

    # Legend
    lines.append("---")
    lines.append("")
    lines.append("**Legend:** 🟢 ≥90% | 🟡 ≥70% | 🟠 ≥50% | 🔴 <50%")
    lines.append("")

    return "\n".join(lines)
