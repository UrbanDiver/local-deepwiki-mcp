"""Dependency graph generation using Mermaid."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from local_deepwiki.core.path_utils import is_test_file
from local_deepwiki.generators.analysis.dependency_graph_data import (
    find_circular_dependency_edges,
    infer_package_name,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType

from ._utils import sanitize_mermaid_name

logger = get_logger(__name__)


def _is_test_module(module: str, file_path: str) -> bool:
    """Check if a module is a test module.

    Delegates to the canonical ``is_test_file`` helper in ``path_utils``.

    Args:
        module: Module name like 'test_parser' or 'core.indexer'.
        file_path: File path like 'tests/test_parser.py'.

    Returns:
        True if this is a test module.
    """
    return is_test_file(file_path) or module.startswith("test_") or ".test_" in module


@dataclass(frozen=True, slots=True)
class DiagramScanContext:
    """Immutable configuration for dependency-scanning functions.

    Bundles the common immutable parameters shared by ``_scan_import_lines``,
    ``_scan_chunk_imports``, and ``_scan_fallback_chunks``.

    Attributes:
        project_name: Project name for filtering internal imports.
        show_external: Whether to collect external dependencies.
        exclude_tests: Whether to exclude test module imports.
    """

    project_name: str
    show_external: bool = False
    exclude_tests: bool = True


@dataclass(slots=True)
class _ScanAccumulators:
    """Mutable accumulators shared by the dependency-scanning functions.

    Holds the four mutable collections that ``_scan_import_lines``,
    ``_scan_chunk_imports``, and ``_scan_fallback_chunks`` write into.
    """

    dependencies: dict[str, set[str]]
    external_deps: Counter[str]
    module_external_deps: dict[str, set[str]]
    all_internal_modules: set[str]


@dataclass(slots=True)
class _DependencyData:
    """Internal data structure for dependency graph generation."""

    dependencies: dict[str, set[str]]
    external_deps: dict[str, int]
    module_external_deps: dict[str, set[str]]
    all_internal_modules: set[str]


def _scan_import_lines(
    content: str,
    module: str,
    scan_ctx: DiagramScanContext,
    acc: _ScanAccumulators,
) -> None:
    """Scan content lines for import statements and update dependency data.

    Only lines starting with ``import `` or ``from `` are considered,
    so non-import content (function bodies, comments, etc.) is safely skipped.

    Args:
        content: Raw chunk content to scan.
        module: Module name derived from the chunk's file path.
        scan_ctx: Immutable scan configuration (project_name, show_external, exclude_tests).
        acc: Mutable accumulators to update.
    """
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Only consider lines that look like import statements
        if not (line.startswith("import ") or line.startswith("from ")):
            continue

        imported = _parse_import_line(line, scan_ctx.project_name)
        if imported:
            if scan_ctx.exclude_tests and imported.startswith("test_"):
                continue
            acc.dependencies[module].add(imported)
            acc.all_internal_modules.add(imported)
        elif scan_ctx.show_external:
            ext_module = _parse_external_import(line)
            if ext_module:
                acc.external_deps[ext_module] += 1
                acc.module_external_deps[module].add(ext_module)


_FALLBACK_CHUNK_TYPES = frozenset(
    {ChunkType.MODULE, ChunkType.FUNCTION, ChunkType.CLASS}
)


def _scan_chunk_imports(
    chunk: object,
    scan_ctx: DiagramScanContext,
    acc: _ScanAccumulators,
    *,
    files_with_import_chunks: set[str],
    fallback_chunks: list,
) -> None:
    """Process one chunk in the first dependency-collection pass."""
    if hasattr(chunk, "chunk"):
        chunk = chunk.chunk  # type: ignore[union-attr]

    if chunk.chunk_type == ChunkType.IMPORT:
        file_path = chunk.file_path
        module = _path_to_module(file_path)
        if not module:
            return
        if scan_ctx.exclude_tests and _is_test_module(module, file_path):
            return
        files_with_import_chunks.add(file_path)
        acc.all_internal_modules.add(module)
        _scan_import_lines(chunk.content, module, scan_ctx, acc)
    elif chunk.chunk_type in _FALLBACK_CHUNK_TYPES:
        fallback_chunks.append(chunk)


def _scan_fallback_chunks(
    fallback_chunks: list,
    scan_ctx: DiagramScanContext,
    acc: _ScanAccumulators,
    *,
    files_with_import_chunks: set[str],
) -> None:
    """Process fallback (non-IMPORT) chunks for files that have no dedicated IMPORT chunks."""
    for chunk in fallback_chunks:
        if hasattr(chunk, "chunk"):
            chunk = chunk.chunk  # type: ignore[union-attr]

        file_path = chunk.file_path
        if file_path in files_with_import_chunks:
            continue

        module = _path_to_module(file_path)
        if not module:
            continue
        if scan_ctx.exclude_tests and _is_test_module(module, file_path):
            continue

        acc.all_internal_modules.add(module)
        _scan_import_lines(chunk.content, module, scan_ctx, acc)


def _collect_dependencies(
    chunks: list,
    project_name: str,
    *,
    show_external: bool,
    exclude_tests: bool,
) -> _DependencyData:
    """Collect module dependencies from import chunks.

    First pass processes dedicated IMPORT chunks. If a file has no IMPORT
    chunks, a second pass scans MODULE/FUNCTION/CLASS chunks as a fallback
    so that repos without dedicated import chunks still produce dependency
    diagrams.

    Args:
        chunks: List of CodeChunk objects.
        project_name: Name of the project for filtering internal imports.
        show_external: Whether to collect external dependencies.
        exclude_tests: Whether to exclude test modules.

    Returns:
        DependencyData with collected dependencies.
    """
    scan_ctx = DiagramScanContext(
        project_name=project_name,
        show_external=show_external,
        exclude_tests=exclude_tests,
    )
    acc = _ScanAccumulators(
        dependencies=defaultdict(set),
        external_deps=Counter(),
        module_external_deps=defaultdict(set),
        all_internal_modules=set(),
    )
    files_with_import_chunks: set[str] = set()
    fallback_chunks: list = []

    for chunk in chunks:
        _scan_chunk_imports(
            chunk,
            scan_ctx,
            acc,
            files_with_import_chunks=files_with_import_chunks,
            fallback_chunks=fallback_chunks,
        )

    _scan_fallback_chunks(
        fallback_chunks,
        scan_ctx,
        acc,
        files_with_import_chunks=files_with_import_chunks,
    )

    return _DependencyData(
        dependencies=acc.dependencies,
        external_deps=acc.external_deps,
        module_external_deps=acc.module_external_deps,
        all_internal_modules=acc.all_internal_modules,
    )


def _build_internal_deps(
    dependencies: dict[str, set[str]],
    internal_modules: set[str],
) -> dict[str, set[str]]:
    """Filter dependencies to only include internal modules.

    Args:
        dependencies: Raw dependency mapping.
        internal_modules: Set of known internal modules.

    Returns:
        Filtered dependency mapping.
    """
    internal_deps: dict[str, set[str]] = {}
    for module, imports in dependencies.items():
        internal_imports = {imp for imp in imports if imp in internal_modules}
        if internal_imports:
            internal_deps[module] = internal_imports
    return internal_deps


def _group_modules(modules: set[str]) -> dict[str, list[str]]:
    """Group modules by top-level directory for subgraphs.

    Args:
        modules: Set of module names.

    Returns:
        Mapping of group name to list of modules.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for module in sorted(modules):
        parts = module.split(".")
        group = parts[0] if parts else "other"
        groups[group].append(module)
    return groups


