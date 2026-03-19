"""Data structures and utilities for dependency graph generation.

Contains the import patterns, dataclasses, and helper functions used by
the ``DependencyGraphGenerator`` class.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import dropwhile
from pathlib import Path

from local_deepwiki.core.path_utils import is_test_file


# Language-specific import patterns
IMPORT_PATTERNS = {
    "python": [
        # from X import Y
        re.compile(r"^from\s+([\w.]+)\s+import"),
        # import X
        re.compile(r"^import\s+([\w.]+)"),
    ],
    "typescript": [
        # import { X } from "Y"
        re.compile(r'import\s+.*?\s+from\s+["\']([^"\']+)["\']'),
        # import "Y"
        re.compile(r'import\s+["\']([^"\']+)["\']'),
        # require("Y")
        re.compile(r'require\s*\(\s*["\']([^"\']+)["\']'),
    ],
    "javascript": [
        # import { X } from "Y"
        re.compile(r'import\s+.*?\s+from\s+["\']([^"\']+)["\']'),
        # import "Y"
        re.compile(r'import\s+["\']([^"\']+)["\']'),
        # require("Y")
        re.compile(r'require\s*\(\s*["\']([^"\']+)["\']'),
    ],
    "go": [
        # import "X"
        re.compile(r'import\s+["\']([^"\']+)["\']'),
        # import ( "X" )
        re.compile(r'^\s*["\']([^"\']+)["\']'),
    ],
    "rust": [
        # use X::Y
        re.compile(r"^use\s+([\w:]+)"),
        # mod X
        re.compile(r"^mod\s+(\w+)"),
    ],
    "java": [
        # import X.Y.Z
        re.compile(r"^import\s+([\w.]+)"),
    ],
}

# Common root directories to skip when extracting module names
_SKIP_DIRS = frozenset({"src", "lib", "pkg", "app", "source", "sources"})


@dataclass(frozen=True, slots=True)
class DependencyNode:
    """A node in the dependency graph."""

    name: str
    file_path: str
    is_external: bool = False
    is_test: bool = False


@dataclass(slots=True)
class DependencyEdge:
    """An edge in the dependency graph."""

    source: str
    target: str
    count: int = 1
    is_circular: bool = False


@dataclass(slots=True)
class DependencyGraph:
    """A complete dependency graph."""

    nodes: dict[str, DependencyNode] = field(default_factory=dict)
    edges: dict[tuple[str, str], DependencyEdge] = field(default_factory=dict)
    cycles: list[list[str]] = field(default_factory=list)

    def add_node(self, node: DependencyNode) -> None:
        """Add a node to the graph."""
        if node.name not in self.nodes:
            self.nodes[node.name] = node

    def add_edge(self, source: str, target: str) -> None:
        """Add an edge to the graph."""
        key = (source, target)
        if key in self.edges:
            self.edges[key].count += 1
        else:
            self.edges[key] = DependencyEdge(source=source, target=target)

    def get_adjacency_list(self) -> dict[str, set[str]]:
        """Get adjacency list representation of the graph."""
        adj: dict[str, set[str]] = defaultdict(set)
        for (source, target), _ in self.edges.items():
            adj[source].add(target)
        return dict(adj)


def _sanitize_mermaid_name(name: str) -> str:
    """Sanitize a name for use in Mermaid diagrams.

    Args:
        name: Original name.

    Returns:
        Sanitized name safe for Mermaid syntax.
    """
    result = name.replace("<", "_").replace(">", "_").replace(" ", "_")
    result = result.replace("[", "_").replace("]", "_").replace(".", "_")
    result = result.replace("-", "_").replace(":", "_").replace("/", "_")
    if result and result[0].isdigit():
        result = "M" + result
    return result


def _is_test_path(file_path: str) -> bool:
    """Check if a file path is a test file.

    Delegates to the canonical ``is_test_file`` helper in ``path_utils``.

    Args:
        file_path: File path to check.

    Returns:
        True if the file is a test file.
    """
    return is_test_file(file_path)


def _extract_module_name(file_path: str, project_root: str = "") -> str:
    """Extract module name from file path.

    Args:
        file_path: File path like 'src/myproject/core/parser.py'.
        project_root: Optional project root to strip.

    Returns:
        Module name like 'core.parser'.
    """
    path = Path(file_path)

    # Remove extension
    name = path.stem if path.suffix else path.name

    # Build module path from directory structure
    parts = list(path.parts[:-1])  # Exclude filename

    # Skip common root directories
    parts = list(dropwhile(lambda p: p.lower() in _SKIP_DIRS, parts))

    # Skip package directory if it matches project name
    if project_root:
        project_name = Path(project_root).name.lower().replace("-", "_")
        if parts and parts[0].lower().replace("-", "_") == project_name:
            parts = parts[1:]

    if parts:
        return ".".join(parts) + "." + name
    return name


def _get_directory_module(file_path: str) -> str:
    """Get the directory/module containing a file.

    Args:
        file_path: File path like 'src/myproject/core/parser.py'.

    Returns:
        Directory module name like 'core'.
    """
    path = Path(file_path)
    parts = list(path.parts[:-1])

    # Skip common root directories
    parts = list(dropwhile(lambda p: p.lower() in _SKIP_DIRS, parts))

    # Return the top-level module/directory
    if len(parts) >= 2:
        return parts[1] if parts[0] in _SKIP_DIRS else parts[0]
    elif parts:
        return parts[0]
    return "root"


def find_circular_dependencies(
    graph: dict[str, set[str] | Iterable[str]],
) -> list[list[str]]:
    """Find all circular dependency cycles using DFS.

    Args:
        graph: Adjacency list mapping module to its dependencies.

    Returns:
        List of cycles, where each cycle is a list of module names.
    """
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def _normalize_cycle(cycle: list[str]) -> list[str]:
        if len(cycle) <= 1:
            return cycle
        if cycle[0] == cycle[-1] and len(cycle) > 1:
            cycle = cycle[:-1]
        min_idx = cycle.index(min(cycle))
        return cycle[min_idx:] + cycle[:min_idx]

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                dfs(neighbor, path.copy())
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor) if neighbor in path else -1
                if cycle_start >= 0:
                    cycle = path[cycle_start:] + [neighbor]
                    normalized = _normalize_cycle(cycle)
                    if normalized not in cycles:
                        cycles.append(normalized)

        rec_stack.remove(node)

    for node in graph:
        if node not in visited:
            dfs(node, [])

    return cycles


def find_circular_dependency_edges(
    deps: dict[str, set[str]],
) -> set[tuple[str, str]]:
    """Find circular dependency *edges* in a dependency graph.

    Args:
        deps: Mapping of module to its dependencies.

    Returns:
        Set of (from, to) tuples that form circular dependencies.
    """
    circular: set[tuple[str, str]] = set()

    def dfs(node: str, path: list[str], visited: set[str]) -> None:
        if node in path:
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            for src, tgt in zip(cycle, cycle[1:]):
                circular.add((src, tgt))
            return

        if node in visited:
            return

        visited.add(node)
        path.append(node)

        for dep in deps.get(node, set()):
            dfs(dep, path.copy(), visited)

    for module in deps:
        dfs(module, [], set())

    return circular


def infer_package_name(repo_path: str | Path) -> str:
    """Infer the Python package name from a repository path.

    Uses the directory name, normalised with hyphens replaced by
    underscores (PEP 503).

    Args:
        repo_path: Path to the repository root.

    Returns:
        Lower-cased, underscore-separated package name.
    """
    return Path(repo_path).name.lower().replace("-", "_")
