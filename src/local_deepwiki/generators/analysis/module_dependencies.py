"""Cross-module dependency analysis.

Builds an inter-module import graph from Python source files.  Modules are
identified as second-level packages (e.g. ``core.indexer``, ``generators.wiki``)
relative to the project root.  Edge weights reflect how many times one module
imports from another.

No LLM or external service calls — pure filesystem + regex analysis.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from local_deepwiki.generators.analysis.source_filter import iter_python_files
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# Matches ``from x.y.z import ...`` and ``import x.y.z``
_IMPORT_PATTERNS = (
    re.compile(r"^from\s+([\w.]+)\s+import"),
    re.compile(r"^import\s+([\w.]+)"),
)


def _extract_full_imports(source: str) -> list[str]:
    """Return full dotted module paths from all import statements in *source*."""
    modules: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        for pattern in _IMPORT_PATTERNS:
            match = pattern.match(stripped)
            if match:
                modules.append(match.group(1))
                break
    return modules


def _module_label(rel_path: Path) -> str:
    """Convert a relative file path to a dotted module label.

    ``src/local_deepwiki/core/indexer.py`` -> ``core.indexer``

    We take up to the first two meaningful package parts (skipping ``src``
    and single top-level project wrappers) so that siblings like
    ``core/indexer.py`` and ``core/vectorstore/base.py`` both map to
    ``core``.
    """
    parts = list(rel_path.with_suffix("").parts)
    # Drop common wrapper dirs.
    while parts and parts[0] in ("src", "lib", "pkg"):
        parts = parts[1:]
    if not parts:
        return "root"
    return ".".join(parts[:2]) if len(parts) >= 2 else parts[0]


def _top_level(dotted: str) -> str:
    """Return the first component of a dotted module name."""
    return dotted.split(".")[0]


def _discover_project_tops(repo_path: Path) -> set[str]:
    """Discover top-level project package names from a repository root.

    Checks both the root and a ``src/`` subdirectory for Python packages
    (directories containing ``__init__.py``).

    Args:
        repo_path: Root of the repository.

    Returns:
        Set of top-level package names.
    """
    project_tops: set[str] = set()
    for item in repo_path.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            project_tops.add(item.name)
    src_dir = repo_path / "src"
    if src_dir.is_dir():
        for item in src_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                project_tops.add(item.name)
    return project_tops


def _resolve_import_target(
    dotted: str,
    project_tops: set[str],
    src_module: str,
    module_filter: str | None,
    include_external: bool,
) -> str | None:
    """Classify a dotted import and return the target module label.

    Returns the target module label string, or ``None`` if the import
    should be skipped (e.g. self-import, filtered out, or unwanted external).
    """
    top = _top_level(dotted)
    is_internal = top in project_tops

    if not include_external and not is_internal:
        return None

    if is_internal:
        parts = dotted.split(".")
        if parts[0] in project_tops:
            parts = parts[1:]
        if not parts:
            return None
        tgt_module = ".".join(parts[:2]) if len(parts) >= 2 else parts[0]
    else:
        tgt_module = top

    if tgt_module == src_module:
        return None

    if module_filter and not tgt_module.startswith(module_filter):
        if not include_external:
            return None

    return tgt_module


def _build_module_graph(
    repo_path: Path,
    project_tops: set[str],
    module_filter: str | None,
    include_external: bool,
) -> tuple[
    dict[str, int],
    dict[str, int],
    dict[tuple[str, str], int],
    dict[tuple[str, str], list[str]],
]:
    """Scan Python files and build raw import-graph data structures.

    Args:
        repo_path: Root of the repository.
        project_tops: Known top-level package names for internal detection.
        module_filter: Optional prefix filter for source modules.
        include_external: Whether to include third-party/stdlib imports.

    Returns:
        Tuple of (module_file_counts, module_line_counts, edge_counts,
        edge_imports) defaultdict instances.
    """
    module_file_counts: dict[str, int] = defaultdict(int)
    module_line_counts: dict[str, int] = defaultdict(int)
    edge_counts: dict[tuple[str, str], int] = defaultdict(int)
    edge_imports: dict[tuple[str, str], list[str]] = defaultdict(list)

    for py_file, rel_path in iter_python_files(repo_path, exclude_tests=False):
        src_module = _module_label(rel_path)
        if module_filter and not src_module.startswith(module_filter):
            continue

        module_file_counts[src_module] += 1

        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning("Could not read %s", py_file)
            continue

        module_line_counts[src_module] += source.count("\n") + 1

        for dotted in _extract_full_imports(source):
            tgt_module = _resolve_import_target(
                dotted, project_tops, src_module, module_filter, include_external
            )
            if tgt_module is None:
                continue

            edge = (src_module, tgt_module)
            edge_counts[edge] += 1
            if dotted not in edge_imports[edge]:
                edge_imports[edge].append(dotted)

    return module_file_counts, module_line_counts, edge_counts, edge_imports


def _compute_dependency_stats(
    edges: list[dict[str, Any]],
    modules: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute afferent/efferent coupling statistics from edges.

    Args:
        edges: List of edge dicts with ``source`` and ``target`` keys.
        modules: List of module dicts (used only for total count).

    Returns:
        Stats dict with total_modules, total_edges, most_depended_on,
        and most_dependent keys.
    """
    ca: dict[str, int] = defaultdict(int)
    ce: dict[str, int] = defaultdict(int)
    for edge in edges:
        ca[edge["target"]] += 1
        ce[edge["source"]] += 1

    most_depended_on = sorted(ca.items(), key=lambda x: x[1], reverse=True)[:3]
    most_dependent = sorted(ce.items(), key=lambda x: x[1], reverse=True)[:3]

    return {
        "total_modules": len(modules),
        "total_edges": len(edges),
        "most_depended_on": [{"module": m, "afferent": c} for m, c in most_depended_on],
        "most_dependent": [{"module": m, "efferent": c} for m, c in most_dependent],
    }


