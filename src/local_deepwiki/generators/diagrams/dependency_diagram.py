"""Dependency graph generation using Mermaid."""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from local_deepwiki.models import ChunkType

from ._utils import sanitize_mermaid_name

logger = logging.getLogger(__name__)


def _is_test_module(module: str, file_path: str) -> bool:
    """Check if a module is a test module.

    Args:
        module: Module name like 'test_parser' or 'core.indexer'.
        file_path: File path like 'tests/test_parser.py'.

    Returns:
        True if this is a test module.
    """
    # Check module name
    if module.startswith("test_") or ".test_" in module:
        return True
    # Check file path
    if "/tests/" in file_path or file_path.startswith("tests/"):
        return True
    return False


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
    project_name: str,
    *,
    show_external: bool,
    exclude_tests: bool,
    dependencies: dict[str, set[str]],
    external_deps: Counter[str],
    module_external_deps: dict[str, set[str]],
    all_internal_modules: set[str],
) -> None:
    """Scan content lines for import statements and update dependency data.

    Only lines starting with ``import `` or ``from `` are considered,
    so non-import content (function bodies, comments, etc.) is safely skipped.

    Args:
        content: Raw chunk content to scan.
        module: Module name derived from the chunk's file path.
        project_name: Project name for filtering internal imports.
        show_external: Whether to collect external dependencies.
        exclude_tests: Whether to exclude test module imports.
        dependencies: Mutable dependency mapping to update.
        external_deps: Mutable external dependency counter to update.
        module_external_deps: Mutable per-module external deps to update.
        all_internal_modules: Mutable set of known internal modules to update.
    """
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Only consider lines that look like import statements
        if not (line.startswith("import ") or line.startswith("from ")):
            continue

        imported = _parse_import_line(line, project_name)
        if imported:
            if exclude_tests and imported.startswith("test_"):
                continue
            dependencies[module].add(imported)
            all_internal_modules.add(imported)
        elif show_external:
            ext_module = _parse_external_import(line)
            if ext_module:
                external_deps[ext_module] += 1
                module_external_deps[module].add(ext_module)


_FALLBACK_CHUNK_TYPES = frozenset(
    {ChunkType.MODULE, ChunkType.FUNCTION, ChunkType.CLASS}
)


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
    dependencies: dict[str, set[str]] = defaultdict(set)
    external_deps: Counter[str] = Counter()
    module_external_deps: dict[str, set[str]] = defaultdict(set)
    all_internal_modules: set[str] = set()

    # Track which files have dedicated IMPORT chunks
    files_with_import_chunks: set[str] = set()
    # Buffer non-import chunks for the fallback pass
    fallback_chunks: list = []

    for chunk in chunks:
        if hasattr(chunk, "chunk"):
            chunk = chunk.chunk

        if chunk.chunk_type == ChunkType.IMPORT:
            file_path = chunk.file_path
            module = _path_to_module(file_path)
            if not module:
                continue

            if exclude_tests and _is_test_module(module, file_path):
                continue

            files_with_import_chunks.add(file_path)
            all_internal_modules.add(module)

            _scan_import_lines(
                chunk.content,
                module,
                project_name,
                show_external=show_external,
                exclude_tests=exclude_tests,
                dependencies=dependencies,
                external_deps=external_deps,
                module_external_deps=module_external_deps,
                all_internal_modules=all_internal_modules,
            )
        elif chunk.chunk_type in _FALLBACK_CHUNK_TYPES:
            fallback_chunks.append(chunk)

    # Second pass: scan non-import chunks for files without dedicated IMPORT chunks
    for chunk in fallback_chunks:
        if hasattr(chunk, "chunk"):
            chunk = chunk.chunk

        file_path = chunk.file_path
        if file_path in files_with_import_chunks:
            continue

        module = _path_to_module(file_path)
        if not module:
            continue

        if exclude_tests and _is_test_module(module, file_path):
            continue

        all_internal_modules.add(module)

        _scan_import_lines(
            chunk.content,
            module,
            project_name,
            show_external=show_external,
            exclude_tests=exclude_tests,
            dependencies=dependencies,
            external_deps=external_deps,
            module_external_deps=module_external_deps,
            all_internal_modules=all_internal_modules,
        )

    return _DependencyData(
        dependencies=dependencies,
        external_deps=external_deps,
        module_external_deps=module_external_deps,
        all_internal_modules=all_internal_modules,
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
    *,
    detect_circular: bool = True,
    show_external: bool = False,
    max_external: int = 10,
    wiki_base_path: str = "",
    exclude_tests: bool = True,
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
        detect_circular: Whether to highlight circular dependencies.
        show_external: Whether to show external (third-party) dependencies.
        max_external: Maximum number of external dependencies to display.
        wiki_base_path: Base path for wiki links (e.g., "files/"). Empty disables links.
        exclude_tests: Whether to exclude test modules from the graph (default: True).

    Returns:
        Mermaid flowchart markdown string, or None if no dependencies found.
    """
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

    # Add external dependency edges
    if show_external and ext_node_ids:
        for module, ext_imports in sorted(data.module_external_deps.items()):
            from_id = node_ids.get(module)
            if not from_id:
                continue
            for ext in sorted(ext_imports):
                target_ext_id = ext_node_ids.get(ext)
                if target_ext_id:
                    lines.append(f"    {from_id} -.-> {target_ext_id}")

    # Add click handlers for wiki links
    if wiki_base_path:
        for module, node_id in sorted(node_ids.items()):
            wiki_path = _module_to_wiki_path(module, project_name)
            lines.append(f'    click {node_id} "{wiki_base_path}{wiki_path}"')

    # Add styling
    lines.append("    classDef external fill:#2d2d3d,stroke:#666,stroke-dasharray: 5 5")
    _add_circular_styling(lines, internal_deps, node_ids, circular_edges)

    lines.append("```")

    return "\n".join(lines)


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

    Args:
        deps: Mapping of module to its dependencies.

    Returns:
        Set of (from, to) tuples that form circular dependencies.
    """
    circular: set[tuple[str, str]] = set()

    def dfs(node: str, path: list[str], visited: set[str]) -> None:
        if node in path:
            # Found a cycle - mark all edges in the cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            for src, tgt in zip(cycle, cycle[1:]):
                circular.add((src, tgt))
            return

        if node in visited:
            return

        visited.add(node)
        path.append(node)

        for dep in deps.get(node, []):
            dfs(dep, path.copy(), visited)

    for module in deps:
        dfs(module, [], set())

    return circular


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
