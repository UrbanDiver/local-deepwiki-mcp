"""Dependency graph visualization for module interdependencies.

This module provides a dedicated DependencyGraphGenerator class for generating
Mermaid dependency graphs showing module/file interdependencies with circular
dependency detection.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from local_deepwiki.models import ChunkType, IndexStatus

# Re-export extracted data structures and utilities for backward compatibility
from local_deepwiki.generators.analysis.dependency_graph_data import (  # noqa: F401
    IMPORT_PATTERNS,
    DependencyEdge,
    DependencyGraph,
    DependencyNode,
    _SKIP_DIRS,
    _extract_module_name,
    _get_directory_module,
    _is_test_path,
    _sanitize_mermaid_name,
    find_circular_dependencies,
    infer_package_name,
)

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore import VectorStore


# ---------------------------------------------------------------------------
# Module-level pure helpers — no instance state required
# ---------------------------------------------------------------------------


def _normalize_cycle(cycle: list[str]) -> list[str]:
    """Normalize a cycle for consistent comparison.

    Rotates the cycle so that the smallest element is first.

    Args:
        cycle: List of nodes forming a cycle.

    Returns:
        Normalized cycle list.
    """
    if len(cycle) <= 1:
        return cycle

    # Remove the duplicate last element if present
    if cycle[0] == cycle[-1] and len(cycle) > 1:
        cycle = cycle[:-1]

    # Find the minimum element and rotate
    min_idx = cycle.index(min(cycle))
    return cycle[min_idx:] + cycle[:min_idx]


def _get_circular_edges(cycles: list[list[str]]) -> set[tuple[str, str]]:
    """Extract edges that are part of circular dependencies.

    Args:
        cycles: List of detected cycles.

    Returns:
        Set of (source, target) tuples that form cycles.
    """
    edges: set[tuple[str, str]] = set()
    for cycle in cycles:
        rotated = cycle[1:] + cycle[:1]
        for source, target in zip(cycle, rotated):
            edges.add((source, target))
    return edges


def _parse_imports(content: str, language: str) -> list[str]:
    """Parse import statements from code content.

    Args:
        content: Code content with import statements.
        language: Programming language.

    Returns:
        List of imported module names.
    """
    imports: list[str] = []

    # Get patterns for this language
    patterns = IMPORT_PATTERNS.get(language, IMPORT_PATTERNS.get("python", []))

    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        for pattern in patterns:
            match = pattern.search(line)
            if match:
                imports.append(match.group(1))
                break

    return imports


def _file_path_to_wiki_path(file_path: str) -> str:
    """Convert a file path to its wiki page path.

    Args:
        file_path: Source file path.

    Returns:
        Wiki page path.
    """
    path = Path(file_path)
    wiki_path = str(path.with_suffix(".md"))
    return f"files/{wiki_path}"


def _generate_empty_graph_message(message: str) -> str:
    """Generate a placeholder for empty graphs.

    Args:
        message: Message to display.

    Returns:
        Mermaid diagram with placeholder message.
    """
    return f"```mermaid\nflowchart TD\n    A[{message}]\n```"


def _render_file_graph(graph: DependencyGraph, module_path: str) -> str:
    """Render the file dependency graph as Mermaid markdown.

    Args:
        graph: The dependency graph to render.
        module_path: Module path being visualized.

    Returns:
        Mermaid flowchart markdown string.
    """
    lines = ["```mermaid", "flowchart TD"]
    lines.append(f"    subgraph {_sanitize_mermaid_name(module_path)}[{module_path}]")

    # Create node ID mapping
    node_ids: dict[str, str] = {}
    for i, (name, _node) in enumerate(sorted(graph.nodes.items())):
        node_id = f"F{i}"
        node_ids[name] = node_id
        lines.append(f"        {node_id}[{name}]")

    lines.append("    end")

    # Add edges
    link_idx = 0
    circular_link_indices: list[int] = []

    for (source, target), edge in sorted(graph.edges.items()):
        source_id = node_ids.get(source)
        target_id = node_ids.get(target)

        if source_id and target_id:
            if edge.is_circular:
                lines.append(f"    {source_id} -.->|circular| {target_id}")
                circular_link_indices.append(link_idx)
            else:
                lines.append(f"    {source_id} --> {target_id}")
            link_idx += 1

    # Add circular styling
    if circular_link_indices:
        lines.append("    linkStyle default stroke:#666")
        for idx in circular_link_indices:
            lines.append(f"    linkStyle {idx} stroke:#f00,stroke-width:2px")

    lines.append("```")

    # Add cycle warnings
    if graph.cycles:
        lines.append("")
        lines.append("**Warning: Circular dependencies detected!**")
        for cycle in graph.cycles[:3]:
            cycle_str = " -> ".join(cycle) + " -> " + cycle[0]
            lines.append(f"- `{cycle_str}`")

    return "\n".join(lines)


def _render_subgraphs(
    groups: dict[str, list[DependencyNode]],
    node_ids: dict[str, str],
    idx: int,
) -> tuple[list[str], int]:
    """Render internal module subgraphs into Mermaid lines.

    Args:
        groups: Mapping of top-level package name to its nodes.
        node_ids: Mutable mapping that will be updated with new node IDs.
        idx: Current node index counter.

    Returns:
        Tuple of (lines, updated_idx).
    """
    lines: list[str] = []
    for group_name, nodes in sorted(groups.items()):
        safe_group = _sanitize_mermaid_name(group_name)
        display_name = group_name.replace("_", " ").title()
        lines.append(f"    subgraph {safe_group}[{display_name}]")
        for node in sorted(nodes, key=lambda n: n.name):
            node_id = f"M{idx}"
            node_ids[node.name] = node_id
            idx += 1
            display = node.name.split(".")[-1]
            lines.append(f"        {node_id}[{display}]")
        lines.append("    end")
    return lines, idx


def _render_external_subgraph(
    external_nodes: list[DependencyNode],
    max_external: int,
    node_ids: dict[str, str],
    idx: int,
) -> tuple[list[str], int]:
    """Render the external dependencies subgraph into Mermaid lines.

    Args:
        external_nodes: List of external dependency nodes.
        max_external: Maximum number of external nodes to show.
        node_ids: Mutable mapping that will be updated with new node IDs.
        idx: Current node index counter.

    Returns:
        Tuple of (lines, updated_idx).
    """
    lines: list[str] = []
    ext_nodes_to_show = sorted(external_nodes, key=lambda n: n.name)[:max_external]
    lines.append("    subgraph external[External Dependencies]")
    for node in ext_nodes_to_show:
        node_id = f"E{idx}"
        node_ids[node.name] = node_id
        idx += 1
        lines.append(f"        {node_id}([{node.name}]):::external")
    lines.append("    end")
    return lines, idx


def _render_edges(
    graph: DependencyGraph,
    node_ids: dict[str, str],
) -> tuple[list[str], list[int]]:
    """Render edge lines for the module dependency graph.

    Args:
        graph: The dependency graph with edges.
        node_ids: Mapping of node name to Mermaid node ID.

    Returns:
        Tuple of (edge_lines, circular_link_indices).
    """
    lines: list[str] = []
    link_idx = 0
    circular_link_indices: list[int] = []

    for (source, target), edge in sorted(graph.edges.items()):
        source_id = node_ids.get(source)
        target_id = node_ids.get(target)
        if not (source_id and target_id and source_id != target_id):
            continue
        if edge.is_circular:
            lines.append(f"    {source_id} -.->|circular| {target_id}")
            circular_link_indices.append(link_idx)
        elif edge.count > 1:
            lines.append(f"    {source_id} -->|{edge.count}| {target_id}")
        else:
            is_ext = graph.nodes.get(
                target, DependencyNode(name="", file_path="")
            ).is_external
            if is_ext:
                lines.append(f"    {source_id} -.-> {target_id}")
            else:
                lines.append(f"    {source_id} --> {target_id}")
        link_idx += 1

    return lines, circular_link_indices


def _render_click_handlers(
    graph: DependencyGraph,
    node_ids: dict[str, str],
    wiki_base_path: str,
) -> list[str]:
    """Render click handler lines for wiki navigation.

    Args:
        graph: The dependency graph with node metadata.
        node_ids: Mapping of node name to Mermaid node ID.
        wiki_base_path: Base path for wiki links.

    Returns:
        List of click handler lines.
    """
    lines: list[str] = []
    for node_name, node_id in sorted(node_ids.items()):
        node = graph.nodes.get(node_name)  # type: ignore[assignment]
        if node and not node.is_external and node.file_path:
            wiki_path = _file_path_to_wiki_path(node.file_path)
            lines.append(f'    click {node_id} "{wiki_base_path}{wiki_path}"')
    return lines


def _render_styling(circular_link_indices: list[int]) -> list[str]:
    """Render class definition and link styling lines.

    Args:
        circular_link_indices: Link indices that should be styled as circular.

    Returns:
        List of styling lines.
    """
    lines: list[str] = [
        "    classDef external fill:#2d2d3d,stroke:#666,stroke-dasharray: 5 5",
        "    classDef circular fill:#ff6b6b,stroke:#c92a2a",
    ]
    if circular_link_indices:
        lines.append("    linkStyle default stroke:#666")
        for idx in circular_link_indices:
            lines.append(f"    linkStyle {idx} stroke:#f00,stroke-width:2px")
    return lines


def _render_cycle_warnings(graph: DependencyGraph) -> list[str]:
    """Render circular dependency warning lines appended after the diagram.

    Args:
        graph: The dependency graph with detected cycles.

    Returns:
        List of warning lines (may be empty if no cycles).
    """
    if not graph.cycles:
        return []
    lines: list[str] = [
        "",
        "**Warning: Circular dependencies detected!**",
        "",
    ]
    for i, cycle in enumerate(graph.cycles[:5], 1):
        cycle_str = " -> ".join(cycle) + " -> " + cycle[0]
        lines.append(f"{i}. `{cycle_str}`")
    if len(graph.cycles) > 5:
        lines.append(f"   ... and {len(graph.cycles) - 5} more")
    return lines


def _render_module_graph(
    graph: DependencyGraph,
    show_external: bool,
    max_external: int,
    wiki_base_path: str,
) -> str:
    """Render the module dependency graph as Mermaid markdown.

    Args:
        graph: The dependency graph to render.
        show_external: Whether to show external dependencies.
        max_external: Maximum external dependencies to show.
        wiki_base_path: Base path for wiki links.

    Returns:
        Mermaid flowchart markdown string.
    """
    lines = ["```mermaid", "flowchart TD"]

    # Group nodes by top-level package
    groups: dict[str, list[DependencyNode]] = defaultdict(list)
    external_nodes = [node for node in graph.nodes.values() if node.is_external]
    for node in graph.nodes.values():
        if not node.is_external:
            group = node.name.split(".")[0] if "." in node.name else "root"
            groups[group].append(node)

    # Build node ID mapping via subgraph rendering
    node_ids: dict[str, str] = {}
    idx = 0

    subgraph_lines, idx = _render_subgraphs(groups, node_ids, idx)
    lines.extend(subgraph_lines)

    if show_external and external_nodes:
        ext_lines, idx = _render_external_subgraph(
            external_nodes, max_external, node_ids, idx
        )
        lines.extend(ext_lines)

    edge_lines, circular_link_indices = _render_edges(graph, node_ids)
    lines.extend(edge_lines)

    if wiki_base_path:
        lines.extend(_render_click_handlers(graph, node_ids, wiki_base_path))

    lines.extend(_render_styling(circular_link_indices))
    lines.append("```")
    lines.extend(_render_cycle_warnings(graph))

    return "\n".join(lines)


class DependencyGraphGenerator:
    """Generator for module and file dependency graphs.

    This class analyzes code imports from indexed chunks and generates
    Mermaid diagrams showing module interdependencies, including detection
    of circular dependencies.
    """

    # Pure helpers promoted to module level — kept as class attributes so
    # existing call sites (including tests) can reach them via the instance.
    _normalize_cycle = staticmethod(_normalize_cycle)
    _get_circular_edges = staticmethod(_get_circular_edges)
    _parse_imports = staticmethod(_parse_imports)
    _file_path_to_wiki_path = staticmethod(_file_path_to_wiki_path)
    _generate_empty_graph_message = staticmethod(_generate_empty_graph_message)
    _render_file_graph = staticmethod(_render_file_graph)
    _render_module_graph = staticmethod(_render_module_graph)

    def __init__(self, vector_store: "VectorStore"):
        """Initialize the dependency graph generator.

        Args:
            vector_store: Vector store with indexed code chunks.
        """
        self._store = vector_store
        self._project_name: str = ""

    async def generate_module_graph(
        self,
        index_status: IndexStatus,
        *,
        show_external: bool = False,
        max_external: int = 10,
        exclude_tests: bool = True,
        wiki_base_path: str = "",
    ) -> str:
        """Generate Mermaid graph of module dependencies.

        Args:
            index_status: Index status with file information.
            show_external: Whether to show external dependencies.
            max_external: Maximum external dependencies to show.
            exclude_tests: Whether to exclude test modules.
            wiki_base_path: Base path for wiki links.

        Returns:
            Mermaid flowchart markdown string showing module dependencies.
        """
        # Extract project name from repo path
        self._project_name = Path(index_status.repo_path).name.lower().replace("-", "_")

        # Build the dependency graph
        graph = await self._build_dependency_graph(
            index_status=index_status,
            show_external=show_external,
            exclude_tests=exclude_tests,
        )

        if not graph.nodes:
            return _generate_empty_graph_message("No module dependencies found.")

        # Detect circular dependencies
        graph.cycles = self.detect_circular_dependencies(graph.get_adjacency_list())

        # Mark circular edges
        circular_edges = _get_circular_edges(graph.cycles)
        for edge_key in circular_edges:
            if edge_key in graph.edges:
                graph.edges[edge_key] = dataclasses.replace(
                    graph.edges[edge_key], is_circular=True
                )

        # Generate Mermaid diagram
        return _render_module_graph(
            graph=graph,
            show_external=show_external,
            max_external=max_external,
            wiki_base_path=wiki_base_path,
        )

    async def generate_file_graph(
        self,
        index_status: IndexStatus,
        module_path: str,
        exclude_tests: bool = True,
    ) -> str:
        """Generate Mermaid graph for files within a module.

        Args:
            index_status: Index status with file information.
            module_path: Module/directory path to show files for.
            exclude_tests: Whether to exclude test files.

        Returns:
            Mermaid flowchart markdown string showing file dependencies.
        """
        self._project_name = Path(index_status.repo_path).name.lower().replace("-", "_")

        # Get files in the specified module
        module_files = [
            f
            for f in index_status.files
            if module_path in f.path and f.path.endswith(".py")
        ]

        if exclude_tests:
            module_files = [f for f in module_files if not _is_test_path(f.path)]

        if not module_files:
            return _generate_empty_graph_message(
                f"No files found in module: {module_path}"
            )

        # Build nodes for all files in this module
        graph = DependencyGraph()

        for file_info in module_files:
            file_name = Path(file_info.path).stem
            graph.add_node(
                DependencyNode(
                    name=file_name,
                    file_path=file_info.path,
                    is_test=_is_test_path(file_info.path),
                )
            )

        # Search for imports mentioning the module
        search_results = await self._store.search(
            f"import {module_path}",
            limit=100,
            chunk_type="import",
        )

        file_stems = [Path(f.path).stem for f in module_files]
        for result in search_results:
            chunk = result.chunk
            if chunk.chunk_type != ChunkType.IMPORT:
                continue

            source_file = Path(chunk.file_path).stem
            if module_path not in chunk.file_path:
                continue

            imports = _parse_imports(chunk.content, chunk.language.value)
            for imp in imports:
                if module_path in imp or imp in file_stems:
                    target_file = imp.split(".")[-1]
                    if target_file in file_stems:
                        graph.add_edge(source_file, target_file)

        # Detect and mark circular edges
        graph.cycles = self.detect_circular_dependencies(graph.get_adjacency_list())
        circular_edges = _get_circular_edges(graph.cycles)
        for edge_key in circular_edges:
            if edge_key in graph.edges:
                graph.edges[edge_key] = dataclasses.replace(
                    graph.edges[edge_key], is_circular=True
                )

        return _render_file_graph(graph, module_path)

    def detect_circular_dependencies(
        self, graph: dict[str, set[str]]
    ) -> list[list[str]]:
        """Find all circular dependency cycles using DFS.

        Delegates to the standalone ``find_circular_dependencies`` helper.

        Args:
            graph: Adjacency list mapping module to its dependencies.

        Returns:
            List of cycles, where each cycle is a list of module names.
        """
        return find_circular_dependencies(graph)

    async def _build_dependency_graph(
        self,
        index_status: IndexStatus,
        show_external: bool,
        exclude_tests: bool,
    ) -> DependencyGraph:
        """Build dependency graph from indexed chunks.

        Args:
            index_status: Index status with file information.
            show_external: Whether to include external dependencies.
            exclude_tests: Whether to exclude test files.

        Returns:
            Populated DependencyGraph.
        """
        graph = DependencyGraph()

        internal_modules: set[str] = set()
        file_to_module: dict[str, str] = {}

        for file_info in index_status.files:
            if exclude_tests and _is_test_path(file_info.path):
                continue

            module_name = _extract_module_name(file_info.path, index_status.repo_path)
            internal_modules.add(module_name)
            file_to_module[file_info.path] = module_name

            graph.add_node(
                DependencyNode(
                    name=module_name,
                    file_path=file_info.path,
                    is_test=_is_test_path(file_info.path),
                )
            )

        import_results = await self._store.search(
            "import require include from use",
            limit=500,
            chunk_type="import",
        )

        for result in import_results:
            chunk = result.chunk
            if chunk.chunk_type != ChunkType.IMPORT:
                continue

            if exclude_tests and _is_test_path(chunk.file_path):
                continue

            source_module = file_to_module.get(chunk.file_path)
            if not source_module:
                source_module = _extract_module_name(
                    chunk.file_path, index_status.repo_path
                )
                graph.add_node(
                    DependencyNode(
                        name=source_module,
                        file_path=chunk.file_path,
                    )
                )
                internal_modules.add(source_module)

            imports = _parse_imports(chunk.content, chunk.language.value)

            for imp in imports:
                if self._is_internal_import(imp, internal_modules):
                    target_module = self._resolve_internal_import(imp, internal_modules)
                    if target_module and target_module != source_module:
                        graph.add_edge(source_module, target_module)
                elif show_external:
                    ext_name = imp.split(".")[0]
                    if ext_name and not ext_name.startswith("_"):
                        if ext_name not in graph.nodes:
                            graph.add_node(
                                DependencyNode(
                                    name=ext_name,
                                    file_path="",
                                    is_external=True,
                                )
                            )
                        graph.add_edge(source_module, ext_name)

        return graph

    def _is_internal_import(self, import_name: str, internal_modules: set[str]) -> bool:
        """Check if an import refers to an internal module.

        Args:
            import_name: Import module name.
            internal_modules: Set of known internal module names.

        Returns:
            True if the import is internal.
        """
        if import_name in internal_modules:
            return True

        if self._project_name and import_name.startswith(self._project_name + "."):
            return True

        import_parts = import_name.split(".")
        for module in internal_modules:
            module_parts = module.split(".")
            if import_parts[-1] == module_parts[-1]:
                return True
            if import_name.endswith("." + module):
                return True

        return False

    def _resolve_internal_import(
        self, import_name: str, internal_modules: set[str]
    ) -> str | None:
        """Resolve an import name to an internal module.

        Args:
            import_name: Import module name.
            internal_modules: Set of known internal module names.

        Returns:
            Resolved internal module name, or None if not found.
        """
        if import_name in internal_modules:
            return import_name

        if self._project_name:
            if import_name.startswith(self._project_name + "."):
                stripped = import_name[len(self._project_name) + 1 :]
                if stripped in internal_modules:
                    return stripped

        import_parts = import_name.split(".")
        for module in internal_modules:
            module_parts = module.split(".")
            if import_parts[-1] == module_parts[-1]:
                return module

        return None


async def generate_dependency_graph_page(
    index_status: IndexStatus,
    vector_store: "VectorStore",
    *,
    show_external: bool = True,
    max_external: int = 10,
    wiki_base_path: str = "files/",
) -> str:
    """Generate a complete dependency graph wiki page.

    Args:
        index_status: Index status with file information.
        vector_store: Vector store with indexed chunks.
        show_external: Whether to show external dependencies.
        max_external: Maximum external dependencies to show.
        wiki_base_path: Base path for wiki links.

    Returns:
        Markdown content for the dependency graph page.
    """
    generator = DependencyGraphGenerator(vector_store)

    module_graph = await generator.generate_module_graph(
        index_status=index_status,
        show_external=show_external,
        max_external=max_external,
        wiki_base_path=wiki_base_path,
    )

    content_parts = [
        "# Dependency Graph",
        "",
        "This page shows the module dependencies within the codebase.",
        "",
        "## Module Dependencies",
        "",
        "The following diagram shows how modules depend on each other. "
        "Click on a module to view its documentation.",
        "",
        module_graph,
        "",
    ]

    content_parts.extend(
        [
            "## Legend",
            "",
            "- **Solid arrows**: Internal module dependencies",
            "- **Dashed arrows**: External dependencies",
            "- **Red dashed arrows**: Circular dependencies (should be addressed)",
            "- **Numbers on arrows**: Number of import statements",
            "",
        ]
    )

    content_parts.extend(
        [
            "## Best Practices",
            "",
            "- Avoid circular dependencies as they can lead to import errors and make "
            "the codebase harder to understand",
            "- Consider using dependency injection or interfaces to break cycles",
            "- External dependencies are grouped separately for clarity",
            "",
        ]
    )

    return "\n".join(content_parts)
