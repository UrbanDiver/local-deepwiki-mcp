"""BFS traversal and call resolution for cross-file codemap graphs.

Discovers entry points via vector search, resolves same-file and
cross-file call targets, and builds a ``CodemapGraph`` via BFS.
"""

from __future__ import annotations

import re
from collections import deque
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore import VectorStore

from local_deepwiki.core.path_utils import is_test_file
from local_deepwiki.core.query_utils import condense_query as _condense_query
from local_deepwiki.generators.codemap.models import (
    BUILTIN_NAMES,
    CALLABLE_CHUNK_TYPES,
    CHUNK_TYPE_WEIGHTS,
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


def _build_file_call_graphs(
    callable_results: list[Any],
    repo_path: Path,
    extractor: Any,
    max_files: int = 15,
) -> dict[str, dict[str, list[str]]]:
    """Build per-file call graphs for the top *max_files* unique files."""
    file_call_graphs: dict[str, dict[str, list[str]]] = {}
    seen_files: set[str] = set()
    for r in callable_results[:max_files]:
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
    return file_call_graphs


def _score_candidates(
    callable_results: list[Any],
    file_call_graphs: dict[str, dict[str, list[str]]],
    repo_path: Path,
) -> list[tuple[float, CodemapNode]]:
    """Score candidates by vector similarity, chunk type, and call-graph connectivity."""
    scored: list[tuple[float, CodemapNode]] = []
    for r in callable_results:
        node = _node_from_chunk(r.chunk, repo_path)
        score = r.score

        # Apply chunk-type weight — classes (often dataclasses/containers)
        # score lower than functions/methods (actual execution flows)
        score *= CHUNK_TYPE_WEIGHTS.get(
            r.chunk.chunk_type.value,
            1.0,
        )

        # Score by call-graph connectivity: functions that call many others
        # are more likely to be orchestrators worth tracing
        func_key = node.qualified_name
        short_name = node.name
        max_callees = 0
        for cg in file_call_graphs.values():
            if func_key in cg or short_name in cg:
                callees = cg.get(func_key, cg.get(short_name, []))
                max_callees = max(max_callees, len(callees))

        if max_callees >= 3:
            # Graduated boost: more callees = more likely an orchestrator
            score *= 1.0 + min(max_callees * 0.15, 1.5)
        elif max_callees == 0:
            # Leaf penalty — dataclasses and simple accessors produce
            # trivial graphs with no edges
            score *= 0.3
        elif max_callees == 1:
            # Mild penalty — single-callee nodes are unlikely orchestrators
            score *= 0.6

        # Boost for entry-pattern names
        if ENTRY_PATTERNS.match(node.name):
            score *= 1.3

        scored.append((score, node))

    return sorted(scored, key=itemgetter(0), reverse=True)


async def _run_fallback_search(
    search_query: str,
    vector_store: "VectorStore",
) -> list[object]:
    """Search for functions/methods when initial candidates are all shallow.

    Tries both the original *search_query* and a condensed technical variant.
    Results are deduplicated by ``file_path:name``.
    """
    queries = [search_query]
    condensed = _condense_query(search_query)
    if condensed != search_query:
        queries.append(condensed)

    fallback_results: list[Any] = []
    seen_chunk_ids: set[str] = set()
    for fallback_query in queries:
        for chunk_type in ("function", "method"):
            try:
                type_results = await vector_store.search(
                    fallback_query,
                    limit=15,
                    min_similarity=0.3,
                    chunk_type=chunk_type,
                )
                for r in type_results:
                    if is_test_file(r.chunk.file_path):
                        continue
                    seen_key = f"{r.chunk.file_path}:{r.chunk.name}"
                    if seen_key not in seen_chunk_ids:
                        seen_chunk_ids.add(seen_key)
                        fallback_results.append(r)
            except (OSError, ValueError, RuntimeError):
                logger.debug(
                    "Fallback search failed for query=%r chunk_type=%s",
                    fallback_query,
                    chunk_type,
                )
    return fallback_results


def _deduplicate_candidates(
    scored: list[tuple[float, CodemapNode]],
    extra: list[tuple[float, CodemapNode]],
) -> list[tuple[float, CodemapNode]]:
    """Merge *extra* into *scored*, dropping duplicates by ``qualified_name``."""
    seen_names = {node.qualified_name for _, node in scored}
    merged = list(scored)
    for fb_score, fb_node in extra:
        if fb_node.qualified_name not in seen_names:
            merged.append((fb_score, fb_node))
            seen_names.add(fb_node.qualified_name)
    return sorted(merged, key=itemgetter(0), reverse=True)


def _match_query_to_functions(
    callable_results: list[Any],
    entry_point_hint: str | None,
) -> list[Any]:
    """Narrow *callable_results* to name-matching entries when a hint is given.

    Args:
        callable_results: List of vector-search results with callable chunks.
        entry_point_hint: Optional hint string for name filtering.

    Returns:
        Filtered list (or original list if no hint or no exact matches found).
    """
    if not entry_point_hint:
        return callable_results
    exact = [
        r
        for r in callable_results
        if r.chunk.name and entry_point_hint.lower() in r.chunk.name.lower()
    ]
    return exact if exact else callable_results


def _load_call_graph_extractor() -> type | None:
    """Import and return the CallGraphExtractor class, or None on failure."""
    try:
        from local_deepwiki.generators.analysis.callgraph import (
            CallGraphExtractor,
        )

        return CallGraphExtractor
    except ImportError:  # pragma: no cover
        logger.warning("Could not import CallGraphExtractor")
        return None


async def _apply_fallback_search(
    search_query: str,
    scored: list[tuple[float, CodemapNode]],
    file_call_graphs: dict[str, dict[str, list[str]]],
    max_candidates: int,
    extractor: Any | None,
    repo_path: Path,
    vector_store: "VectorStore",
) -> list[tuple[float, CodemapNode]]:
    """Run fallback search and merge results when top candidates are all shallow."""
    top_candidates = scored[:max_candidates]
    all_shallow = all(
        _max_callees_for(node, file_call_graphs) <= 1 for _, node in top_candidates
    )
    if not all_shallow:
        return scored

    logger.debug(
        "All top candidates are shallow, running fallback search for functions and methods"
    )
    fallback_results = await _run_fallback_search(search_query, vector_store)
    if not fallback_results:
        return scored

    if extractor is not None:
        extra_graphs = _build_file_call_graphs(fallback_results, repo_path, extractor)
        file_call_graphs.update(extra_graphs)

    fallback_scored = _score_candidates(fallback_results, file_call_graphs, repo_path)
    return _deduplicate_candidates(scored, fallback_scored)


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

    When the initial search returns only leaf nodes (dataclasses/containers
    with no outgoing calls), a fallback search is performed filtering to
    functions and methods only to find actual pipeline orchestrators.
    """
    _CallGraphExtractor = _load_call_graph_extractor()
    extractor = _CallGraphExtractor() if _CallGraphExtractor is not None else None

    search_query = entry_point_hint if entry_point_hint else query
    try:
        results = await vector_store.search(search_query, limit=30, min_similarity=0.3)
    except (OSError, ValueError, RuntimeError):
        logger.exception("Vector search failed for entry point discovery")
        return []

    callable_results = [
        r
        for r in results
        if r.chunk.chunk_type.value in CALLABLE_CHUNK_TYPES
        and not is_test_file(r.chunk.file_path)
    ]
    callable_results = _match_query_to_functions(callable_results, entry_point_hint)

    if not callable_results:
        return []

    file_call_graphs: dict[str, dict[str, list[str]]] = {}
    if extractor is not None:
        file_call_graphs = _build_file_call_graphs(
            callable_results, repo_path, extractor
        )

    scored = _score_candidates(callable_results, file_call_graphs, repo_path)

    if not entry_point_hint:
        scored = await _apply_fallback_search(
            search_query,
            scored,
            file_call_graphs,
            max_candidates,
            extractor,
            repo_path,
            vector_store,
        )

    return [node for _, node in scored[:max_candidates]]


def _max_callees_for(
    node: CodemapNode,
    file_call_graphs: dict[str, dict[str, list[str]]],
) -> int:
    """Return the maximum callee count for *node* across all call graphs."""
    max_callees = 0
    for cg in file_call_graphs.values():
        if node.qualified_name in cg or node.name in cg:
            callees = cg.get(node.qualified_name, cg.get(node.name, []))
            max_callees = max(max_callees, len(callees))
    return max_callees


# ---------------------------------------------------------------------------
# 2. build_cross_file_graph
# ---------------------------------------------------------------------------


def _edge_type_for(focus: CodemapFocus, target_node: CodemapNode | None) -> str:
    """Compute edge label: ``"calls"`` or ``"passes(param, ...)"`` for data-flow."""
    if focus != CodemapFocus.DATA_FLOW or target_node is None:
        return "calls"
    params = _extract_param_names(target_node.content_preview)
    if params:
        return f"passes({', '.join(params)})"
    return "calls"


def _ensure_file_call_graph(
    file_key: str,
    abs_path: Path,
    repo_path: Path,
    extractor: Any | None,
    file_call_graphs: dict[str, dict[str, list[str]]],
) -> dict[str, list[str]]:
    """Lazily populate *file_call_graphs* for *file_key* and return the graph."""
    if file_key not in file_call_graphs and extractor is not None:
        try:
            file_call_graphs[file_key] = extractor.extract_from_file(
                abs_path, repo_path
            )
        except (OSError, ValueError, RuntimeError) as e:
            logger.debug("Could not extract call graph for %s: %s", file_key, e)
            file_call_graphs[file_key] = {}
    return file_call_graphs.get(file_key, {})


async def _resolve_cross_file_callee(
    callee_name: str,
    current_node: CodemapNode,
    depth: int,
    graph: CodemapGraph,
    queue: deque[tuple[CodemapNode, int]],
    vector_store: "VectorStore",
    repo_path: Path,
    focus: CodemapFocus,
) -> None:
    """Search the vector store for *callee_name* in another file and add to *graph*.

    Args:
        callee_name: The name of the callee to resolve cross-file.
        current_node: The BFS node currently being expanded.
        depth: Current BFS depth.
        graph: The codemap graph to update.
        queue: The BFS queue to append new nodes to.
        vector_store: Vector store for cross-file search.
        repo_path: Repository root path.
        focus: Traversal focus mode.
    """
    cross_node = await _search_cross_file(
        callee_name, vector_store, repo_path, current_node.file_path
    )
    if cross_node is not None and not is_test_file(cross_node.file_path):
        graph.nodes[cross_node.qualified_name] = cross_node
        graph.edges.append(
            CodemapEdge(
                source=current_node.qualified_name,
                target=cross_node.qualified_name,
                edge_type=_edge_type_for(focus, cross_node),
                source_file=current_node.file_path,
                target_file=cross_node.file_path,
            )
        )
        queue.append((cross_node, depth + 1))


async def _resolve_callees_for_node(
    current_node: CodemapNode,
    depth: int,
    graph: CodemapGraph,
    queue: deque[tuple[CodemapNode, int]],
    vector_store: "VectorStore",
    repo_path: Path,
    file_call_graphs: dict[str, dict[str, list[str]]],
    extractor: Any | None,
    focus: CodemapFocus,
    max_nodes: int,
) -> None:
    """Process a single BFS node: find callees and add edges/nodes to *graph*."""
    abs_path = Path(current_node.file_path)
    if not abs_path.is_absolute():
        abs_path = repo_path / current_node.file_path

    file_key = current_node.file_path
    cg = _ensure_file_call_graph(
        file_key, abs_path, repo_path, extractor, file_call_graphs
    )

    qn = current_node.qualified_name
    sn = current_node.name
    callees = list(cg.get(qn, cg.get(sn, [])))

    if focus == CodemapFocus.DEPENDENCY_CHAIN:
        callees = await _import_based_callees(
            current_node, vector_store, repo_path, callees
        )

    for callee_name in callees:
        if _is_noise(callee_name):
            continue
        if len(graph.nodes) >= max_nodes:
            break

        # Already tracked?
        if callee_name in graph.nodes:
            target_node = graph.nodes[callee_name]
            graph.edges.append(
                CodemapEdge(
                    source=current_node.qualified_name,
                    target=callee_name,
                    edge_type=_edge_type_for(focus, target_node),
                    source_file=current_node.file_path,
                    target_file=target_node.file_path,
                )
            )
            continue

        # Check same file first
        same_file_node = await _find_in_same_file(
            callee_name, cg, current_node, repo_path, vector_store
        )
        if same_file_node is not None and not is_test_file(same_file_node.file_path):
            graph.nodes[same_file_node.qualified_name] = same_file_node
            graph.edges.append(
                CodemapEdge(
                    source=current_node.qualified_name,
                    target=same_file_node.qualified_name,
                    edge_type=_edge_type_for(focus, same_file_node),
                    source_file=current_node.file_path,
                    target_file=same_file_node.file_path,
                )
            )
            queue.append((same_file_node, depth + 1))
            continue

        # Search vector store for cross-file definition
        await _resolve_cross_file_callee(
            callee_name,
            current_node,
            depth,
            graph,
            queue,
            vector_store,
            repo_path,
            focus,
        )


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
        if is_test_file(current_node.file_path):
            continue

        await _resolve_callees_for_node(
            current_node,
            depth,
            graph,
            queue,
            vector_store,
            repo_path,
            file_call_graphs,
            extractor,
            focus,
            max_nodes,
        )

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


def _match_function_by_name(
    callee_name: str,
    call_graph: dict[str, list[str]],
) -> str | None:
    """Return the call-graph key that matches *callee_name*, or ``None``.

    A function is "defined" in the same file if it appears as a caller key
    in the file's call graph (meaning tree-sitter found its definition).

    Args:
        callee_name: The short name to match.
        call_graph: The file-level call graph dict.

    Returns:
        The matching key (possibly qualified e.g. ``Class.method``) or None.
    """
    for key in call_graph:
        short = key.split(".")[-1]
        if short == callee_name or key == callee_name:
            return key
    return None


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
    matched_key = _match_function_by_name(callee_name, call_graph)
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
            results = await vector_store.search(query, limit=10, min_similarity=0.3)
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
            f"def {callee_name}", limit=5, min_similarity=0.3
        )
    except (OSError, ValueError, RuntimeError) as e:
        logger.debug("Cross-file search failed for %s: %s", callee_name, e)
        return None

    for r in results:
        chunk = r.chunk
        if chunk.chunk_type.value not in CALLABLE_CHUNK_TYPES:
            continue
        if is_test_file(chunk.file_path):
            continue
        if chunk.name and chunk.name.lower() == callee_name.lower():
            node = _node_from_chunk(chunk, repo_path)
            if node.file_path != source_file:
                return node
    return None
