"""Parameter objects for codemap generation.

Frozen dataclasses that bundle long parameter lists into cohesive
request/context objects shared by the codemap orchestration and graph
traversal modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from local_deepwiki.generators.codemap.models import CodemapFocus

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore import VectorStore
    from local_deepwiki.providers.base import LLMProvider


@dataclass(frozen=True, slots=True)
class CodemapRequest:
    """Bundles the parameters for a single ``generate_codemap`` invocation.

    Attributes:
        query: Natural-language query describing the flow to trace.
        vector_store: Vector store for semantic code search.
        repo_path: Repository root path.
        llm: LLM provider for narrative generation.
        entry_point: Optional explicit entry point hint.
        focus: Traversal focus mode (execution, data-flow, dependency).
        max_depth: Maximum BFS depth.
        max_nodes: Maximum nodes in the codemap graph.
    """

    query: str
    vector_store: "VectorStore"
    repo_path: Path
    llm: "LLMProvider"
    entry_point: str | None = None
    focus: CodemapFocus = CodemapFocus.EXECUTION_FLOW
    max_depth: int = 4
    max_nodes: int = 40


@dataclass(frozen=True, slots=True)
class GraphBuildContext:
    """Immutable context shared by BFS graph-building functions.

    Bundles the common parameters passed through ``build_cross_file_graph``,
    ``_resolve_callees_for_node``, ``_resolve_cross_file_callee``, and
    ``_apply_fallback_search``.

    Attributes:
        vector_store: Vector store for cross-file search.
        repo_path: Repository root path.
        focus: Traversal focus mode.
        max_nodes: Maximum nodes allowed in the graph.
        max_depth: Maximum BFS depth.
    """

    vector_store: "VectorStore"
    repo_path: Path
    focus: CodemapFocus = CodemapFocus.EXECUTION_FLOW
    max_nodes: int = 40
    max_depth: int = 4
