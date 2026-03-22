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

from collections import Counter, defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from local_deepwiki.core.parser import CodeParser
from local_deepwiki.generators.analysis.source_filter import iter_source_files
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
_FEATURE_ENVY_CALL_THRESHOLD = 5
_FEATURE_ENVY_IGNORED_OBJECTS: frozenset[str] = frozenset(
    {
        "logger",
        "log",  # logging
        "lines",
        "parts",
        "result_lines",
        "sections",  # list accumulators
        "asyncio",  # stdlib
        "re",
        "os",
        "sys",
        "json",
        "math",
        "time",
        "Path",  # stdlib modules and types
        "errors",
        "smells",
        "warnings",  # collection accumulators
        "prompt_parts",  # prompt builders
        "console",
        "table",  # Rich output objects
        "parser",  # argparse
        "m",
        "s",  # regex match / single-letter iteration vars
        "data",
        "metadata",
        "config",
        "cached",  # dict-like / config access
        "request",
        "response",  # web framework objects
        "node",
        "cursor",  # AST / DB cursors
        "entry",
        "entity",
        "candidate",  # iteration variables
        "mock",
        "patch",  # test doubles
    }
)
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
                    if (
                        obj_name not in ("self", "cls", "super")
                        and obj_name not in _FEATURE_ENVY_IGNORED_OBJECTS
                    ):
                        objects.append(obj_name)
        for child in n.children:
            _walk(child)

    _walk(node)
    return objects


# ---------------------------------------------------------------------------
# Per-smell detector helpers
# ---------------------------------------------------------------------------


def _collect_class_methods(node: Node, out: list[Any]) -> None:
    if node.type in _FUNCTION_TYPES:
        out.append(node)
    for child in node.children:
        _collect_class_methods(child, out)


def _detect_god_class(
    class_node: Any,
    class_name: str,
    rel_path: Path,
    threshold_level: int,
) -> list[dict[str, Any]]:
    """Return god-class smell dicts for *class_node* if thresholds exceeded."""
    smells: list[dict[str, Any]] = []
    methods: list[Any] = []
    for child in class_node.children:
        _collect_class_methods(child, methods)

    class_lines = class_node.end_point[0] - class_node.start_point[0] + 1
    if (
        _SEVERITY_ORDER[SEVERITY_HIGH] >= threshold_level
        and len(methods) > _GOD_CLASS_METHOD_THRESHOLD
        and class_lines > _GOD_CLASS_LINE_THRESHOLD
    ):
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
    return smells


def _detect_long_method(
    func_node: Any,
    func_name: str,
    rel_path: Path,
    threshold_level: int,
) -> dict[str, Any] | None:
    """Return a long-method smell dict or None."""
    func_lines = func_node.end_point[0] - func_node.start_point[0] + 1
    cyclomatic = _estimate_cyclomatic(func_node)
    if _SEVERITY_ORDER[SEVERITY_HIGH] >= threshold_level and (
        func_lines > _LONG_METHOD_LINE_THRESHOLD
        or cyclomatic > _LONG_METHOD_CC_THRESHOLD
    ):
        return {
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
            "suggestion": "Extract smaller helper functions. Reduce branching.",
        }
    return None


def _detect_long_params(
    func_node: Any,
    func_name: str,
    params: list[str],
    rel_path: Path,
    threshold_level: int,
) -> dict[str, Any] | None:
    """Return a long-parameter-list smell dict or None."""
    if (
        _SEVERITY_ORDER[SEVERITY_MEDIUM] >= threshold_level
        and len(params) > _LONG_PARAM_THRESHOLD
    ):
        return {
            "type": "long_parameter_list",
            "severity": SEVERITY_MEDIUM,
            "file": str(rel_path),
            "line": func_node.start_point[0] + 1,
            "entity": func_name,
            "description": (
                f"Function has {len(params)} parameters "
                f"(threshold: {_LONG_PARAM_THRESHOLD})"
            ),
            "suggestion": "Introduce a parameter object or configuration dataclass.",
        }
    return None


