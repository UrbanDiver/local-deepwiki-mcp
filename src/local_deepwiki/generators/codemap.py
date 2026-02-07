"""Cross-file codemap generation with BFS traversal and narrative trace.

Given a user query, this module discovers relevant entry points via vector
search, builds a cross-file call graph via BFS, generates a deterministic
Mermaid flowchart, and uses an LLM to synthesize a narrative trace.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType, CodeChunk

logger = get_logger(__name__)

# Patterns that indicate entry-point functions
_ENTRY_PATTERNS = re.compile(
    r"^(main|handle_|run_|start_|cli_|route_|__main__|app\.|serve_|execute_|dispatch_)"
)

# Common builtins to skip during graph traversal
# fmt: off
_BUILTIN_NAMES = frozenset({
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

_CALLABLE_CHUNK_TYPES = frozenset(
    {
        ChunkType.FUNCTION.value,
        ChunkType.CLASS.value,
        ChunkType.METHOD.value,
    }
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class CodemapFocus(str, Enum):
    """Focus mode for codemap generation."""

    EXECUTION_FLOW = "execution_flow"
    DATA_FLOW = "data_flow"
    DEPENDENCY_CHAIN = "dependency_chain"


@dataclass(frozen=True)
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


@dataclass(frozen=True)
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
        pass

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
    return name.lower() in _BUILTIN_NAMES or len(name) <= 1


# Regex to extract parameter names from a function signature line.
# Matches `def foo(a, b, c):` or `function foo(a, b) {` style signatures.
_PARAM_RE = re.compile(r"(?:def|function|fn|func)\s+\w+\s*\(([^)]*)\)")


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
    vector_store: Any,
    repo_path: Path,
    entry_point_hint: str | None = None,
    max_candidates: int = 5,
) -> list[CodemapNode]:
    """Find the most relevant entry-point functions for *query*.

    If *entry_point_hint* is provided the vector store is searched for that
    specific name; otherwise a semantic search is performed and results are
    scored by relevance, entry-pattern matching, and call-graph root status.
    """
    try:
        from local_deepwiki.generators.callgraph import CallGraphExtractor
    except Exception:  # pragma: no cover
        logger.warning("Could not import CallGraphExtractor")
        CallGraphExtractor = None  # type: ignore[assignment,misc]

    search_query = entry_point_hint if entry_point_hint else query
    try:
        results = await vector_store.search(search_query, limit=20)
    except Exception:
        logger.exception("Vector search failed for entry point discovery")
        return []

    callable_results = [
        r for r in results if r.chunk.chunk_type.value in _CALLABLE_CHUNK_TYPES
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
    if CallGraphExtractor is not None:
        extractor = CallGraphExtractor()
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
            except Exception:
                pass

    # Compute all callees across discovered graphs to identify roots
    all_callees: set[str] = set()
    for cg in file_call_graphs.values():
        for callees in cg.values():
            all_callees.update(callees)

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
        if _ENTRY_PATTERNS.match(node.name):
            score *= 1.3

        scored.append((score, node))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [node for _, node in scored[:max_candidates]]


# ---------------------------------------------------------------------------
# 2. build_cross_file_graph
# ---------------------------------------------------------------------------


async def build_cross_file_graph(
    entry_nodes: list[CodemapNode],
    vector_store: Any,
    repo_path: Path,
    max_depth: int = 4,
    max_nodes: int = 40,
    focus: CodemapFocus = CodemapFocus.EXECUTION_FLOW,
) -> CodemapGraph:
    """BFS-traverse call relationships starting from *entry_nodes*.

    For ``DEPENDENCY_CHAIN`` focus the traversal follows import edges
    instead of call edges.
    """
    try:
        from local_deepwiki.generators.callgraph import CallGraphExtractor
    except Exception:  # pragma: no cover
        logger.warning("Could not import CallGraphExtractor")
        CallGraphExtractor = None  # type: ignore[assignment,misc]

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
    if CallGraphExtractor is not None:
        extractor = CallGraphExtractor()

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
            except Exception:
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
            same_file_node = _find_in_same_file(
                callee_name, cg, current_node, repo_path
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
    vector_store: Any,
    repo_path: Path,
    existing: list[str],
) -> list[str]:
    """Supplement *existing* callees with import-derived names."""
    try:
        from local_deepwiki.generators.context_builder import (
            extract_imports_from_chunks,
        )
    except Exception:
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
    except Exception:
        return existing


def _find_in_same_file(
    callee_name: str,
    call_graph: dict[str, list[str]],
    current_node: CodemapNode,
    repo_path: Path,
) -> CodemapNode | None:
    """Return a ``CodemapNode`` if *callee_name* is defined in the same file."""
    # A function is "defined" in the same file if it appears as a caller key
    # in the file's call graph (meaning tree-sitter found its definition).
    for key in call_graph:
        short = key.split(".")[-1]
        if short == callee_name or key == callee_name:
            return CodemapNode(
                name=callee_name,
                qualified_name=key,
                file_path=current_node.file_path,
                start_line=0,
                end_line=0,
                chunk_type="function",
            )
    return None


async def _search_cross_file(
    callee_name: str,
    vector_store: Any,
    repo_path: Path,
    source_file: str,
) -> CodemapNode | None:
    """Search the vector store for *callee_name* in a different file."""
    try:
        results = await vector_store.search(f"def {callee_name}", limit=5)
    except Exception:
        return None

    for r in results:
        chunk = r.chunk
        if chunk.chunk_type.value not in _CALLABLE_CHUNK_TYPES:
            continue
        if chunk.name and chunk.name.lower() == callee_name.lower():
            node = _node_from_chunk(chunk, repo_path)
            if node.file_path != source_file:
                return node
    return None


# ---------------------------------------------------------------------------
# 3. generate_codemap_diagram
# ---------------------------------------------------------------------------


def generate_codemap_diagram(graph: CodemapGraph, focus: CodemapFocus) -> str:
    """Generate a deterministic Mermaid flowchart from *graph*."""
    try:
        from local_deepwiki.generators.diagrams import sanitize_mermaid_name
    except Exception:  # pragma: no cover
        sanitize_mermaid_name = lambda n: re.sub(r"[^a-zA-Z0-9_]", "_", n)  # noqa: E731

    if not graph.nodes:
        return 'flowchart TD\n    empty["No code paths found for this query"]'

    # Deterministic ordering: sort nodes by (file, qualified_name)
    sorted_nodes = sorted(
        graph.nodes.values(), key=lambda n: (n.file_path, n.qualified_name)
    )

    # Assign stable IDs
    node_ids: dict[str, str] = {}
    for idx, node in enumerate(sorted_nodes):
        node_ids[node.qualified_name] = f"N{idx}"

    # Group by file
    files_to_nodes: dict[str, list[CodemapNode]] = defaultdict(list)
    for node in sorted_nodes:
        files_to_nodes[node.file_path].append(node)

    # Determine node classes
    cross_file_targets: set[str] = {
        e.target for e in graph.edges if e.source_file != e.target_file
    }
    nodes_with_outgoing: set[str] = {e.source for e in graph.edges}

    lines: list[str] = ["flowchart TD"]

    for file_path in sorted(files_to_nodes):
        safe_subgraph = sanitize_mermaid_name(file_path)
        lines.append(f'    subgraph {safe_subgraph}["{file_path}"]')
        for node in files_to_nodes[file_path]:
            nid = node_ids[node.qualified_name]
            label = f"{node.name}\\n:{node.start_line}-{node.end_line}"
            lines.append(f'        {nid}["{label}"]')
        lines.append("    end")

    # Edges (sorted for determinism)
    sorted_edges = sorted(
        graph.edges,
        key=lambda e: (e.source, e.target),
    )
    seen_edges: set[tuple[str, str]] = set()
    for edge in sorted_edges:
        src_id = node_ids.get(edge.source)
        tgt_id = node_ids.get(edge.target)
        if src_id is None or tgt_id is None:
            continue
        pair = (src_id, tgt_id)
        if pair in seen_edges:
            continue
        seen_edges.add(pair)
        arrow = "-.->" if edge.source_file != edge.target_file else "-->"
        if focus == CodemapFocus.DATA_FLOW and edge.edge_type != "calls":
            safe_label = edge.edge_type.replace('"', "'")
            lines.append(f'    {src_id} {arrow}|"{safe_label}"| {tgt_id}')
        else:
            lines.append(f"    {src_id} {arrow} {tgt_id}")

    # Class definitions
    lines.append("")
    lines.append("    classDef entry fill:#2d6a4f,color:#fff")
    lines.append("    classDef crossfile fill:#1d3557,color:#fff")
    lines.append("    classDef leaf fill:#6c757d,color:#fff")

    # Apply classes
    if graph.entry_point and graph.entry_point in node_ids:
        lines.append(f"    class {node_ids[graph.entry_point]} entry")

    crossfile_ids = [
        node_ids[qn]
        for qn in cross_file_targets
        if qn in node_ids and qn != graph.entry_point
    ]
    if crossfile_ids:
        lines.append(f"    class {','.join(sorted(crossfile_ids))} crossfile")

    leaf_ids = [
        node_ids[n.qualified_name]
        for n in sorted_nodes
        if n.qualified_name not in nodes_with_outgoing
        and n.qualified_name != graph.entry_point
        and n.qualified_name not in cross_file_targets
    ]
    if leaf_ids:
        lines.append(f"    class {','.join(sorted(leaf_ids))} leaf")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. generate_codemap_narrative
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a code architecture expert. Given a code execution graph, produce a \
clear narrative trace explaining how the code works. Format your response as:

## Summary
One paragraph overview of what this code flow does.

## Execution Trace
Numbered steps, each with:
- The function/method name and its file location (e.g., `core/indexer.py:42`)
- What it does (1-2 sentences)
- What it calls next and why

## Key Observations
2-3 bullet points about design patterns, error handling, or notable decisions."""

