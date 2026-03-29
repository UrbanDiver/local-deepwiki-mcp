"""Cross-file codemap generation with BFS traversal and narrative trace.

Given a user query, this module discovers relevant entry points via vector
search, builds a cross-file call graph via BFS, generates a deterministic
Mermaid flowchart, and uses an LLM to synthesize a narrative trace.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict, deque
from pathlib import Path

from local_deepwiki.core.path_utils import is_test_file
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore import VectorStore
    from local_deepwiki.providers.base import LLMProvider

from local_deepwiki.generators.codemap.graph import (
    _content_preview,
    _extract_param_names,
    _is_noise,
    _node_from_chunk,
    _PARAM_RE,
    build_cross_file_graph,
    discover_entry_points,
)
from local_deepwiki.generators.codemap.models import (
    BUILTIN_NAMES,
    CALLABLE_CHUNK_TYPES,
    CHUNK_TYPE_WEIGHTS,
    ENTRY_PATTERNS,
    CodemapEdge,
    CodemapFocus,
    CodemapGraph,
    CodemapNode,
    CodemapResult,
)
from local_deepwiki.generators.codemap.viz import generate_codemap_diagram
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType, CodeChunk

logger = get_logger(__name__)

# Backward-compatible aliases for private names that were previously
# module-level in this file.  External code (including tests) may
# reference them via ``codemap._ENTRY_PATTERNS`` etc.
_ENTRY_PATTERNS = ENTRY_PATTERNS
_BUILTIN_NAMES = BUILTIN_NAMES
_CALLABLE_CHUNK_TYPES = CALLABLE_CHUNK_TYPES
_CHUNK_TYPE_WEIGHTS = CHUNK_TYPE_WEIGHTS


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


def _format_node_lines(node: CodemapNode, full_mode: bool) -> list[str]:
    """Format a single node as prompt lines (full or truncated)."""
    header = (
        f"- {node.qualified_name} ({node.chunk_type}) "
        f"at {node.file_path}:{node.start_line}-{node.end_line}"
    )
    lines = [header]
    if full_mode:
        preview = node.content_preview or "(no preview)"
        lines.append(f"  Preview: {preview}")
        if node.docstring:
            lines.append(f"  Docstring: {node.docstring}")
    else:
        first_line = (node.content_preview or "").split("\n")[0]
        if first_line:
            lines.append(f"  Preview: {first_line}")
    return lines


def _build_narrative_prompt(
    graph: CodemapGraph,
    query: str,
    focus: CodemapFocus,
    ordered: list[CodemapNode],
) -> str:
    """Assemble the user prompt for narrative generation."""
    edge_lines = [f"  {e.source} --[{e.edge_type}]--> {e.target}" for e in graph.edges]

    header_parts: list[str] = [
        f"Query: {query}",
        f"Focus: {focus.value}",
        "",
        "Nodes (BFS order):",
    ]
    total_chars = sum(len(p) for p in header_parts) + sum(len(e) for e in edge_lines)
    full_mode = total_chars < 6000

    parts = list(header_parts)
    for node in ordered:
        parts.extend(_format_node_lines(node, full_mode))

    parts.append("")
    parts.append("Edges:")
    parts.extend(edge_lines)

    prompt = "\n".join(parts)
    if len(prompt) > 8000:
        prompt = prompt[:8000] + "\n...(truncated)"
    return prompt


async def generate_codemap_narrative(
    graph: CodemapGraph,
    query: str,
    focus: CodemapFocus,
    llm: "LLMProvider",
) -> str:
    """Use *llm* to synthesise a narrative trace for the codemap."""
    if not graph.nodes:
        return "No nodes in the graph to narrate."

    ordered = _bfs_ordered_nodes(graph)
    user_prompt = _build_narrative_prompt(graph, query, focus, ordered)
    system_prompt = (
        _DATA_FLOW_SYSTEM_PROMPT if focus == CodemapFocus.DATA_FLOW else _SYSTEM_PROMPT
    )

    try:
        return await llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.3,
        )
    except (ValueError, RuntimeError, OSError, TypeError):
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
    vector_store: "VectorStore",
    repo_path: Path,
    llm: "LLMProvider",
    *,
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

    diagram = generate_codemap_diagram(graph, focus, repo_path=repo)
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
                "docstring": n.docstring or "",
                "content_preview": n.content_preview or "",
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


def _is_test_path(file_path: str) -> bool:
    """Return ``True`` if *file_path* looks like a test/fixture file.

    Delegates to the centralized ``is_test_file`` utility.
    """
    return is_test_file(file_path)


def _build_combined_call_graph(
    files_to_chunks: dict[str, list[CodeChunk]],
    repo: Path,
) -> dict[str, list[str]]:
    """Build a merged call graph across all files in the repository."""
    from local_deepwiki.generators.analysis.callgraph import CallGraphExtractor

    extractor = CallGraphExtractor()
    combined_cg: dict[str, list[str]] = {}

    for file_path in files_to_chunks:
        abs_path = Path(file_path)
        if not abs_path.is_absolute():
            abs_path = repo / file_path
        try:
            cg = extractor.extract_from_file(abs_path, repo)
            combined_cg.update(cg)
        except (OSError, ValueError, RuntimeError):
            logger.debug(
                "Failed to extract call graph from %s", file_path, exc_info=True
            )
    return combined_cg


def _count_call_graph_connections(
    combined_cg: dict[str, list[str]],
) -> Counter[str]:
    """Count caller/callee mentions in the call graph, skipping noise."""
    connection_count: Counter[str] = Counter()
    for caller, callees in combined_cg.items():
        if _is_noise(caller):
            continue
        connection_count[caller] += len(callees)
        for callee in callees:
            if not _is_noise(callee):
                connection_count[callee] += 1
    return connection_count


def _apply_chunk_type_weights(
    connection_count: Counter[str],
    chunk_by_name: dict[str, CodeChunk],
) -> None:
    """Apply chunk-type weights to connection counts (in-place)."""
    for func_name in list(connection_count):
        chunk = chunk_by_name.get(func_name)
        if chunk:
            weight = CHUNK_TYPE_WEIGHTS.get(chunk.chunk_type.value, 1.0)
            connection_count[func_name] = int(connection_count[func_name] * weight)


def _build_file_import_count(all_chunks: list[CodeChunk]) -> Counter[str]:
    """Count how many times each module is imported across all import chunks."""
    file_import_count: Counter[str] = Counter()
    for chunk in all_chunks:
        if chunk.chunk_type != ChunkType.IMPORT:
            continue
        for line in chunk.content.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                match = re.match(r"(?:from\s+(\S+)|import\s+(\S+))", stripped)
                if match:
                    module = match.group(1) or match.group(2)
                    if module:
                        file_import_count[module] += 1
    return file_import_count


def _boost_by_import_popularity(
    connection_count: Counter[str],
    chunk_by_name: dict[str, CodeChunk],
    file_import_count: Counter[str],
    repo: Path,
) -> None:
    """Boost scores for functions in heavily-imported modules (in-place)."""
    for func_name in list(connection_count):
        chunk = chunk_by_name.get(func_name)
        if not chunk or not chunk.file_path:
            continue
        try:
            rel = str(Path(chunk.file_path).relative_to(repo))
        except (ValueError, TypeError):
            rel = chunk.file_path
        module = rel.rsplit(".", 1)[0].replace("/", ".").replace("\\", ".")
        if module in file_import_count:
            connection_count[func_name] += file_import_count[module]


def _rank_functions_by_connections(
    combined_cg: dict[str, list[str]],
    all_chunks: list[CodeChunk],
    chunk_by_name: dict[str, CodeChunk],
    repo: Path,
) -> Counter[str]:
    """Score every function by call-graph connections, chunk-type weight, and import popularity."""
    connection_count = _count_call_graph_connections(combined_cg)
    _apply_chunk_type_weights(connection_count, chunk_by_name)
    file_import_count = _build_file_import_count(all_chunks)
    _boost_by_import_popularity(
        connection_count, chunk_by_name, file_import_count, repo
    )
    return connection_count


def _format_topic_suggestions(
    ranked: list[tuple[str, int]],
    chunk_by_name: dict[str, CodeChunk],
    repo: Path,
    max_suggestions: int,
) -> list[dict[str, Any]]:
    """Convert ranked function list into topic suggestion dicts."""
    suggestions: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for func_name, count in ranked:
        if func_name in seen_names or _is_noise(func_name):
            continue
        seen_names.add(func_name)

        chunk = chunk_by_name.get(func_name)
        if chunk is None:
            continue

        file_path = chunk.file_path
        try:
            file_path = str(Path(file_path).relative_to(repo))
        except (ValueError, TypeError):
            pass

        if _is_test_path(file_path):
            continue

        is_entry = bool(ENTRY_PATTERNS.match(func_name.split(".")[-1]))
        reason = (
            f"Entry point with {count} connections"
            if is_entry
            else f"Hub function with {count} connections"
        )

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


async def suggest_topics(
    vector_store: "VectorStore",
    repo_path: Path,
    max_suggestions: int = 8,
) -> list[dict[str, Any]]:
    """Suggest interesting codemap topics based on call-graph hubs.

    Focuses on production source code -- test helpers and fixtures are
    excluded so that codemap pages document real execution flows.

    Returns a list of suggestion dicts sorted by connection count.
    """
    try:
        from local_deepwiki.generators.analysis.callgraph import CallGraphExtractor  # noqa: F401
    except ImportError:  # pragma: no cover
        logger.warning("Could not import CallGraphExtractor")
        return []

    repo = Path(repo_path)

    try:
        all_chunks = list(vector_store.get_all_chunks())
    except (OSError, ValueError, RuntimeError):
        logger.exception("Failed to retrieve chunks for topic suggestions")
        return []

    files_to_chunks: dict[str, list[CodeChunk]] = defaultdict(list)
    for chunk in all_chunks:
        files_to_chunks[chunk.file_path].append(chunk)

    combined_cg = _build_combined_call_graph(files_to_chunks, repo)

    # Index callable chunks by name, preferring production source over tests
    chunk_by_name: dict[str, CodeChunk] = {}
    for chunk in all_chunks:
        if chunk.chunk_type.value in CALLABLE_CHUNK_TYPES and chunk.name:
            key = chunk.name
            if chunk.parent_name:
                key = f"{chunk.parent_name}.{chunk.name}"
            existing = chunk_by_name.get(key)
            if existing is None:
                chunk_by_name[key] = chunk
            elif _is_test_path(existing.file_path) and not _is_test_path(
                chunk.file_path
            ):
                chunk_by_name[key] = chunk

    connection_count = _rank_functions_by_connections(
        combined_cg,
        all_chunks,
        chunk_by_name,
        repo,
    )

    return _format_topic_suggestions(
        connection_count.most_common(),
        chunk_by_name,
        repo,
        max_suggestions,
    )
