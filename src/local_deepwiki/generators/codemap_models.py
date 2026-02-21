"""Data structures and constants for codemap generation.

Enums, frozen dataclasses, and module-level constants shared by the
codemap graph traversal, visualization, and orchestration modules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from local_deepwiki.models import ChunkType

# Patterns that indicate entry-point functions
ENTRY_PATTERNS = re.compile(
    r"^(main|handle_|run_|start_|cli_|route_|__main__|app\.|serve_|execute_|dispatch_)"
)

# Common builtins to skip during graph traversal
# fmt: off
BUILTIN_NAMES = frozenset({
    "print", "len", "str", "int", "float", "bool", "dict", "list", "set",
    "tuple", "range", "enumerate", "zip", "map", "filter", "sorted",
    "reversed", "min", "max", "sum", "any", "all", "isinstance",
    "issubclass", "hasattr", "getattr", "setattr", "type", "repr", "hash",
    "format", "open", "super", "next", "iter", "abs", "round", "append",
    "extend", "pop", "get", "keys", "values", "items", "join", "split",
    "strip", "replace", "lower", "upper", "find", "log", "debug", "info",
    "warning", "error",
})
# fmt: on

CALLABLE_CHUNK_TYPES = frozenset(
    {
        ChunkType.FUNCTION.value,
        ChunkType.CLASS.value,
        ChunkType.METHOD.value,
    }
)

# Weights for chunk types when scoring codemap topic suggestions.
# Classes often accumulate many connections just from their methods
# (e.g. __init__, properties), so they are downranked relative to
# functions and methods which represent actual execution flows.
CHUNK_TYPE_WEIGHTS: dict[str, float] = {
    ChunkType.FUNCTION.value: 1.0,
    ChunkType.METHOD.value: 1.0,
    ChunkType.CLASS.value: 0.3,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class CodemapFocus(StrEnum):
    """Focus mode for codemap generation."""

    EXECUTION_FLOW = "execution_flow"
    DATA_FLOW = "data_flow"
    DEPENDENCY_CHAIN = "dependency_chain"


@dataclass(frozen=True, slots=True)
class CodemapNode:
    """A single node in the codemap graph."""

    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str
    docstring: str | None = None
    content_preview: str = ""


@dataclass(frozen=True, slots=True)
class CodemapEdge:
    """A directed edge in the codemap graph."""

    source: str
    target: str
    edge_type: str
    source_file: str
    target_file: str


@dataclass
class CodemapGraph:
    """The complete codemap graph built via BFS."""

    nodes: dict[str, CodemapNode] = field(default_factory=dict)
    edges: list[CodemapEdge] = field(default_factory=list)
    entry_point: str | None = None

    @property
    def cross_file_edges(self) -> list[CodemapEdge]:
        return [e for e in self.edges if e.source_file != e.target_file]

    @property
    def files_involved(self) -> set[str]:
        return {node.file_path for node in self.nodes.values()}


@dataclass
class CodemapResult:
    """Final result returned by ``generate_codemap``."""

    query: str
    focus: str
    entry_point: str | None
    mermaid_diagram: str
    narrative: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    files_involved: list[str]
    total_nodes: int
    total_edges: int
    cross_file_edges: int