_DATA_FLOW_SYSTEM_PROMPT = """\
You are a code architecture expert specializing in data flow analysis. Given a \
code graph with parameter annotations on edges, produce a narrative trace that \
focuses on how data is transformed and passed between functions. Format your \
response as:

## Summary
One paragraph overview of what data flows through this code and how it is transformed.

## Data Flow Trace
Numbered steps, each with:
- The function/method name and its file location (e.g., `core/indexer.py:42`)
- What data it receives (parameter names and their purpose)
- How it transforms the data (1-2 sentences)
- What data it passes to the next function and why

## Key Observations
2-3 bullet points about data transformation patterns, immutability, or notable \
design decisions around data handling."""

_FALLBACK_NARRATIVE = (
    "Narrative generation failed. See the Mermaid diagram above for the code flow."
)


async def generate_codemap_narrative(
    graph: CodemapGraph,
    query: str,
    focus: CodemapFocus,
    llm: Any,
) -> str:
    """Use *llm* to synthesise a narrative trace for the codemap."""
    if not graph.nodes:
        return "No nodes in the graph to narrate."

    # Build BFS-ordered node list (entry point first, then BFS order)
    ordered = _bfs_ordered_nodes(graph)

    # Assemble user prompt parts
    parts: list[str] = [
        f"Query: {query}",
        f"Focus: {focus.value}",
        "",
        "Nodes (BFS order):",
    ]
    edge_lines = [f"  {e.source} --[{e.edge_type}]--> {e.target}" for e in graph.edges]

    total_chars = sum(len(p) for p in parts) + sum(len(e) for e in edge_lines)

    # Decide truncation level
    full_mode = total_chars < 6000

    for node in ordered:
        header = (
            f"- {node.qualified_name} ({node.chunk_type}) "
            f"at {node.file_path}:{node.start_line}-{node.end_line}"
        )
        if full_mode:
            preview = node.content_preview or "(no preview)"
            doc = f"  Docstring: {node.docstring}" if node.docstring else ""
            parts.append(header)
            parts.append(f"  Preview: {preview}")
            if doc:
                parts.append(doc)
        else:
            # Truncated: first line of preview only, no docstring
            first_line = (node.content_preview or "").split("\n")[0]
            parts.append(header)
            if first_line:
                parts.append(f"  Preview: {first_line}")

    parts.append("")
    parts.append("Edges:")
    parts.extend(edge_lines)

    user_prompt = "\n".join(parts)

    # Final truncation guard
    if len(user_prompt) > 8000:
        user_prompt = user_prompt[:8000] + "\n...(truncated)"

    system_prompt = (
        _DATA_FLOW_SYSTEM_PROMPT if focus == CodemapFocus.DATA_FLOW else _SYSTEM_PROMPT
    )

    try:
        narrative = await llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.3,
        )
        return narrative
    except Exception:
        logger.exception("LLM narrative generation failed")
        return _FALLBACK_NARRATIVE


