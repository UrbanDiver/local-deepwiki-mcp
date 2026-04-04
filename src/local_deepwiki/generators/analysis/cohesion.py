"""Cohesion metrics: LCOM4 class cohesion and module import cohesion.

Computes Lack of Cohesion of Methods (LCOM4) per class using tree-sitter AST
walking, and internal-import ratio per module directory.
No LLM calls -- pure computation on source code.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from local_deepwiki.core.chunk_extractors import CLASS_NODE_TYPES, FUNCTION_NODE_TYPES
from local_deepwiki.core.parser.ast_utils import (
    find_nodes_by_type,
    get_node_name,
    get_node_text,
)
from local_deepwiki.core.parser.code_parser import CodeParser
from local_deepwiki.generators.analysis.source_filter import iter_python_files
from local_deepwiki.logging import get_logger
from local_deepwiki.models import Language as LangEnum

logger = get_logger(__name__)

# Matches ``from x.y.z import ...`` and ``import x.y.z``
_IMPORT_PATTERNS = (
    re.compile(r"^from\s+([\w.]+)\s+import"),
    re.compile(r"^import\s+([\w.]+)"),
)


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------


class _UnionFind:
    """Disjoint-set data structure with path compression."""

    __slots__ = ("_parent",)

    def __init__(self, n: int) -> None:
        self._parent = list(range(n))

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb

    def components(self) -> int:
        return len({self.find(i) for i in range(len(self._parent))})


# ---------------------------------------------------------------------------
# LCOM4 helpers
# ---------------------------------------------------------------------------


def _extract_self_fields(method_node: Any, source: bytes) -> set[str]:
    """Walk *method_node* and return names of ``self.<field>`` accesses."""
    fields: set[str] = set()

    def walk(node: Any) -> None:
        if node.type == "attribute":
            children = node.children
            if len(children) >= 2:
                obj = children[0]
                if obj.type == "identifier" and get_node_text(obj, source) == "self":
                    attr = node.child_by_field_name("attribute")
                    if attr:
                        fields.add(get_node_text(attr, source))
        for child in node.children:
            walk(child)

    walk(method_node)
    return fields


# Base class names that indicate ABC or Protocol patterns.
_ABC_BASES = frozenset({"ABC", "ABCMeta"})
_PROTOCOL_BASES = frozenset({"Protocol"})


def _classify_class_pattern(class_node: Any, source: bytes) -> str | None:
    """Classify a class as a known OOP pattern where LCOM4 is misleading.

    Returns:
        ``"abc"`` for abstract base classes, ``"protocol"`` for Protocol
        classes, ``"mixin"`` for mixin classes, or ``None`` for regular classes.
    """
    # --- Check class name for Mixin ---
    name_node = class_node.child_by_field_name("name")
    if name_node and "Mixin" in get_node_text(name_node, source):
        return "mixin"

    # --- Check base classes in the argument_list ---
    for child in class_node.children:
        if child.type == "argument_list":
            for arg in child.children:
                base_name = _extract_base_name(arg, source)
                if base_name in _ABC_BASES:
                    return "abc"
                if base_name in _PROTOCOL_BASES:
                    return "protocol"
                # Handle keyword arguments like metaclass=ABCMeta
                if arg.type == "keyword_argument":
                    for kw_child in arg.children:
                        kw_name = _extract_base_name(kw_child, source)
                        if kw_name in _ABC_BASES:
                            return "abc"
            break

    # --- Check for @abstractmethod on >= half of methods ---
    func_types = FUNCTION_NODE_TYPES.get(LangEnum.PYTHON, set())
    methods = find_nodes_by_type(class_node, func_types)
    if methods:
        abstract_count = sum(
            1 for m in methods if _has_abstractmethod_decorator(m, source)
        )
        if abstract_count >= len(methods) / 2:
            return "abc"

    return None


def _extract_base_name(node: Any, source: bytes) -> str:
    """Extract the final identifier from a base class node.

    For ``ABC`` returns ``"ABC"``. For ``abc.ABC`` returns ``"ABC"``.
    """
    if node.type == "identifier":
        return get_node_text(node, source)
    if node.type == "attribute":
        # Dotted name -- last identifier child is the class name.
        children = [c for c in node.children if c.type == "identifier"]
        if children:
            return get_node_text(children[-1], source)
    return ""


def _has_abstractmethod_decorator(method_node: Any, source: bytes) -> bool:
    """Return True if *method_node* has an ``@abstractmethod`` decorator."""
    parent = method_node.parent
    if parent is None or parent.type != "decorated_definition":
        return False
    for sibling in parent.children:
        if sibling.type == "decorator":
            for dec_child in sibling.children:
                if (
                    dec_child.type == "identifier"
                    and get_node_text(dec_child, source) == "abstractmethod"
                ):
                    return True
    return False


def compute_lcom4(class_node: Any, source: bytes, language: LangEnum) -> int:
    """Compute LCOM4 for a single class node.

    LCOM4 counts the connected components in the method-field graph where
    methods sharing at least one field are connected.

    Args:
        class_node: Tree-sitter node for the class.
        source: Original source as bytes.
        language: Programming language of the source.

    Returns:
        Number of connected components (1 = perfectly cohesive, 0 = no methods).
    """
    func_types = FUNCTION_NODE_TYPES.get(language)
    if func_types is None:
        return 0

    methods = find_nodes_by_type(class_node, func_types)
    if not methods:
        return 0

    # Build method -> fields mapping
    method_fields: list[set[str]] = [_extract_self_fields(m, source) for m in methods]

    n = len(methods)
    uf = _UnionFind(n)

    # Connect methods that share at least one field
    for i in range(n):
        for j in range(i + 1, n):
            if method_fields[i] & method_fields[j]:
                uf.union(i, j)

    return uf.components()


# ---------------------------------------------------------------------------
# Class cohesion analysis
# ---------------------------------------------------------------------------


def analyze_class_cohesion(
    repo_path: Path,
    *,
    language: LangEnum | None = None,
    exclude_tests: bool = True,
) -> list[dict[str, Any]]:
    """Walk Python files, parse each, find classes, compute LCOM4 per class.

    Args:
        repo_path: Root of the repository.
        language: Restrict to this language (currently only Python supported).
        exclude_tests: Skip test files when True.

    Returns:
        List of dicts sorted by LCOM4 descending.
    """
    lang = language or LangEnum.PYTHON
    parser = CodeParser()
    results: list[dict[str, Any]] = []

    for full_path, rel_path in iter_python_files(
        repo_path, exclude_tests=exclude_tests
    ):
        parsed = parser.parse_file(full_path)
        if parsed is None:
            continue
        root, detected_lang, source = parsed

        class_types = CLASS_NODE_TYPES.get(detected_lang)
        if class_types is None:
            continue

        for cls_node in find_nodes_by_type(root, class_types):
            cls_name = get_node_name(cls_node, source, detected_lang) or "<anonymous>"
            lcom4 = compute_lcom4(cls_node, source, detected_lang)
            pattern = _classify_class_pattern(cls_node, source)

            func_types = FUNCTION_NODE_TYPES.get(detected_lang, set())
            methods = find_nodes_by_type(cls_node, func_types)
            all_fields: set[str] = set()
            for m in methods:
                all_fields |= _extract_self_fields(m, source)

            results.append(
                {
                    "class_name": cls_name,
                    "file": str(rel_path),
                    "line": cls_node.start_point[0] + 1,
                    "lcom4": lcom4,
                    "method_count": len(methods),
                    "field_count": len(all_fields),
                    "pattern": pattern,
                }
            )

    results.sort(key=lambda r: r["lcom4"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Module cohesion (internal-import ratio)
# ---------------------------------------------------------------------------


def _extract_imports(source: str) -> list[str]:
    """Return full dotted module paths from all import statements."""
    modules: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        for pattern in _IMPORT_PATTERNS:
            match = pattern.match(stripped)
            if match:
                modules.append(match.group(1))
                break
    return modules


def _module_label(rel_path: Path) -> str:
    """Convert a relative file path to a dotted module label.

    Keeps the full package hierarchy (does NOT strip the project top-level
    package) so labels match import paths exactly.

    ``src/mypkg/core/indexer.py`` -> ``mypkg.core.indexer``
    ``src/mypkg/__init__.py`` -> ``mypkg``
    """
    parts = list(rel_path.with_suffix("").parts)
    # Drop common wrapper dirs.
    while parts and parts[0] in ("src", "lib", "pkg"):
        parts = parts[1:]
    if not parts:
        return "root"
    # Collapse __init__ to parent
    meaningful = [p for p in parts if p != "__init__"]
    return ".".join(meaningful) if meaningful else parts[0]


def _parent_module(label: str) -> str:
    """Return the parent module label (everything up to the last dot).

    ``core.parser.ast_utils`` -> ``core.parser``
    ``core`` -> ``core``
    """
    parts = label.split(".")
    if len(parts) <= 1:
        return label
    return ".".join(parts[:-1])


def compute_module_cohesion(repo_path: Path) -> list[dict[str, Any]]:
    """Compute internal-import ratio per module directory.

    A "module" is a Python package directory. For each module, counts total
    imports and how many reference files within the same module.

    Args:
        repo_path: Root of the repository.

    Returns:
        List of dicts sorted by cohesion_ratio ascending (least cohesive first).
    """
    # Gather per-module data
    module_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"internal": 0, "total": 0, "files": set()}
    )

    for py_file, rel_path in iter_python_files(repo_path, exclude_tests=True):
        file_label = _module_label(rel_path)
        parent = _parent_module(file_label)

        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning("Could not read %s", py_file)
            continue

        imports = _extract_imports(source)
        if not imports:
            # Still register the file in its module
            module_data[parent]["files"].add(str(rel_path))
            continue

        module_data[parent]["files"].add(str(rel_path))

        for dotted in imports:
            module_data[parent]["total"] += 1

            # Check if the import is internal to this module.
            # Import path is already a dotted module name (e.g. "mypkg.b"),
            # and parent is also a dotted label (e.g. "mypkg"), so we can
            # compare directly.
            import_parent = _parent_module(dotted)

            if import_parent == parent or dotted.startswith(parent + "."):
                module_data[parent]["internal"] += 1

    results: list[dict[str, Any]] = []
    for mod_name, data in module_data.items():
        total = data["total"]
        internal = data["internal"]
        ratio = internal / total if total > 0 else 0.0
        results.append(
            {
                "module": mod_name,
                "internal_imports": internal,
                "total_imports": total,
                "cohesion_ratio": round(ratio, 4),
                "file_count": len(data["files"]),
            }
        )

    results.sort(key=lambda r: r["cohesion_ratio"])
    return results


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def analyze_cohesion(
    repo_path: Path,
    *,
    top_n: int = 20,
    exclude_tests: bool = True,
) -> dict[str, Any]:
    """Run both class and module cohesion analyses.

    Args:
        repo_path: Root of the repository.
        top_n: Max number of classes to return (highest LCOM4 first).
        exclude_tests: Skip test files.

    Returns:
        Dict with ``status``, ``class_cohesion``, ``module_cohesion``,
        and ``stats`` keys.
    """
    all_classes = analyze_class_cohesion(repo_path, exclude_tests=exclude_tests)
    module_results = compute_module_cohesion(repo_path)

    total_classes = len(all_classes)
    regular_classes = [c for c in all_classes if c.get("pattern") is None]
    pattern_count = total_classes - len(regular_classes)
    classes_gt_2 = sum(1 for c in regular_classes if c["lcom4"] > 2)
    avg_lcom = (
        sum(c["lcom4"] for c in regular_classes) / len(regular_classes)
        if regular_classes
        else 0.0
    )
    # Don't penalize small leaf packages with 0 internal imports —
    # they're likely independent implementations (e.g. providers/llm).
    low_cohesion_modules = sum(
        1
        for m in module_results
        if m["cohesion_ratio"] < 0.3
        and not (m["internal_imports"] == 0 and m["file_count"] < 6)
    )

    return {
        "status": "success",
        "class_cohesion": all_classes[:top_n],
        "module_cohesion": module_results,
        "stats": {
            "total_classes": total_classes,
            "classes_with_lcom_gt_2": classes_gt_2,
            "avg_lcom": round(avg_lcom, 2),
            "total_modules": len(module_results),
            "low_cohesion_modules": low_cohesion_modules,
            "excluded_pattern_classes": pattern_count,
        },
    }
