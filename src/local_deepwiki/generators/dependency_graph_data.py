"""Data structures and utilities for dependency graph generation.

Contains the import patterns, dataclasses, and helper functions used by
the ``DependencyGraphGenerator`` class.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import dropwhile
from pathlib import Path


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


@dataclass
class DependencyNode:
    """A node in the dependency graph."""

    name: str
    file_path: str
    is_external: bool = False
    is_test: bool = False


@dataclass
class DependencyEdge:
    """An edge in the dependency graph."""

    source: str
    target: str
    count: int = 1
    is_circular: bool = False


@dataclass
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

    Args:
        file_path: File path to check.

    Returns:
        True if the file is a test file.
    """
    path_lower = file_path.lower()
    return (
        "/test/" in path_lower
        or "/tests/" in path_lower
        or file_path.startswith("test_")
        or "/test_" in file_path
        or "_test.py" in file_path
        or ".test." in file_path
        or "/spec/" in path_lower
        or ".spec." in path_lower
    )


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