def _bfs_ordered_nodes(graph: CodemapGraph) -> list[CodemapNode]:
    """Return nodes in BFS order starting from the entry point."""
    if not graph.entry_point or graph.entry_point not in graph.nodes:
        return sorted(graph.nodes.values(), key=lambda n: n.qualified_name)

    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        adjacency[edge.source].append(edge.target)

    visited: set[str] = set()
    ordered: list[CodemapNode] = []
    queue: deque[str] = deque([graph.entry_point])
    visited.add(graph.entry_point)

    while queue:
        qn = queue.popleft()
        if qn in graph.nodes:
            ordered.append(graph.nodes[qn])
        for neighbour in adjacency.get(qn, []):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)

    # Append any nodes not reachable from entry (shouldn't happen, but safe)
    for qn in sorted(graph.nodes):
        if qn not in visited:
            ordered.append(graph.nodes[qn])

    return ordered


# ---------------------------------------------------------------------------
# 5. generate_codemap (orchestrator)
# ---------------------------------------------------------------------------


async def generate_codemap(
    query: str,
    vector_store: Any,
    repo_path: Path,
    llm: Any,
    entry_point: str | None = None,
    focus: CodemapFocus = CodemapFocus.EXECUTION_FLOW,
    max_depth: int = 4,
    max_nodes: int = 40,
) -> CodemapResult:
    """Main entry point: build a codemap for *query* and return a full result."""
    repo = Path(repo_path)

    entry_nodes = await discover_entry_points(
        query, vector_store, repo, entry_point_hint=entry_point, max_candidates=3
    )

    if not entry_nodes:
        empty_diagram = 'flowchart TD\n    empty["No code paths found for this query"]'
        return CodemapResult(
            query=query,
            focus=focus.value,
            entry_point=None,
            mermaid_diagram=empty_diagram,
            narrative="No relevant entry points found for the given query.",
            nodes=[],
            edges=[],
            files_involved=[],
            total_nodes=0,
            total_edges=0,
            cross_file_edges=0,
        )

    graph = await build_cross_file_graph(
        entry_nodes,
        vector_store,
        repo,
        max_depth=max_depth,
        max_nodes=max_nodes,
        focus=focus,
    )

    diagram = generate_codemap_diagram(graph, focus)
    narrative = await generate_codemap_narrative(graph, query, focus, llm)

    return CodemapResult(
        query=query,
        focus=focus.value,
        entry_point=graph.entry_point,
        mermaid_diagram=diagram,
        narrative=narrative,
        nodes=[
            {
                "name": n.name,
                "qualified_name": n.qualified_name,
                "file_path": n.file_path,
                "start_line": n.start_line,
                "end_line": n.end_line,
                "chunk_type": n.chunk_type,
            }
            for n in sorted(graph.nodes.values(), key=lambda n: n.qualified_name)
        ],
        edges=[
            {
                "source": e.source,
                "target": e.target,
                "edge_type": e.edge_type,
                "source_file": e.source_file,
                "target_file": e.target_file,
            }
            for e in graph.edges
        ],
        files_involved=sorted(graph.files_involved),
        total_nodes=len(graph.nodes),
        total_edges=len(graph.edges),
        cross_file_edges=len(graph.cross_file_edges),
    )