def _build_node_ids(modules: set[str]) -> dict[str, str]:
    """Create unique node IDs for each module.

    Args:
        modules: Set of module names.

    Returns:
        Mapping of module name to node ID.
    """
    return {module: f"M{i}" for i, module in enumerate(sorted(modules))}


def _add_subgraphs(
    lines: list[str],
    module_groups: dict[str, list[str]],
    node_ids: dict[str, str],
) -> None:
    """Add subgraph definitions for module groups.

    Args:
        lines: Lines list to append to.
        module_groups: Mapping of group to modules.
        node_ids: Mapping of module to node ID.
    """
    for group_name in sorted(module_groups.keys()):
        modules = module_groups[group_name]
        safe_group = sanitize_mermaid_name(group_name)
        display_group = group_name.replace("_", " ").title()
        lines.append(f"    subgraph {safe_group}[{display_group}]")
        for module in sorted(modules):
            node_id = node_ids[module]
            display_name = module.split(".")[-1]
            lines.append(f"        {node_id}[{display_name}]")
        lines.append("    end")


def _add_external_subgraph(
    lines: list[str],
    external_deps: dict[str, int],
    max_external: int,
) -> dict[str, str]:
    """Add external dependencies subgraph.

    Args:
        lines: Lines list to append to.
        external_deps: External dependency counts.
        max_external: Maximum externals to show.

    Returns:
        Mapping of external module to node ID.
    """
    ext_node_ids: dict[str, str] = {}
    if not external_deps:
        return ext_node_ids

    top_external = sorted(external_deps.items(), key=lambda x: -x[1])[:max_external]
    if top_external:
        lines.append("    subgraph external[External Dependencies]")
        for i, (ext, _count) in enumerate(top_external):
            ext_id = f"E{i}"
            ext_node_ids[ext] = ext_id
            lines.append(f"        {ext_id}([{ext}]):::external")
        lines.append("    end")
    return ext_node_ids


