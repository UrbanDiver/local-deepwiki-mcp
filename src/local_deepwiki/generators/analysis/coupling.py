"""Coupling metrics — Robert C. Martin's package-level stability metrics.

Computes per-module:
- Afferent coupling (Ca): number of modules that depend on this module.
- Efferent coupling (Ce): number of modules this module depends on.
- Instability (I): Ce / (Ca + Ce).  0 = maximally stable, 1 = maximally unstable.
- Abstractness (A): fraction of abstract classes.
- Distance from main sequence (D): |A + I - 1|.

No LLM or external service calls — pure filesystem + AST analysis.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from local_deepwiki.core.parser import CodeParser
from local_deepwiki.generators.analysis.module_dependencies import (
    analyze_cross_module_dependencies,
)
from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from tree_sitter import Node

logger = get_logger(__name__)

# Tree-sitter node types that represent class definitions.
_CLASS_TYPES = frozenset(
    {
        "class_definition",
        "class_declaration",
        "struct_item",
        "impl_item",
    }
)

# Regex to detect @abstractmethod decorator lines in source text.
_ABSTRACT_METHOD_RE = re.compile(r"@\s*abstractmethod\b")
# Regex to detect ABC / ABCMeta / Protocol in class base lists.
_ABC_BASE_RE = re.compile(r"\b(ABC|ABCMeta|Protocol)\b")


def _count_classes_in_file(full_path: Path) -> tuple[int, int]:
    """Return ``(total_classes, abstract_classes)`` found in *full_path*.

    A class is considered abstract if:
    - It inherits from ``ABC``, ``ABCMeta``, or ``Protocol``, OR
    - It contains at least one ``@abstractmethod`` decorator.

    Falls back to (0, 0) for unparseable or unsupported files.
    """
    parser = CodeParser()
    parse_result = parser.parse_file(full_path)
    if parse_result is None:
        return 0, 0

    root_node, _lang, src_bytes = parse_result
    source = src_bytes.decode("utf-8", errors="replace")
    lines = source.splitlines()

    total = 0
    abstract = 0

    def _is_abstract_node(node: Node) -> bool:
        """Check if a class node is abstract via base classes or decorators."""
        # Check parent classes in the node text span.
        class_src = "\n".join(lines[node.start_point[0] : node.end_point[0] + 1])
        if _ABC_BASE_RE.search(class_src):
            return True
        # Check for @abstractmethod anywhere inside the class body.
        if _ABSTRACT_METHOD_RE.search(class_src):
            return True
        return False

    def _walk(n: Node) -> None:
        nonlocal total, abstract
        if n.type in _CLASS_TYPES:
            total += 1
            if _is_abstract_node(n):
                abstract += 1
        for child in n.children:
            _walk(child)

    _walk(root_node)
    return total, abstract


def _compute_abstractness(
    repo_path: Path, modules: list[dict[str, Any]]
) -> dict[str, float]:
    """Return a dict mapping module label -> abstractness score (0.0–1.0)."""
    result: dict[str, float] = {}

    # We need to map each module label back to the files that belong to it.
    # We re-walk the repo since we don't persist the file->module mapping.
    py_files = sorted(repo_path.rglob("*.py"))
    module_names = {m["name"] for m in modules}

    from local_deepwiki.generators.analysis.module_dependencies import _module_label

    module_total: dict[str, int] = {m: 0 for m in module_names}
    module_abstract: dict[str, int] = {m: 0 for m in module_names}

    for py_file in py_files:
        try:
            rel_path = py_file.relative_to(repo_path)
        except ValueError:
            continue
        if any(
            part.startswith(".") or part in ("__pycache__", "node_modules")
            for part in rel_path.parts
        ):
            continue
        label = _module_label(rel_path)
        if label not in module_names:
            continue
        total, abstr = _count_classes_in_file(py_file)
        module_total[label] += total
        module_abstract[label] += abstr

    for mod in module_names:
        tot = module_total[mod]
        result[mod] = round(module_abstract[mod] / tot, 4) if tot > 0 else 0.0

    return result


def analyze_coupling_metrics(
    repo_path: Path,
    module_filter: str | None = None,
) -> dict[str, Any]:
    """Compute Robert C. Martin coupling metrics per module.

    Args:
        repo_path: Root of the repository to analyze.
        module_filter: Optional prefix to restrict analysis to a sub-package.

    Returns:
        A dict with ``status`` and ``metrics`` (list of per-module dicts).
    """
    dep_result = analyze_cross_module_dependencies(
        repo_path,
        module_filter=module_filter,
        include_external=False,
        min_edge_weight=1,
    )

    modules = dep_result["modules"]
    edges = dep_result["edges"]

    # Build Ca (afferent) and Ce (efferent) per module.
    ca: dict[str, int] = {m["name"]: 0 for m in modules}
    ce: dict[str, int] = {m["name"]: 0 for m in modules}

    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        if tgt in ca:
            ca[tgt] += 1
        if src in ce:
            ce[src] += 1

    abstractness = _compute_abstractness(repo_path, modules)

    metrics: list[dict[str, Any]] = []
    for mod in modules:
        name = mod["name"]
        ca_val = ca.get(name, 0)
        ce_val = ce.get(name, 0)
        total = ca_val + ce_val
        instability = round(ce_val / total, 4) if total > 0 else 0.0
        a_val = abstractness.get(name, 0.0)
        distance = round(abs(a_val + instability - 1.0), 4)
        metrics.append(
            {
                "module": name,
                "afferent_coupling": ca_val,
                "efferent_coupling": ce_val,
                "instability": instability,
                "abstractness": a_val,
                "distance": distance,
            }
        )

    # Sort by distance descending (most problematic first).
    metrics.sort(key=lambda m: m["distance"], reverse=True)

    logger.info(
        "Coupling metrics: %d modules analyzed in %s",
        len(metrics),
        repo_path,
    )

    return {
        "status": "success",
        "metrics": metrics,
        "stats": {
            "total_modules": len(metrics),
            "avg_instability": (
                round(sum(m["instability"] for m in metrics) / len(metrics), 4)
                if metrics
                else 0.0
            ),
            "avg_abstractness": (
                round(sum(m["abstractness"] for m in metrics) / len(metrics), 4)
                if metrics
                else 0.0
            ),
        },
    }
