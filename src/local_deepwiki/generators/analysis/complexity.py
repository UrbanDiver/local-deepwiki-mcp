"""Complexity metrics generator.

Computes cyclomatic complexity, nesting depth, and other code complexity metrics
using tree-sitter AST analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from local_deepwiki.core.parser import CodeParser

if TYPE_CHECKING:
    from tree_sitter import Node
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


async def compute_complexity_metrics(
    file_path: Path, repo_path: Path
) -> dict[str, Any]:
    """Compute cyclomatic complexity metrics for a source file.

    Analyzes code complexity using tree-sitter AST parsing. Returns
    function/class counts, line metrics, cyclomatic complexity,
    nesting depth, and parameter counts.

    Args:
        file_path: Path to the source file (relative to repo_path for display)
        repo_path: Path to the repository root

    Returns:
        dict with 'status', 'file_path', 'language', 'lines', 'counts',
        'complexity', 'functions', and 'classes' keys.
    """
    full_file = repo_path / file_path

    parser = CodeParser()
    parse_result = parser.parse_file(full_file)

    if parse_result is None:
        return {
            "status": "success",
            "file_path": str(file_path),
            "message": (
                f"File type not supported for AST analysis: {full_file.suffix}"
            ),
            "metrics": {},
        }

    root_node, language, source_bytes = parse_result
    source_text = source_bytes.decode("utf-8", errors="replace")
    lines = source_text.splitlines()

    # --- Line counts ---
    total_lines = len(lines)
    blank_lines = sum(1 for line in lines if not line.strip())

    def _count_comment_lines(root: Node) -> int:
        """Count lines that contain comments."""
        comment_line_set: set[int] = set()

        def _walk(n: Node) -> None:
            """Recursively collect line numbers that contain comment nodes."""
            if n.type in ("comment", "line_comment", "block_comment"):
                for line_no in range(n.start_point[0], n.end_point[0] + 1):
                    comment_line_set.add(line_no)
            for child in n.children:
                _walk(child)

        _walk(root)
        return len(comment_line_set)

    comment_lines = _count_comment_lines(root_node)

    # --- AST traversal to collect function / class metrics ---
    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    max_nesting = 0

    nesting_types = frozenset(
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

    function_types = frozenset(
        {
            "function_definition",
            "function_declaration",
            "method_definition",
            "arrow_function",
            "function_item",
        }
    )

    class_types = frozenset(
        {
            "class_definition",
            "class_declaration",
            "struct_item",
            "impl_item",
        }
    )

    def _estimate_cyclomatic(node: Node) -> int:
        """Estimate cyclomatic complexity by counting decision points."""
        count = 1  # Base complexity
        branch_types = frozenset(
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
        logical_ops = frozenset({"and", "or", "&&", "||"})

        def _count_branches(n: Node) -> None:
            """Recursively count branch and logical-operator decision points."""
            nonlocal count
            if n.type in branch_types:
                count += 1
            if n.type in ("boolean_operator", "binary_expression"):
                for child in n.children:
                    if child.type in ("and", "or") or (
                        child.text
                        and child.text.decode("utf-8", errors="replace") in logical_ops
                    ):
                        count += 1
                        break
            for child in n.children:
                _count_branches(child)

        _count_branches(node)
        return count

    def _extract_function_info(node: Node, depth: int) -> dict[str, Any]:
        """Extract name, line range, parameter count, and complexity from a function node."""
        name = ""
        param_count = 0
        for child in node.children:
            if child.type in ("identifier", "name", "property_identifier"):
                name = (
                    child.text.decode("utf-8", errors="replace") if child.text else ""
                )
            if child.type in (
                "parameters",
                "formal_parameters",
                "parameter_list",
            ):
                param_count = sum(
                    1
                    for p in child.children
                    if p.type not in ("(", ")", ",", "comment")
                    and (p.text.decode("utf-8", errors="replace") if p.text else "")
                    not in ("self", "cls")
                )
        cyclomatic = _estimate_cyclomatic(node)
        return {
            "name": name,
            "line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "param_count": param_count,
            "nesting_depth": depth,
            "cyclomatic_complexity": cyclomatic,
        }

    def _walk_node(node: Node, depth: int = 0) -> None:
        """Recursively traverse the AST, collecting function and class metrics."""
        nonlocal max_nesting
        node_type = node.type

        if node_type in function_types:
            func_info = _extract_function_info(node, depth)
            functions.append(func_info)

        if node_type in class_types:
            class_name = ""
            for child in node.children:
                if child.type in (
                    "identifier",
                    "name",
                    "type_identifier",
                ):
                    class_name = (
                        child.text.decode("utf-8", errors="replace")
                        if child.text
                        else ""
                    )
                    break
            classes.append({"name": class_name, "line": node.start_point[0] + 1})

        if node_type in nesting_types:
            max_nesting = max(max_nesting, depth)

        for child in node.children:
            child_depth = depth + 1 if node_type in nesting_types else depth
            _walk_node(child, child_depth)

    _walk_node(root_node, 0)

    # --- Compute aggregate metrics ---
    param_counts = [f["param_count"] for f in functions]
    cyclomatic_values = [f["cyclomatic_complexity"] for f in functions]
    nesting_depths = [f["nesting_depth"] for f in functions]

    avg_params = round(sum(param_counts) / len(param_counts), 2) if param_counts else 0
    max_params = max(param_counts) if param_counts else 0
    avg_cyclomatic = (
        round(sum(cyclomatic_values) / len(cyclomatic_values), 2)
        if cyclomatic_values
        else 0
    )
    max_cyclomatic = max(cyclomatic_values) if cyclomatic_values else 0
    avg_nesting = (
        round(sum(nesting_depths) / len(nesting_depths), 2) if nesting_depths else 0
    )

    result = {
        "status": "success",
        "file_path": str(file_path),
        "language": language.value,
        "lines": {
            "total": total_lines,
            "blank": blank_lines,
            "comment": comment_lines,
            "code": total_lines - blank_lines - comment_lines,
        },
        "counts": {
            "functions": len(functions),
            "classes": len(classes),
        },
        "complexity": {
            "avg_cyclomatic": avg_cyclomatic,
            "max_cyclomatic": max_cyclomatic,
            "avg_params": avg_params,
            "max_params": max_params,
            "avg_nesting_depth": avg_nesting,
            "max_nesting_depth": max_nesting,
        },
        "functions": functions[:50],
        "classes": classes[:50],
    }

    logger.info(
        "Complexity metrics: %d functions, %d classes for %s",
        len(functions),
        len(classes),
        file_path,
    )
    return result