def _add_edges(
    lines: list[str],
    internal_deps: dict[str, set[str]],
    node_ids: dict[str, str],
    circular_edges: set[tuple[str, str]],
) -> None:
    """Add internal dependency edges to the diagram.

    Args:
        lines: Lines list to append to.
        internal_deps: Internal dependency mapping.
        node_ids: Module to node ID mapping.
        circular_edges: Set of circular dependency edges.
    """
    for module, imports in sorted(internal_deps.items()):
        from_id = node_ids.get(module)
        if not from_id:
            continue
        for imp in sorted(imports):
            to_id = node_ids.get(imp)
            if to_id and from_id != to_id:
                if (module, imp) in circular_edges or (imp, module) in circular_edges:
                    lines.append(f"    {from_id} -.->|circular| {to_id}")
                else:
                    lines.append(f"    {from_id} --> {to_id}")


def _add_circular_styling(
    lines: list[str],
    internal_deps: dict[str, set[str]],
    node_ids: dict[str, str],
    circular_edges: set[tuple[str, str]],
) -> None:
    """Add styling for circular dependencies.

    Args:
        lines: Lines list to append to.
        internal_deps: Internal dependency mapping.
        node_ids: Module to node ID mapping.
        circular_edges: Set of circular dependency edges.
    """
    if not circular_edges:
        return

    lines.append("    linkStyle default stroke:#666")
    link_idx = 0
    for module, imports in sorted(internal_deps.items()):
        from_id = node_ids.get(module)
        if not from_id:
            continue
        for imp in sorted(imports):
            to_id = node_ids.get(imp)
            if to_id and from_id != to_id:
                if (module, imp) in circular_edges or (imp, module) in circular_edges:
                    lines.append(
                        f"    linkStyle {link_idx} stroke:#f00,stroke-width:2px"
                    )
                link_idx += 1


def generate_dependency_graph(
    chunks: list,
    project_name: str = "project",
    **kwargs: object,
) -> str | None:
    """Generate an enhanced Mermaid flowchart showing module dependencies.

    Features:
    - Subgraphs grouping modules by top-level directory
    - Clickable nodes linking to wiki pages (when wiki_base_path provided)
    - Optional external dependency display with different styling
    - Circular dependency detection and highlighting

    Args:
        chunks: List of CodeChunk objects (should include IMPORT chunks).
        project_name: Name of the project for filtering internal imports.

    Keyword Args:
        detect_circular: Whether to highlight circular dependencies (default True).
        show_external: Whether to show external dependencies (default False).
        max_external: Maximum number of external dependencies (default 10).
        wiki_base_path: Base path for wiki links (default "").
        exclude_tests: Whether to exclude test modules (default True).

    Returns:
        Mermaid flowchart markdown string, or None if no dependencies found.
    """
    detect_circular: bool = bool(kwargs.get("detect_circular", True))
    show_external: bool = bool(kwargs.get("show_external", False))
    max_external: int = int(kwargs.get("max_external", 10))  # type: ignore[arg-type]
    wiki_base_path: str = str(kwargs.get("wiki_base_path", ""))
    exclude_tests: bool = bool(kwargs.get("exclude_tests", True))

    # Collect all dependency data
    data = _collect_dependencies(
        chunks, project_name, show_external=show_external, exclude_tests=exclude_tests
    )

    if not data.dependencies:
        return None

    # Build internal dependency graph
    internal_deps = _build_internal_deps(data.dependencies, data.all_internal_modules)
    module_groups = _group_modules(data.all_internal_modules)
    node_ids = _build_node_ids(data.all_internal_modules)

    # Detect circular dependencies
    circular_edges: set[tuple[str, str]] = set()
    if detect_circular and internal_deps:
        circular_edges = _find_circular_dependencies(internal_deps)

    # Build Mermaid flowchart
    lines = ["```mermaid", "flowchart TD"]

    # Add module subgraphs
    _add_subgraphs(lines, module_groups, node_ids)

    # Add external dependencies if enabled
    ext_node_ids: dict[str, str] = {}
    if show_external:
        ext_node_ids = _add_external_subgraph(lines, data.external_deps, max_external)

    # Add internal dependency edges
    _add_edges(lines, internal_deps, node_ids, circular_edges)

    _add_external_edges(lines, data, ext_node_ids, node_ids, show_external)
    _add_wiki_links(lines, node_ids, project_name, wiki_base_path)

    lines.append("    classDef external fill:#2d2d3d,stroke:#666,stroke-dasharray: 5 5")
    _add_circular_styling(lines, internal_deps, node_ids, circular_edges)

    lines.append("```")

    return "\n".join(lines)