def analyze_cross_module_dependencies(
    repo_path: Path,
    module_filter: str | None = None,
    include_external: bool = False,
    min_edge_weight: int = 1,
) -> dict[str, Any]:
    """Build and return the inter-module import graph for *repo_path*.

    Args:
        repo_path: Root of the repository to scan.
        module_filter: When given, only include modules whose label starts with
            this prefix (e.g. ``"core"``).
        include_external: When ``False`` (default), third-party and stdlib
            imports are excluded.
        min_edge_weight: Minimum number of import occurrences to include an
            edge in the output.

    Returns:
        A dict with ``status``, ``modules``, ``edges``, ``mermaid``, and
        ``stats`` keys.
    """
    project_tops = _discover_project_tops(repo_path)

    module_file_counts, module_line_counts, edge_counts, edge_imports = (
        _build_module_graph(repo_path, project_tops, module_filter, include_external)
    )

    # Build output structures.
    all_module_names = set(module_file_counts.keys()) | {
        tgt for (_, tgt) in edge_counts
    }
    modules = [
        {
            "name": m,
            "file_count": module_file_counts.get(m, 0),
            "total_lines": module_line_counts.get(m, 0),
        }
        for m in sorted(all_module_names)
    ]

    edges = [
        {
            "source": src,
            "target": tgt,
            "weight": cnt,
            "imports": edge_imports[(src, tgt)][:10],
        }
        for (src, tgt), cnt in sorted(edge_counts.items())
        if cnt >= min_edge_weight
    ]

    mermaid = _build_mermaid(edges)
    stats = _compute_dependency_stats(edges, modules)

    logger.info(
        "Cross-module deps: %d modules, %d edges in %s",
        len(modules),
        len(edges),
        repo_path,
    )

    return {
        "status": "success",
        "modules": modules,
        "edges": edges,
        "mermaid": mermaid,
        "stats": stats,
    }


def _build_mermaid(edges: list[dict[str, Any]]) -> str:
    """Render a Mermaid ``graph LR`` diagram from the edge list."""
    if not edges:
        return "graph LR\n  %% No edges to display"

    lines = ["graph LR"]
    for edge in edges:
        src = _sanitize_id(edge["source"])
        tgt = _sanitize_id(edge["target"])
        weight = edge["weight"]
        lines.append(f"  {src} -->|{weight}| {tgt}")

    return "\n".join(lines)


def _sanitize_id(name: str) -> str:
    """Convert a dotted module name to a valid Mermaid node ID."""
    return name.replace(".", "_").replace("-", "_")
