"""Mermaid diagram generation for codemap graphs.

Produces deterministic Mermaid flowcharts from ``CodemapGraph`` instances,
with subgraphs per file, color-coded node classes (entry/cross-file/leaf),
and optional click handlers for source navigation.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from local_deepwiki.generators.codemap.models import (
    CodemapFocus,
    CodemapGraph,
    CodemapNode,
)


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

    # Click handlers for source navigation
    if repo_path is not None:
        for node in sorted_nodes:
            nid = node_ids[node.qualified_name]
            try:
                rel = str(Path(node.file_path).relative_to(repo_path))
            except (ValueError, TypeError):
                rel = node.file_path
            lines.append(f'    click {nid} "files/{rel}" _blank')

    return "\n".join(lines)