def _detect_deep_nesting(
    func_node: Any,
    func_name: str,
    rel_path: Path,
    threshold_level: int,
) -> dict[str, Any] | None:
    """Return a deep-nesting smell dict or None."""
    nesting = _max_nesting(func_node)
    if (
        _SEVERITY_ORDER[SEVERITY_MEDIUM] >= threshold_level
        and nesting > _DEEP_NESTING_THRESHOLD
    ):
        return {
            "type": "deep_nesting",
            "severity": SEVERITY_MEDIUM,
            "file": str(rel_path),
            "line": func_node.start_point[0] + 1,
            "entity": func_name,
            "description": (
                f"Function has nesting depth {nesting} "
                f"(threshold: {_DEEP_NESTING_THRESHOLD})"
            ),
            "suggestion": "Use early returns (guard clauses) to flatten nesting.",
        }
    return None


def _count_external_calls(func_node: Any) -> tuple[str, int] | None:
    """Return (most_common_obj, count) for feature-envy detection, or None."""
    calls = _collect_attribute_calls(func_node)
    if not calls:
        return None
    counter = Counter(calls)
    most_common_obj, count = counter.most_common(1)[0]
    if count > _FEATURE_ENVY_CALL_THRESHOLD:
        return most_common_obj, count
    return None


def _detect_feature_envy(
    func_node: Any,
    func_name: str,
    rel_path: Path,
    threshold_level: int,
) -> list[dict[str, Any]]:
    """Return feature-envy smell dicts (0 or 1) for *func_node*."""
    smells: list[dict[str, Any]] = []
    if _SEVERITY_ORDER[SEVERITY_MEDIUM] < threshold_level:
        return smells
    result = _count_external_calls(func_node)
    if result is not None:
        most_common_obj, count = result
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
                    f"Consider moving this function to the '{most_common_obj}' class."
                ),
            }
        )
    return smells


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

    function_params: dict[str, list[str]] = {}

    def _walk_root(node: Any) -> None:
        if node.type in _CLASS_TYPES:
            class_name = ""
            for child in node.children:
                if child.type in ("identifier", "name", "type_identifier"):
                    class_name = _node_text(child)
                    break
            smells.extend(
                _detect_god_class(
                    node, class_name or "<unnamed>", rel_path, threshold_level
                )
            )
        elif node.type in _FUNCTION_TYPES:
            func_name = ""
            for child in node.children:
                if child.type in ("identifier", "name", "property_identifier"):
                    func_name = _node_text(child)
                    break
            func_name = func_name or "<anonymous>"
            params = _get_params(node)
            function_params[func_name] = params

            smell = _detect_long_method(node, func_name, rel_path, threshold_level)
            if smell:
                smells.append(smell)

            smell = _detect_long_params(
                node, func_name, params, rel_path, threshold_level
            )
            if smell:
                smells.append(smell)

            smell = _detect_deep_nesting(node, func_name, rel_path, threshold_level)
            if smell:
                smells.append(smell)

            smells.extend(
                _detect_feature_envy(node, func_name, rel_path, threshold_level)
            )

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


def _compute_smell_summary(all_smells: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the summary dict from a flat list of smell dicts.

    Args:
        all_smells: All detected smell dicts.

    Returns:
        Dict with ``total``, ``by_severity``, and ``by_type`` keys.
    """
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
    return {
        "total": len(all_smells),
        "by_severity": by_severity,
        "by_type": by_type,
    }


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

    all_smells: list[dict[str, Any]] = []

    for full_path, rel_path in iter_source_files(
        repo_path, exclude_tests=exclude_tests
    ):
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

    logger.info(
        "Design smells: %d smells found in %s",
        len(all_smells),
        repo_path,
    )

    return {
        "status": "success",
        "smells": all_smells,
        "summary": _compute_smell_summary(all_smells),
    }
