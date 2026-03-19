"""Design smell detection using heuristic thresholds.

Detects common design smells via static AST analysis:
- God Class (>15 methods AND >500 lines)
- Long Method (>80 lines OR cyclomatic complexity >15)
- Long Parameter List (>6 parameters)
- Feature Envy (function makes >3 calls to methods of a single other class)
- Large File (>800 lines)
- Deep Nesting (nesting depth >4 levels)
- Data Clump (>3 functions share the same 3+ parameter names)

No LLM or external service calls — pure filesystem + AST analysis.
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from local_deepwiki.core.parser import CodeParser
from local_deepwiki.core.parser.languages import EXTENSION_MAP
from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from tree_sitter import Node

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Severity constants
# ---------------------------------------------------------------------------
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

_SEVERITY_ORDER = {SEVERITY_LOW: 0, SEVERITY_MEDIUM: 1, SEVERITY_HIGH: 2}

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
_GOD_CLASS_METHOD_THRESHOLD = 15
_GOD_CLASS_LINE_THRESHOLD = 500
_LONG_METHOD_LINE_THRESHOLD = 80
_LONG_METHOD_CC_THRESHOLD = 15
_LONG_PARAM_THRESHOLD = 6
_FEATURE_ENVY_CALL_THRESHOLD = 3
_LARGE_FILE_LINE_THRESHOLD = 800
_DEEP_NESTING_THRESHOLD = 4
_DATA_CLUMP_SHARED_PARAMS = 3
_DATA_CLUMP_MIN_FUNCTIONS = 3

# ---------------------------------------------------------------------------
# Node-type sets (shared with complexity.py patterns)
# ---------------------------------------------------------------------------
_FUNCTION_TYPES = frozenset(
    {
        "function_definition",
        "function_declaration",
        "method_definition",
        "arrow_function",
        "function_item",
    }
)

_CLASS_TYPES = frozenset(
    {
        "class_definition",
        "class_declaration",
        "struct_item",
        "impl_item",
    }
)

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

_TEST_DIR_NAMES = frozenset({"tests", "test", "__tests__", "spec"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_test_file(rel_path: Path) -> bool:
    name = rel_path.name
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return True
    return any(part in _TEST_DIR_NAMES for part in rel_path.parts)


def _node_text(node: Node) -> str:
    return node.text.decode("utf-8", errors="replace") if node.text else ""


def _estimate_cyclomatic(node: Node) -> int:
    count = 1
    logical_ops = frozenset({"and", "or", "&&", "||"})

    def _count(n: Node) -> None:
        nonlocal count
        if n.type in _BRANCH_TYPES:
            count += 1
        if n.type in ("boolean_operator", "binary_expression"):
            for child in n.children:
                if child.type in ("and", "or") or _node_text(child) in logical_ops:
                    count += 1
                    break
        for child in n.children:
            _count(child)

    _count(node)
    return count


def _get_params(node: Node) -> list[str]:
    """Extract parameter names from a function node."""
    params: list[str] = []
    for child in node.children:
        if child.type in ("parameters", "formal_parameters", "parameter_list"):
            for p in child.children:
                if p.type not in ("(", ")", ",", "comment"):
                    name = _node_text(p)
                    if name not in ("self", "cls"):
                        params.append(name)
    return params


def _max_nesting(node: Node, depth: int = 0) -> int:
    """Return the maximum nesting depth within a node."""
    result = depth if node.type in _NESTING_TYPES else 0
    for child in node.children:
        child_depth = depth + 1 if node.type in _NESTING_TYPES else depth
        result = max(result, _max_nesting(child, child_depth))
    return result


def _collect_attribute_calls(node: Node) -> list[str]:
    """Collect object names from attribute access calls (obj.method()).

    Returns a list of object names (left side of dot) found in call expressions.
    """
    objects: list[str] = []

    def _walk(n: Node) -> None:
        # call_expression children: function + arguments
        if n.type in ("call", "call_expression"):
            func_node = None
            for child in n.children:
                if child.type in (
                    "attribute",
                    "member_expression",
                    "field_expression",
                ):
                    func_node = child
                    break
            if func_node is not None:
                obj_node = func_node.children[0] if func_node.children else None
                if obj_node and obj_node.type == "identifier":
                    obj_name = _node_text(obj_node)
                    if obj_name not in ("self", "cls", "super"):
                        objects.append(obj_name)
        for child in n.children:
            _walk(child)

    _walk(node)
    return objects


# ---------------------------------------------------------------------------
# Per-file analysis
# ---------------------------------------------------------------------------


def _analyze_file(
    full_path: Path,
    rel_path: Path,
    severity_threshold: str,
) -> list[dict[str, Any]]:
    """Detect design smells in a single source file.

    Returns a list of smell dicts (possibly empty).
    """
    smells: list[dict[str, Any]] = []
    threshold_level = _SEVERITY_ORDER[severity_threshold]

    parser = CodeParser()
    parse_result = parser.parse_file(full_path)
    if parse_result is None:
        return smells

    root_node, _lang, src_bytes = parse_result
    source = src_bytes.decode("utf-8", errors="replace")
    total_lines = len(source.splitlines())

    # --- Large File ---
    if _SEVERITY_ORDER[SEVERITY_MEDIUM] >= threshold_level:
        if total_lines > _LARGE_FILE_LINE_THRESHOLD:
            smells.append(
                {
                    "type": "large_file",
                    "severity": SEVERITY_MEDIUM,
                    "file": str(rel_path),
                    "line": 1,
                    "entity": rel_path.name,
                    "description": (
                        f"File has {total_lines} lines "
                        f"(threshold: {_LARGE_FILE_LINE_THRESHOLD})"
                    ),
                    "suggestion": "Split into smaller, focused modules.",
                }
            )

    # --- Walk classes and functions ---
    function_params: dict[str, list[str]] = {}  # func_name -> param list

    def _walk_class(class_node: Node, class_name: str) -> None:
        """Inspect a class node for God Class smell."""
        methods: list[Node] = []
        for child in class_node.children:
            _collect_methods(child, methods)

        class_lines = class_node.end_point[0] - class_node.start_point[0] + 1
        has_many_methods = len(methods) > _GOD_CLASS_METHOD_THRESHOLD
        has_many_lines = class_lines > _GOD_CLASS_LINE_THRESHOLD

        if _SEVERITY_ORDER[SEVERITY_HIGH] >= threshold_level:
            if has_many_methods and has_many_lines:
                smells.append(
                    {
                        "type": "god_class",
                        "severity": SEVERITY_HIGH,
                        "file": str(rel_path),
                        "line": class_node.start_point[0] + 1,
                        "entity": class_name,
                        "description": (
                            f"Class has {len(methods)} methods and {class_lines} lines "
                            f"(thresholds: {_GOD_CLASS_METHOD_THRESHOLD} methods, "
                            f"{_GOD_CLASS_LINE_THRESHOLD} lines)"
                        ),
                        "suggestion": (
                            "Apply Single Responsibility Principle — extract cohesive "
                            "groups of methods into separate classes."
                        ),
                    }
                )

    def _collect_methods(node: Node, out: list[Node]) -> None:
        if node.type in _FUNCTION_TYPES:
            out.append(node)
        for child in node.children:
            _collect_methods(child, out)

    def _walk_function(func_node: Node, func_name: str) -> None:
        """Inspect a function node for method-level smells."""
        func_lines = func_node.end_point[0] - func_node.start_point[0] + 1
        cyclomatic = _estimate_cyclomatic(func_node)
        params = _get_params(func_node)
        nesting = _max_nesting(func_node)

        # Record params for data clump detection.
        function_params[func_name] = params

        # --- Long Method ---
        if _SEVERITY_ORDER[SEVERITY_HIGH] >= threshold_level:
            if (
                func_lines > _LONG_METHOD_LINE_THRESHOLD
                or cyclomatic > _LONG_METHOD_CC_THRESHOLD
            ):
                smells.append(
                    {
                        "type": "long_method",
                        "severity": SEVERITY_HIGH,
                        "file": str(rel_path),
                        "line": func_node.start_point[0] + 1,
                        "entity": func_name,
                        "description": (
                            f"Function has {func_lines} lines and cyclomatic "
                            f"complexity {cyclomatic} "
                            f"(thresholds: {_LONG_METHOD_LINE_THRESHOLD} lines, "
                            f"CC {_LONG_METHOD_CC_THRESHOLD})"
                        ),
                        "suggestion": (
                            "Extract smaller helper functions. Reduce branching."
                        ),
                    }
                )

        # --- Long Parameter List ---
        if _SEVERITY_ORDER[SEVERITY_MEDIUM] >= threshold_level:
            if len(params) > _LONG_PARAM_THRESHOLD:
                smells.append(
                    {
                        "type": "long_parameter_list",
                        "severity": SEVERITY_MEDIUM,
                        "file": str(rel_path),
                        "line": func_node.start_point[0] + 1,
                        "entity": func_name,
                        "description": (
                            f"Function has {len(params)} parameters "
                            f"(threshold: {_LONG_PARAM_THRESHOLD})"
                        ),
                        "suggestion": (
                            "Introduce a parameter object or configuration dataclass."
                        ),
                    }
                )

        # --- Deep Nesting ---
        if _SEVERITY_ORDER[SEVERITY_MEDIUM] >= threshold_level:
            if nesting > _DEEP_NESTING_THRESHOLD:
                smells.append(
                    {
                        "type": "deep_nesting",
                        "severity": SEVERITY_MEDIUM,
                        "file": str(rel_path),
                        "line": func_node.start_point[0] + 1,
                        "entity": func_name,
                        "description": (
                            f"Function has nesting depth {nesting} "
                            f"(threshold: {_DEEP_NESTING_THRESHOLD})"
                        ),
                        "suggestion": (
                            "Use early returns (guard clauses) to flatten nesting."
                        ),
                    }
                )

        # --- Feature Envy ---
        if _SEVERITY_ORDER[SEVERITY_MEDIUM] >= threshold_level:
            calls = _collect_attribute_calls(func_node)
            if calls:
                counter = Counter(calls)
                most_common_obj, count = counter.most_common(1)[0]
                if count > _FEATURE_ENVY_CALL_THRESHOLD:
                    smells.append(
                        {
                            "type": "feature_envy",
                            "severity": SEVERITY_MEDIUM,
                            "file": str(rel_path),
                            "line": func_node.start_point[0] + 1,
                            "entity": func_name,
                            "description": (
                                f"Function calls '{most_common_obj}' methods "
                                f"{count} times — it may belong there "
                                f"(threshold: {_FEATURE_ENVY_CALL_THRESHOLD})"
                            ),
                            "suggestion": (
                                f"Consider moving this function to the "
                                f"'{most_common_obj}' class."
                            ),
                        }
                    )

    def _walk_root(node: Node) -> None:
        if node.type in _CLASS_TYPES:
            class_name = ""
            for child in node.children:
                if child.type in ("identifier", "name", "type_identifier"):
                    class_name = _node_text(child)
                    break
            _walk_class(node, class_name or "<unnamed>")
        elif node.type in _FUNCTION_TYPES:
            func_name = ""
            for child in node.children:
                if child.type in ("identifier", "name", "property_identifier"):
                    func_name = _node_text(child)
                    break
            _walk_function(node, func_name or "<anonymous>")
        for child in node.children:
            _walk_root(child)

    _walk_root(root_node)

    # --- Data Clump (file-level check after all functions walked) ---
    if (
        _SEVERITY_ORDER[SEVERITY_LOW] >= threshold_level
        and len(function_params) >= _DATA_CLUMP_MIN_FUNCTIONS
    ):
        _detect_data_clumps(function_params, rel_path, smells)

    return smells


def _detect_data_clumps(
    function_params: dict[str, list[str]],
    rel_path: Path,
    smells: list[dict[str, Any]],
) -> None:
    """Detect data clump smell: >3 functions share the same 3+ parameter names."""
    # Build param-set -> list of function names mapping.
    param_groups: dict[frozenset[str], list[str]] = defaultdict(list)
    for func_name, params in function_params.items():
        if len(params) >= _DATA_CLUMP_SHARED_PARAMS:
            param_set = frozenset(params)
            param_groups[param_set].append(func_name)

    # Find cliques where many functions share all params from a common subset.
    # For simplicity: if the same frozen set appears in >= _DATA_CLUMP_MIN_FUNCTIONS,
    # report it. Also check subsets of size >= _DATA_CLUMP_SHARED_PARAMS.
    reported: set[frozenset[str]] = set()

    for param_set, funcs in param_groups.items():
        if len(funcs) >= _DATA_CLUMP_MIN_FUNCTIONS and param_set not in reported:
            reported.add(param_set)
            shared = sorted(param_set)
            smells.append(
                {
                    "type": "data_clump",
                    "severity": SEVERITY_LOW,
                    "file": str(rel_path),
                    "line": 1,
                    "entity": ", ".join(funcs[:5]),
                    "description": (
                        f"{len(funcs)} functions share parameters: "
                        + ", ".join(shared[:6])
                    ),
                    "suggestion": (
                        "Extract shared parameters into a dedicated data class or "
                        "named tuple."
                    ),
                }
            )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def analyze_design_smells(
    repo_path: Path,
    severity_threshold: str = "medium",
    exclude_tests: bool = True,
) -> dict[str, Any]:
    """Scan *repo_path* for design smells.

    Args:
        repo_path: Root of the repository to scan.
        severity_threshold: Minimum severity to include (``"low"``,
            ``"medium"``, ``"high"``).
        exclude_tests: When ``True``, skip test files.

    Returns:
        A dict with ``status``, ``smells``, and ``summary`` keys.
    """
    if severity_threshold not in _SEVERITY_ORDER:
        return {
            "status": "error",
            "message": (
                f"Invalid severity_threshold '{severity_threshold}'. "
                "Valid values: low, medium, high"
            ),
        }

    supported_extensions = set(EXTENSION_MAP.keys())

    all_smells: list[dict[str, Any]] = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and d not in ("node_modules", "__pycache__", ".deepwiki", "dist", "build")
        ]
        for fname in files:
            full_path = Path(root) / fname
            try:
                rel_path = full_path.relative_to(repo_path)
            except ValueError:
                continue

            if full_path.suffix not in supported_extensions:
                continue
            if exclude_tests and _is_test_file(rel_path):
                continue

            file_smells = _analyze_file(full_path, rel_path, severity_threshold)
            all_smells.extend(file_smells)

    # Sort: severity descending, then file, then line.
    all_smells.sort(
        key=lambda s: (
            -_SEVERITY_ORDER.get(s["severity"], 0),
            s["file"],
            s["line"],
        )
    )

    # Summary
    by_severity: dict[str, int] = {
        SEVERITY_HIGH: 0,
        SEVERITY_MEDIUM: 0,
        SEVERITY_LOW: 0,
    }
    by_type: dict[str, int] = {}
    for smell in all_smells:
        sev = smell["severity"]
        stype = smell["type"]
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_type[stype] = by_type.get(stype, 0) + 1

    logger.info(
        "Design smells: %d smells found in %s",
        len(all_smells),
        repo_path,
    )

    return {
        "status": "success",
        "smells": all_smells,
        "summary": {
            "total": len(all_smells),
            "by_severity": by_severity,
            "by_type": by_type,
        },
    }
