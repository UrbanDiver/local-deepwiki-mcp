"""Maintainability Index computation per function.

Uses the standard MI formula:
  MI = max(0, (171 - 5.2*ln(HV) - 0.23*CC - 16.2*ln(LOC)) * 100/171)

Where HV = Halstead Volume, CC = cyclomatic complexity, LOC = lines of code.
No LLM calls -- pure computation on tree-sitter ASTs.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

from local_deepwiki.core.chunk_extractors import FUNCTION_NODE_TYPES
from local_deepwiki.core.parser.ast_utils import find_nodes_by_type, get_node_name
from local_deepwiki.core.parser.code_parser import CodeParser
from local_deepwiki.generators.analysis.source_filter import iter_python_files
from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from tree_sitter import Node

logger = get_logger(__name__)

# Tree-sitter leaf node types classified as operands.
_OPERAND_TYPES: frozenset[str] = frozenset(
    {
        "identifier",
        "string",
        "string_content",
        "integer",
        "float",
        "true",
        "false",
        "none",
        "type",
    }
)

# Leaf node types to skip (not meaningful for Halstead).
_SKIP_TYPES: frozenset[str] = frozenset(
    {
        "comment",
        "newline",
        "NEWLINE",
        "INDENT",
        "DEDENT",
        "line_continuation",
    }
)

# Node types that add to cyclomatic complexity.
_CC_NODE_TYPES: frozenset[str] = frozenset(
    {
        "if_statement",
        "elif_clause",
        "for_statement",
        "while_statement",
        "except_clause",
        "with_statement",
        "assert_statement",
        "boolean_operator",
    }
)


def _collect_leaves(node: Node) -> list[Node]:
    """Collect all leaf nodes (no children) from an AST subtree."""
    leaves: list[Node] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if not current.children:
            leaves.append(current)
        else:
            stack.extend(reversed(current.children))
    return leaves


def _compute_halstead(func_node: Node, source: bytes) -> dict[str, Any]:
    """Compute Halstead metrics for a function AST node.

    Classifies leaf nodes into operators and operands:
    - Operands: identifiers, strings, numbers, booleans, none
    - Operators: keywords, punctuation, and other meaningful tokens
    - Skipped: comments, newlines, whitespace-like nodes

    Returns:
        Dict with keys n1, n2, N1, N2, and volume.
    """
    operators: dict[str, int] = {}
    operands: dict[str, int] = {}

    for leaf in _collect_leaves(func_node):
        node_type = leaf.type
        if node_type in _SKIP_TYPES:
            continue

        text = leaf.text.decode("utf-8", errors="replace") if leaf.text else ""
        if not text.strip():
            continue

        if node_type in _OPERAND_TYPES:
            operands[text] = operands.get(text, 0) + 1
        else:
            operators[text] = operators.get(text, 0) + 1

    n1 = len(operators)  # unique operators
    n2 = len(operands)  # unique operands
    big_n1 = sum(operators.values())  # total operators
    big_n2 = sum(operands.values())  # total operands

    vocabulary = n1 + n2
    length = big_n1 + big_n2

    if vocabulary <= 1:
        volume = 0.0
    else:
        volume = length * math.log2(vocabulary)

    return {
        "n1": n1,
        "n2": n2,
        "N1": big_n1,
        "N2": big_n2,
        "volume": volume,
    }


def _count_cc(node: Node) -> int:
    """Count cyclomatic complexity decision points inside a node.

    Starts at 1 (base path) and increments for each decision node.
    """
    count = 1
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in _CC_NODE_TYPES:
            count += 1
        stack.extend(current.children)
    return count


def _compute_mi(halstead_volume: float, cc: int, loc: int) -> float:
    """Compute normalized Maintainability Index (0-100).

    Uses the standard formula:
      raw = 171 - 5.2*ln(HV) - 0.23*CC - 16.2*ln(LOC)
      MI  = max(0, min(100, raw * 100 / 171))
    """
    if halstead_volume <= 0 or loc <= 0:
        return 100.0
    raw = 171 - 5.2 * math.log(halstead_volume) - 0.23 * cc - 16.2 * math.log(loc)
    return max(0.0, min(100.0, raw * 100 / 171))


def _compute_mi_stats(all_functions: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary statistics from per-function MI values."""
    total = len(all_functions)
    mi_values = [f["mi"] for f in all_functions]
    avg_mi = sum(mi_values) / total if total > 0 else 100.0
    low_mi_count = sum(1 for v in mi_values if v < 20)
    low_mi_pct = (low_mi_count / total * 100) if total > 0 else 0.0
    min_mi = min(mi_values) if mi_values else 100.0
    return {
        "total_functions": total,
        "avg_mi": round(avg_mi, 1),
        "low_mi_functions": low_mi_count,
        "low_mi_pct": round(low_mi_pct, 1),
        "min_mi": round(min_mi, 1),
    }


def analyze_maintainability(
    repo_path: Path,
    *,
    top_n: int = 20,
    exclude_tests: bool = True,
) -> dict[str, Any]:
    """Compute Maintainability Index per function across the repository.

    Args:
        repo_path: Root of the repository to scan.
        top_n: Maximum number of functions to return (sorted by MI ascending).
        exclude_tests: Skip test files when True.

    Returns:
        Dict with status, functions (worst MI first), and summary stats.
    """
    repo_path = Path(repo_path)
    parser = CodeParser()
    files = iter_python_files(repo_path, exclude_tests=exclude_tests)

    all_functions: list[dict[str, Any]] = []

    for full_path, rel_path in files:
        result = parser.parse_file(full_path)
        if result is None:
            continue

        root, language, source = result
        fn_types = FUNCTION_NODE_TYPES.get(language)
        if fn_types is None:
            continue

        fn_nodes = find_nodes_by_type(root, fn_types)
        for fn_node in fn_nodes:
            fn_name = get_node_name(fn_node, source, language) or "<anonymous>"
            loc = fn_node.end_point[0] - fn_node.start_point[0] + 1
            halstead = _compute_halstead(fn_node, source)
            cc = _count_cc(fn_node)
            mi = _compute_mi(halstead["volume"], cc, loc)

            all_functions.append(
                {
                    "function": fn_name,
                    "file": str(rel_path),
                    "line": fn_node.start_point[0] + 1,
                    "mi": round(mi, 1),
                    "halstead_volume": round(halstead["volume"], 1),
                    "cc": cc,
                    "loc": loc,
                }
            )

    # Sort by MI ascending (worst first)
    all_functions.sort(key=lambda f: f["mi"])

    stats = _compute_mi_stats(all_functions)

    logger.info(
        "Maintainability: %d functions, avg_mi=%.1f, low_mi=%d in %s",
        stats["total_functions"],
        stats["avg_mi"],
        stats["low_mi_functions"],
        repo_path,
    )

    return {
        "status": "success",
        "functions": all_functions[:top_n],
        "stats": stats,
    }