def _add_external_edges(
    lines: list[str],
    data: Any,
    ext_node_ids: dict[str, str],
    node_ids: dict[str, str],
    show_external: bool,
) -> None:
    """Append external dependency edges to the Mermaid flowchart lines."""
    if not (show_external and ext_node_ids):
        return
    for module, ext_imports in sorted(data.module_external_deps.items()):
        from_id = node_ids.get(module)
        if not from_id:
            continue
        for ext in sorted(ext_imports):
            target_ext_id = ext_node_ids.get(ext)
            if target_ext_id:
                lines.append(f"    {from_id} -.-> {target_ext_id}")


def _add_wiki_links(
    lines: list[str],
    node_ids: dict[str, str],
    project_name: str,
    wiki_base_path: str,
) -> None:
    """Append Mermaid click handlers linking nodes to wiki pages."""
    if not wiki_base_path:
        return
    for module, node_id in sorted(node_ids.items()):
        wiki_path = _module_to_wiki_path(module, project_name)
        lines.append(f'    click {node_id} "{wiki_base_path}{wiki_path}"')


def _parse_external_import(line: str) -> str | None:
    """Parse an import line to extract external module name.

    Args:
        line: Import line like 'from pathlib import Path' or 'import os'

    Returns:
        Top-level module name if external import, None otherwise.
    """
    # from X import Y - extract X's top-level module
    from_match = re.match(r"from\s+([\w.]+)\s+import", line)
    if from_match:
        module = from_match.group(1)
        # Get top-level package name
        top_level = module.split(".")[0]
        # Skip relative imports and stdlib typing
        if top_level and not top_level.startswith("_"):
            return top_level
        return None

    # import X - extract X's top-level module
    import_match = re.match(r"import\s+([\w.]+)", line)
    if import_match:
        module = import_match.group(1)
        top_level = module.split(".")[0]
        if top_level and not top_level.startswith("_"):
            return top_level

    return None


def _module_to_wiki_path(module: str, project_name: str) -> str:
    """Convert module name to wiki file path.

    Args:
        module: Module name like 'core.parser'
        project_name: Project name like 'local_deepwiki'

    Returns:
        Wiki path like 'src/local_deepwiki/core/parser.md'
    """
    return f"src/{project_name}/{module.replace('.', '/')}.md"


def _find_circular_dependencies(deps: dict[str, set[str]]) -> set[tuple[str, str]]:
    """Find circular dependencies in a dependency graph.

    Delegates to the canonical ``find_circular_dependency_edges`` helper.

    Args:
        deps: Mapping of module to its dependencies.

    Returns:
        Set of (from, to) tuples that form circular dependencies.
    """
    return find_circular_dependency_edges(deps)


def _path_to_module(file_path: str) -> str | None:
    """Convert file path to module name.

    Args:
        file_path: Path like 'src/local_deepwiki/core/indexer.py'

    Returns:
        Module name like 'core.indexer', or None if not applicable.
    """
    p = Path(file_path)
    if p.suffix != ".py":
        return None
    if p.name.startswith("__"):
        return None

    parts = list(p.parts)

    # Strip leading src/ directory if present
    try:
        if "src" in parts:
            idx = parts.index("src")
            parts = parts[idx + 1 :]
    except (ValueError, IndexError):
        logger.debug("Failed to extract module path from %s", file_path, exc_info=True)

    # Skip the top-level package directory (e.g. 'local_deepwiki') only when
    # there is enough nesting that doing so still leaves a meaningful path.
    # For shallow layouts like package/file.py the package name is the only
    # context and must be preserved.
    if len(parts) > 2:
        parts = parts[1:]

    # Remove .py extension from last part
    if parts:
        parts[-1] = parts[-1].replace(".py", "")

    return ".".join(parts) if parts else None


def _parse_import_line(line: str, project_name: str) -> str | None:
    """Parse an import line to extract module name.

    Args:
        line: Import line like 'from local_deepwiki.core import parser'
        project_name: Project name to filter internal imports.

    Returns:
        Module name if internal import, None otherwise.
    """
    # from X import Y
    from_match = re.match(r"from\s+([\w.]+)\s+import", line)
    if from_match:
        module = from_match.group(1)
        if project_name in module:
            # Extract relative module path
            parts = module.split(".")
            if project_name in parts:
                idx = parts.index(project_name)
                rel_parts = parts[idx + 1 :]
                if rel_parts:
                    return ".".join(rel_parts)
        return None

    # import X
    import_match = re.match(r"import\s+([\w.]+)", line)
    if import_match:
        module = import_match.group(1)
        if project_name in module:
            parts = module.split(".")
            if project_name in parts:
                idx = parts.index(project_name)
                rel_parts = parts[idx + 1 :]
                if rel_parts:
                    return ".".join(rel_parts)

    return None