# ---------------------------------------------------------------------------
# 6. suggest_topics
# ---------------------------------------------------------------------------


async def suggest_topics(
    vector_store: Any,
    repo_path: Path,
    max_suggestions: int = 8,
) -> list[dict[str, Any]]:
    """Suggest interesting codemap topics based on call-graph hubs.

    Returns a list of suggestion dicts sorted by connection count.
    """
    try:
        from local_deepwiki.generators.callgraph import CallGraphExtractor
    except Exception:  # pragma: no cover
        logger.warning("Could not import CallGraphExtractor")
        return []

    repo = Path(repo_path)

    # Gather all callable chunks
    try:
        all_chunks = list(vector_store.get_all_chunks())
    except Exception:
        logger.exception("Failed to retrieve chunks for topic suggestions")
        return []

    # Group chunks by file for call-graph extraction
    files_to_chunks: dict[str, list[CodeChunk]] = defaultdict(list)
    for chunk in all_chunks:
        files_to_chunks[chunk.file_path].append(chunk)

    # Build combined call graph across all files
    extractor = CallGraphExtractor()
    combined_cg: dict[str, list[str]] = {}
    chunk_by_name: dict[str, CodeChunk] = {}

    for file_path in files_to_chunks:
        abs_path = Path(file_path)
        if not abs_path.is_absolute():
            abs_path = repo / file_path
        try:
            cg = extractor.extract_from_file(abs_path, repo)
            combined_cg.update(cg)
        except Exception:
            continue

    # Index callable chunks by name for quick lookup
    for chunk in all_chunks:
        if chunk.chunk_type.value in _CALLABLE_CHUNK_TYPES and chunk.name:
            key = chunk.name
            if chunk.parent_name:
                key = f"{chunk.parent_name}.{chunk.name}"
            chunk_by_name[key] = chunk

    # Count connections per function (skip noise/builtins for accurate ranking)
    connection_count: dict[str, int] = defaultdict(int)
    for caller, callees in combined_cg.items():
        if _is_noise(caller):
            continue
        connection_count[caller] += len(callees)
        for callee in callees:
            if not _is_noise(callee):
                connection_count[callee] += 1

    # Also count how many files import each file (core module detection)
    file_import_count: dict[str, int] = defaultdict(int)
    for chunk in all_chunks:
        if chunk.chunk_type == ChunkType.IMPORT:
            for line in chunk.content.splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    # Extract module path
                    match = re.match(r"(?:from\s+(\S+)|import\s+(\S+))", stripped)
                    if match:
                        module = match.group(1) or match.group(2)
                        if module:
                            file_import_count[module] += 1

    # Boost score for functions in heavily-imported modules
    for func_name in list(connection_count):
        chunk = chunk_by_name.get(func_name)
        if chunk and chunk.file_path:
            # Convert file path to dotted module name for matching
            try:
                rel = str(Path(chunk.file_path).relative_to(repo))
            except (ValueError, TypeError):
                rel = chunk.file_path
            # Strip extension and convert separators to dots
            module = rel.rsplit(".", 1)[0].replace("/", ".").replace("\\", ".")
            if module in file_import_count:
                connection_count[func_name] += file_import_count[module]

    # Build suggestions from hubs and entry patterns
    suggestions: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    # Sort by connection count
    ranked = sorted(connection_count.items(), key=lambda t: t[1], reverse=True)

    for func_name, count in ranked:
        if func_name in seen_names:
            continue
        if _is_noise(func_name):
            continue
        seen_names.add(func_name)

        chunk = chunk_by_name.get(func_name)
        if chunk is None:
            continue  # Skip stdlib/external entities without indexed source
        file_path = chunk.file_path
        try:
            file_path = str(Path(file_path).relative_to(repo))
        except (ValueError, TypeError):
            pass

        is_entry = bool(_ENTRY_PATTERNS.match(func_name.split(".")[-1]))
        reason = f"Hub function with {count} connections"
        if is_entry:
            reason = f"Entry point with {count} connections"

        display_name = func_name.replace("_", " ").replace(".", " ")
        suggestions.append(
            {
                "topic": f"How {display_name} works",
                "entry_point": func_name,
                "file_path": file_path,
                "reason": reason,
                "suggested_query": f"How does {func_name} work?",
            }
        )

        if len(suggestions) >= max_suggestions:
            break

    return suggestions
