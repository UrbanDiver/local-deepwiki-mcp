"""Hotspot analysis — ranks functions across a repo by a chosen complexity metric.

No LLM or external service calls — works entirely from the filesystem via
tree-sitter AST parsing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from local_deepwiki.core.parser import CodeParser
from local_deepwiki.generators.analysis.source_filter import iter_source_files
from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from tree_sitter import Node

logger = get_logger(__name__)

# Metric names accepted by the public API.
VALID_METRICS = frozenset({"complexity", "params", "length", "nesting"})

# Node types that count as branch/decision points for cyclomatic complexity.
_BRANCH_TYPES = frozenset(
    {
        "if_statement",
        "elif_clause",
        "else_clause",
        "for_statement",
        "while_statement",
        "try_statement",
        "except_clause",
        "case_clause",
        "match_arm",
        "conditional_expression",
        "ternary_expression",
        "boolean_operator",
        "binary_expression",
    }
)
_LOGICAL_OPS = frozenset({"and", "or", "&&", "||"})

_NESTING_TYPES = frozenset(
    {
        "if_statement",
        "for_statement",
        "while_statement",
        "try_statement",
        "for_expression",
        "while_expression",
        "if_expression",
        "match_statement",
        "switch_statement",
    }
)

_FUNCTION_TYPES = frozenset(
    {
        "function_definition",
        "function_declaration",
        "method_definition",
        "arrow_function",
        "function_item",
    }
)


def _estimate_cyclomatic(node: Node) -> int:
    """Estimate cyclomatic complexity by counting decision points."""
    count = 1  # Base complexity

    def _count(n: Node) -> None:
        nonlocal count
        if n.type in _BRANCH_TYPES:
            count += 1
        if n.type in ("boolean_operator", "binary_expression"):
            for child in n.children:
                if child.type in ("and", "or") or (
                    child.text
                    and child.text.decode("utf-8", errors="replace") in _LOGICAL_OPS
                ):
                    count += 1
                    break
        for child in n.children:
            _count(child)

    _count(node)
    return count


def _extract_function_info(node: Node, depth: int) -> dict[str, Any]:
    """Extract name, line range, param count, and complexity from a function node."""
    name = ""
    param_count = 0
    for child in node.children:
        if child.type in ("identifier", "name", "property_identifier"):
            name = child.text.decode("utf-8", errors="replace") if child.text else ""
        if child.type in ("parameters", "formal_parameters", "parameter_list"):
            param_count = sum(
                1
                for p in child.children
                if p.type not in ("(", ")", ",", "comment")
                and (p.text.decode("utf-8", errors="replace") if p.text else "")
                not in ("self", "cls")
            )
    cyclomatic = _estimate_cyclomatic(node)
    length = node.end_point[0] - node.start_point[0] + 1
    return {
        "name": name,
        "line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
        "cyclomatic": cyclomatic,
        "params": param_count,
        "length": length,
        "nesting": depth,
    }


def _walk_node(node: Node, depth: int, results: list[dict[str, Any]]) -> None:
    """Recursively collect function metrics from the AST."""
    if node.type in _FUNCTION_TYPES:
        results.append(_extract_function_info(node, depth))
    next_depth = depth + 1 if node.type in _NESTING_TYPES else depth
    for child in node.children:
        _walk_node(child, next_depth, results)


def _parse_file_functions(full_path: Path, rel_path: Path) -> list[dict[str, Any]]:
    """Parse one file and return per-function metric rows."""
    parser = CodeParser()
    parse_result = parser.parse_file(full_path)
    if parse_result is None:
        return []
    root_node, _lang, _src = parse_result
    raw: list[dict[str, Any]] = []
    _walk_node(root_node, 0, raw)
    return [
        {
            "function": entry["name"] or "<anonymous>",
            "file": str(rel_path),
            "line": entry["line"],
            "cyclomatic": entry["cyclomatic"],
            "params": entry["params"],
            "length": entry["length"],
            "nesting": entry["nesting"],
        }
        for entry in raw
    ]


def analyze_hotspots(
    repo_path: Path,
    metric: str = "complexity",
    top_n: int = 20,
    min_threshold: float | None = None,
    exclude_tests: bool = True,
) -> dict[str, Any]:
    """Walk all source files in *repo_path* and rank functions by *metric*.

    Args:
        repo_path: Root of the repository to scan.
        metric: Ranking key — one of ``complexity``, ``params``, ``length``,
            ``nesting``.
        top_n: How many results to return (1–100).
        min_threshold: Optional minimum metric value to include.
        exclude_tests: When ``True``, skip test files.

    Returns:
        A dict with ``status``, ``hotspots``, and ``stats`` keys.
    """
    if metric not in VALID_METRICS:
        return {
            "status": "error",
            "message": (
                f"Invalid metric '{metric}'. Valid values: "
                + ", ".join(sorted(VALID_METRICS))
            ),
        }

    # Map metric name to the dict key used in per-function rows.
    metric_key = "cyclomatic" if metric == "complexity" else metric

    all_functions: list[dict[str, Any]] = []
    files_scanned = 0

    for full_path, rel_path in iter_source_files(
        repo_path, exclude_tests=exclude_tests
    ):
        rows = _parse_file_functions(full_path, rel_path)
        if rows:
            all_functions.extend(rows)
        files_scanned += 1

    # Apply threshold filter.
    if min_threshold is not None:
        all_functions = [f for f in all_functions if f[metric_key] >= min_threshold]

    # Sort descending by chosen metric.
    all_functions.sort(key=lambda f: f[metric_key], reverse=True)

    hotspots = [
        {
            "function": f["function"],
            "file": f["file"],
            "line": f["line"],
            "metric_value": f[metric_key],
            "details": {
                "cyclomatic": f["cyclomatic"],
                "params": f["params"],
                "length": f["length"],
                "nesting": f["nesting"],
            },
        }
        for f in all_functions[:top_n]
    ]

    logger.info(
        "Hotspots: %d functions scanned, top %d by %s returned",
        len(all_functions),
        len(hotspots),
        metric,
    )

    return {
        "status": "success",
        "hotspots": hotspots,
        "stats": {
            "total_functions": len(all_functions),
            "files_scanned": files_scanned,
            "metric_used": metric,
        },
    }
