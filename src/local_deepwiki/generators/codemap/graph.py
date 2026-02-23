"""BFS traversal and call resolution for cross-file codemap graphs.

Discovers entry points via vector search, resolves same-file and
cross-file call targets, and builds a ``CodemapGraph`` via BFS.
"""

from __future__ import annotations

import re
from collections import deque
from itertools import chain
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore import VectorStore

from local_deepwiki.generators.codemap.models import (
    BUILTIN_NAMES,
    CALLABLE_CHUNK_TYPES,
    ENTRY_PATTERNS,
    CodemapEdge,
    CodemapFocus,
    CodemapGraph,
    CodemapNode,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType, CodeChunk

logger = get_logger(__name__)

# Regex to extract parameter names from a function signature line.
# Matches `def foo(a, b, c):` or `function foo(a, b) {` style signatures.
_PARAM_RE = re.compile(r"(?:def|function|fn|func)\s+\w+\s*\(([^)]*)\)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_preview(content: str, max_lines: int = 3) -> str:
    """Return the first *max_lines* non-blank lines of *content*."""
    lines: list[str] = []
    for raw in content.splitlines():
        stripped = raw.strip()
        if stripped:
            lines.append(stripped)
            if len(lines) >= max_lines:
                break
    return "\n".join(lines)


def _node_from_chunk(chunk: CodeChunk, repo_path: Path) -> CodemapNode:
    """Build a ``CodemapNode`` from a ``CodeChunk``."""
    qualified = chunk.name or "unknown"
    if chunk.parent_name:
        qualified = f"{chunk.parent_name}.{chunk.name}"

    rel_path = chunk.file_path
    try:
        rel_path = str(Path(chunk.file_path).relative_to(repo_path))
    except ValueError:
        logger.debug(
            "Failed to compute relative path for %s", chunk.file_path, exc_info=True
        )

    return CodemapNode(
        name=chunk.name or "unknown",
        qualified_name=qualified,
        file_path=rel_path,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        chunk_type=chunk.chunk_type.value,
        docstring=chunk.docstring,
        content_preview=_content_preview(chunk.content),
    )


def _is_noise(name: str) -> bool:
    """Return ``True`` if *name* should be skipped during traversal."""
    return name.lower() in BUILTIN_NAMES or len(name) <= 1


def _extract_param_names(content: str) -> list[str]:
    """Extract parameter names from the first function signature in *content*.

    Returns a list of bare parameter names (no type annotations or defaults).
    """
    for line in content.splitlines():
        m = _PARAM_RE.search(line)
        if m:
            raw = m.group(1)
            params: list[str] = []
            for part in raw.split(","):
                part = part.strip()
                if not part:
                    continue
                # Strip type annotations (Python: `name: Type`, TS: `name: Type`)
                name = part.split(":")[0].split("=")[0].strip()
                # Strip leading `self`, `cls`, `*`, `**`
                name = name.lstrip("*")
                if name and name not in ("self", "cls"):
                    params.append(name)
            return params
    return []


# ---------------------------------------------------------------------------
# 1. discover_entry_points
# ---------------------------------------------------------------------------


async def discover_entry_points(
    query: str,
    vector_store: "VectorStore",
    repo_path: Path,
    *,
    entry_point_hint: str | None = None,
    max_candidates: int = 5,
) -> list[CodemapNode]:
    """Find the most relevant entry-point functions for *query*.

    If *entry_point_hint* is provided the vector store is searched for that
    specific name; otherwise a semantic search is performed and results are
    scored by relevance, entry-pattern matching, and call-graph root status.
    """
    _CallGraphExtractor: type | None
    try:
        from local_deepwiki.generators.analysis.callgraph import (
            CallGraphExtractor as _CallGraphExtractor,
        )
    except ImportError:  # pragma: no cover
        logger.warning("Could not import CallGraphExtractor")
        _CallGraphExtractor = None  # fallback if callgraph module unavailable

    search_query = entry_point_hint if entry_point_hint else query
    try:
        results = await vector_store.search(search_query, limit=20, min_similarity=0.0)
    except (OSError, ValueError, RuntimeError):
        logger.exception("Vector search failed for entry point discovery")
        return []

    callable_results = [
        r for r in results if r.chunk.chunk_type.value in CALLABLE_CHUNK_TYPES
    ]

    if entry_point_hint:
        # Narrow to exact or close name matches
        exact = [
            r
            for r in callable_results
            if r.chunk.name and entry_point_hint.lower() in r.chunk.name.lower()
        ]
        if exact:
            callable_results = exact

    if not callable_results:
        return []

    # Build per-file call graphs for scoring (root detection)
    file_call_graphs: dict[str, dict[str, list[str]]] = {}
    if _CallGraphExtractor is not None:
        extractor = _CallGraphExtractor()
        seen_files: set[str] = set()
        for r in callable_results[:10]:
            fp = r.chunk.file_path
            if fp in seen_files:
                continue
            seen_files.add(fp)
            try:
                abs_path = Path(fp)
                if not abs_path.is_absolute():
                    abs_path = repo_path / fp
                cg = extractor.extract_from_file(abs_path, repo_path)
                file_call_graphs[fp] = cg
            except (OSError, ValueError, RuntimeError) as e:
                logger.debug("Could not extract call graph from %s: %s", fp, e)

    # Compute all callees across discovered graphs to identify roots
    all_callees: set[str] = set()
    for cg in file_call_graphs.values():
        all_callees.update(chain.from_iterable(cg.values()))

    scored: list[tuple[float, CodemapNode]] = []
    for r in callable_results:
        node = _node_from_chunk(r.chunk, repo_path)
        score = r.score

        # Boost if the function is a call-graph root (called by others, or
        # itself calls many functions)
        func_key = node.qualified_name
        short_name = node.name
        is_root = False
        for cg in file_call_graphs.values():
            if func_key in cg or short_name in cg:
                callees = cg.get(func_key, cg.get(short_name, []))
                if len(callees) >= 2:
                    is_root = True
                    break
        if is_root:
            score *= 1.5

        # Boost for entry-pattern names
        if ENTRY_PATTERNS.match(node.name):
            score *= 1.3

        scored.append((score, node))

    scored = sorted(scored, key=itemgetter(0), reverse=True)
    return [node for _, node in scored[:max_candidates]]


# ---------------------------------------------------------------------------
# 2. build_cross_file_graph
# ---------------------------------------------------------------------------


async def build_cross_file_graph(
    entry_nodes: list[CodemapNode],
    vector_store: "VectorStore",
    repo_path: Path,
    *,
    max_depth: int = 4,
    max_nodes: int = 40,
    focus: CodemapFocus = CodemapFocus.EXECUTION_FLOW,
) -> CodemapGraph:
    """BFS-traverse call relationships starting from *entry_nodes*.

    For ``DEPENDENCY_CHAIN`` focus the traversal follows import edges
    instead of call edges.
    """
    _CGExtractor: type | None
    try:
        from local_deepwiki.generators.analysis.callgraph import (
            CallGraphExtractor as _CGExtractor,
        )
    except ImportError:  # pragma: no cover
        logger.warning("Could not import CallGraphExtractor")
        _CGExtractor = None  # fallback if callgraph module unavailable

    graph = CodemapGraph()

    if not entry_nodes:
        return graph

    graph.entry_point = entry_nodes[0].qualified_name

    # Seed the BFS queue: (node, depth)
    queue: deque[tuple[CodemapNode, int]] = deque()
    for node in entry_nodes:
        graph.nodes[node.qualified_name] = node
        queue.append((node, 0))

    # Cache file-level call graphs so we parse each file at most once
    file_call_graphs: dict[str, dict[str, list[str]]] = {}

    extractor = None
    if _CGExtractor is not None:
        extractor = _CGExtractor()

    while queue and len(graph.nodes) < max_nodes:
        current_node, depth = queue.popleft()
        if depth >= max_depth:
            continue

        abs_path = Path(current_node.file_path)
        if not abs_path.is_absolute():
            abs_path = repo_path / current_node.file_path

        # Retrieve call graph for the current file
        file_key = current_node.file_path
        if file_key not in file_call_graphs and extractor is not None:
            try:
                file_call_graphs[file_key] = extractor.extract_from_file(
                    abs_path, repo_path
                )
            except (OSError, ValueError, RuntimeError) as e:
                logger.debug("Could not extract call graph for %s: %s", file_key, e)
                file_call_graphs[file_key] = {}

        cg = file_call_graphs.get(file_key, {})

        # Determine callees for the current function
        callees: list[str] = []
        qn = current_node.qualified_name
        sn = current_node.name
        callees = list(cg.get(qn, cg.get(sn, [])))

        if focus == CodemapFocus.DEPENDENCY_CHAIN:
            # Supplement with import-based edges
            callees = await _import_based_callees(
                current_node, vector_store, repo_path, callees
            )

        for callee_name in callees:
            if _is_noise(callee_name):
                continue
            if len(graph.nodes) >= max_nodes:
                break

            # For DATA_FLOW, compute a descriptive edge type from the
            # target function's parameter signature.
            def _edge_type_for(target_node: CodemapNode | None) -> str:
                if focus != CodemapFocus.DATA_FLOW or target_node is None:
                    return "calls"
                params = _extract_param_names(target_node.content_preview)
                if params:
                    return f"passes({', '.join(params)})"
                return "calls"

            # Already tracked?
            if callee_name in graph.nodes:
                target_node = graph.nodes[callee_name]
                graph.edges.append(
                    CodemapEdge(
                        source=current_node.qualified_name,
                        target=callee_name,
                        edge_type=_edge_type_for(target_node),
                        source_file=current_node.file_path,
                        target_file=target_node.file_path,
                    )
                )
                continue

            # Check same file first
            same_file_node = await _find_in_same_file(
                callee_name, cg, current_node, repo_path, vector_store
            )
            if same_file_node is not None:
                graph.nodes[same_file_node.qualified_name] = same_file_node
                graph.edges.append(
                    CodemapEdge(
                        source=current_node.qualified_name,
                        target=same_file_node.qualified_name,
                        edge_type=_edge_type_for(same_file_node),
                        source_file=current_node.file_path,
                        target_file=same_file_node.file_path,
                    )
                )
                queue.append((same_file_node, depth + 1))
                continue

            # Search vector store for cross-file definition
            cross_node = await _search_cross_file(
                callee_name, vector_store, repo_path, current_node.file_path
            )
            if cross_node is not None:
                graph.nodes[cross_node.qualified_name] = cross_node
                graph.edges.append(
                    CodemapEdge(
                        source=current_node.qualified_name,
                        target=cross_node.qualified_name,
                        edge_type=_edge_type_for(cross_node),
                        source_file=current_node.file_path,
                        target_file=cross_node.file_path,
                    )
                )
                queue.append((cross_node, depth + 1))

    return graph


async def _import_based_callees(
    node: CodemapNode,
    vector_store: "VectorStore",
    repo_path: Path,
    existing: list[str],
) -> list[str]:
    """Supplement *existing* callees with import-derived names."""
    try:
        from local_deepwiki.generators.context_builder import (
            extract_imports_from_chunks,
        )
    except ImportError:
        return existing

    try:
        chunks = [
            c
            for c in vector_store.get_all_chunks()
            if c.file_path.endswith(node.file_path) and c.chunk_type == ChunkType.IMPORT
        ]
        _, modules = extract_imports_from_chunks(chunks)
        combined = list(existing)
        for mod in modules:
            if mod not in combined:
                combined.append(mod)
        return combined
    except (AttributeError, ValueError, RuntimeError, OSError):
        # AttributeError: vector_store missing get_all_chunks method
        # ValueError/RuntimeError: chunk processing or import extraction failures
        # OSError: underlying storage I/O errors
        return existing


async def _find_in_same_file(
    callee_name: str,
    call_graph: dict[str, list[str]],
    current_node: CodemapNode,
    repo_path: Path,
    vector_store: "VectorStore",
) -> CodemapNode | None:
    """Return a ``CodemapNode`` if *callee_name* is defined in the same file.

    First confirms the callee exists via the call graph, then searches the
    vector store for the matching chunk so that ``content_preview``,
    ``start_line``, ``end_line``, and ``docstring`` are populated.
    """
    # A function is "defined" in the same file if it appears as a caller key
    # in the file's call graph (meaning tree-sitter found its definition).
    matched_key: str | None = None
    for key in call_graph:
        short = key.split(".")[-1]
        if short == callee_name or key == callee_name:
            matched_key = key
            break

    if matched_key is None:
        return None

    # Try to find the actual chunk from the vector store for full metadata.
    # Search with both the short name and the qualified name (for class
    # methods the qualified form like "WikiGenerator._init_context" gives
    # a much better semantic match than just "def _init_context").
    queries = [f"def {callee_name}"]
    if matched_key != callee_name:
        queries.append(matched_key)

    try:
        for query in queries:
            results = await vector_store.search(query, limit=10, min_similarity=0.0)
            for r in results:
                chunk = r.chunk
                if chunk.chunk_type.value not in CALLABLE_CHUNK_TYPES:
                    continue
                if chunk.name and chunk.name.lower() == callee_name.lower():
                    node = _node_from_chunk(chunk, repo_path)
                    if node.file_path == current_node.file_path:
                        return node
    except (OSError, ValueError, RuntimeError) as e:
        logger.debug("Same-file chunk lookup failed for %s: %s", callee_name, e)

    # Fallback: return a skeleton node when the vector store has no match.
    return CodemapNode(
        name=callee_name,
        qualified_name=matched_key,
        file_path=current_node.file_path,
        start_line=0,
        end_line=0,
        chunk_type="function",
    )


async def _search_cross_file(
    callee_name: str,
    vector_store: "VectorStore",
    repo_path: Path,
    source_file: str,
) -> CodemapNode | None:
    """Search the vector store for *callee_name* in a different file."""
    try:
        results = await vector_store.search(
            f"def {callee_name}", limit=5, min_similarity=0.0
        )
    except (OSError, ValueError, RuntimeError) as e:
        logger.debug("Cross-file search failed for %s: %s", callee_name, e)
        return None

    for r in results:
        chunk = r.chunk
        if chunk.chunk_type.value not in CALLABLE_CHUNK_TYPES:
            continue
        if chunk.name and chunk.name.lower() == callee_name.lower():
            node = _node_from_chunk(chunk, repo_path)
            if node.file_path != source_file:
                return node
    return None
