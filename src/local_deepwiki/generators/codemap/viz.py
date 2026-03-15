"""Mermaid diagram generation for codemap graphs.

Produces deterministic Mermaid flowcharts from ``CodemapGraph`` instances,
with subgraphs per file, color-coded node classes (entry/cross-file/leaf),
and optional click handlers for source navigation.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Callable

from local_deepwiki.generators.codemap.models import (
    CodemapFocus,
    CodemapGraph,
    CodemapNode,
)


def _build_subgraphs(
    sorted_nodes: list[CodemapNode],
    node_ids: dict[str, str],
    sanitize: Callable[[str], str],
) -> list[str]:
    """Group nodes by file and generate Mermaid subgraph blocks."""
    files_to_nodes: dict[str, list[CodemapNode]] = defaultdict(list)
    for node in sorted_nodes:
        files_to_nodes[node.file_path].append(node)

    lines: list[str] = []
    for file_path in sorted(files_to_nodes):
        safe_subgraph = sanitize(file_path)
        lines.append(f'    subgraph {safe_subgraph}["{file_path}"]')
        for node in files_to_nodes[file_path]:
            nid = node_ids[node.qualified_name]
            label = f"{node.name}\\n:{node.start_line}-{node.end_line}"
            lines.append(f'        {nid}["{label}"]')
        lines.append("    end")
    return lines


def _render_edges(
    graph: CodemapGraph,
    node_ids: dict[str, str],
    focus: CodemapFocus,
) -> list[str]:
    """Deduplicate edges, choose arrow style, and add labels."""
    sorted_edges = sorted(
        graph.edges,
        key=lambda e: (e.source, e.target),
    )
    lines: list[str] = []
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
    return lines


def _apply_node_classes(
    graph: CodemapGraph,
    sorted_nodes: list[CodemapNode],
    node_ids: dict[str, str],
) -> list[str]:
    """Generate classDef and class assignment lines for entry/crossfile/leaf nodes."""
    cross_file_targets: set[str] = {
        e.target for e in graph.edges if e.source_file != e.target_file
    }
    nodes_with_outgoing: set[str] = {e.source for e in graph.edges}

    lines: list[str] = [
        "",
        "    classDef entry fill:#2d6a4f,color:#fff",
        "    classDef crossfile fill:#1d3557,color:#fff",
        "    classDef leaf fill:#6c757d,color:#fff",
    ]

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

    return lines


def _build_click_handlers(
    sorted_nodes: list[CodemapNode],
    node_ids: dict[str, str],
    repo_path: Path | None,
) -> list[str]:
    """Generate click handler lines for source navigation."""
    if repo_path is None:
        return []

    lines: list[str] = []
    for node in sorted_nodes:
        nid = node_ids[node.qualified_name]
        try:
            rel = str(Path(node.file_path).relative_to(repo_path))
        except (ValueError, TypeError):
            rel = node.file_path
        lines.append(f'    click {nid} "files/{rel}" _blank')
    return lines


def generate_codemap_diagram(
    graph: CodemapGraph, focus: CodemapFocus, repo_path: Path | None = None
) -> str:
    """Generate a deterministic Mermaid flowchart from *graph*."""
    try:
        from local_deepwiki.generators.diagrams import (
            sanitize_mermaid_name as _sanitize,
        )
    except ImportError:  # pragma: no cover

        def _sanitize(name: str) -> str:
            return re.sub(r"[^a-zA-Z0-9_]", "_", name)

    sanitize_mermaid_name = _sanitize

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

    lines: list[str] = ["flowchart TD"]
    lines.extend(_build_subgraphs(sorted_nodes, node_ids, sanitize_mermaid_name))
    lines.extend(_render_edges(graph, node_ids, focus))
    lines.extend(_apply_node_classes(graph, sorted_nodes, node_ids))
    lines.extend(_build_click_handlers(sorted_nodes, node_ids, repo_path))

    return "\n".join(lines)
