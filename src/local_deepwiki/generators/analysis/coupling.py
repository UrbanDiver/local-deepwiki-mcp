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
    _discover_project_tops,
    analyze_cross_module_dependencies,
)
from local_deepwiki.generators.analysis.source_filter import iter_python_files
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


def _candidate_labels(rel_path: Path, project_tops: set[str]) -> list[str]:
    """Return candidate module labels for *rel_path* in order of specificity.

    The dependency graph builds two kinds of node labels for the same file:

    1. The **source label** (via :func:`_module_label`): takes the first two
       parts of the path after stripping ``src/``, e.g.
       ``src/local_deepwiki/providers/base.py`` → ``local_deepwiki.providers``.

    2. The **import target label** (via :func:`_resolve_import_target`): strips
       the project top-level package name from import paths, e.g.
       ``from local_deepwiki.providers.base import X`` → ``providers.base``.

    Both labels may appear in the graph.  We return the stripped label first
    (most specific, e.g. ``providers.base``) followed by the unstripped label
    (``local_deepwiki.providers``) so that abstractness is attributed to the
    most precise module node that actually exists.
    """
    parts = list(rel_path.with_suffix("").parts)
    # Drop common source-layout wrapper directories.
    while parts and parts[0] in ("src", "lib", "pkg"):
        parts = parts[1:]
    if not parts:
        return ["root"]

    # Unstripped label (matches _module_label output).
    def _take2(ps: list[str]) -> str:
        meaningful = [p for p in ps[:2] if p != "__init__"]
        return ".".join(meaningful) if meaningful else (ps[0] if ps else "root")

    unstripped = _take2(parts)

    # Stripped label (matches _resolve_import_target output for imports).
    stripped: str | None = None
    if parts[0] in project_tops:
        tail = parts[1:]
        if tail:
            stripped = _take2(tail)

    candidates: list[str] = []
    if stripped and stripped != unstripped:
        candidates.append(stripped)
    candidates.append(unstripped)
    return candidates


def _compute_abstractness(
    repo_path: Path, modules: list[dict[str, Any]]
) -> dict[str, float]:
    """Return a dict mapping module label -> abstractness score (0.0–1.0).

    The dependency graph contains two kinds of module nodes for files in
    projects with a top-level wrapper package (e.g. ``local_deepwiki``):

    - **Source nodes** such as ``local_deepwiki.providers`` — created from
      file paths via :func:`~module_dependencies._module_label`.
    - **Import-target nodes** such as ``providers.base`` — created when other
      modules import from ``local_deepwiki.providers.base``.

    We generate both candidate labels for each file and attribute the class
    counts to whichever graph node is found first (preferring the more
    specific stripped label).  This ensures that ABCs and Protocols defined in
    ``providers/base.py`` are counted against ``providers.base`` (Ca=30) rather
    than only against ``local_deepwiki.providers`` (Ce=12), giving an accurate
    abstractness score for the heavily-depended-on module.
    """
    result: dict[str, float] = {}

    # We need to map each module label back to the files that belong to it.
    # We re-walk the repo since we don't persist the file->module mapping.
    module_names = {m["name"] for m in modules}
    project_tops = _discover_project_tops(repo_path)

    module_total: dict[str, int] = {m: 0 for m in module_names}
    module_abstract: dict[str, int] = {m: 0 for m in module_names}

    for py_file, rel_path in iter_python_files(repo_path, exclude_tests=False):
        # Find the first candidate label that exists as a module node.
        label: str | None = None
        for candidate in _candidate_labels(rel_path, project_tops):
            if candidate in module_names:
                label = candidate
                break
        if label is None:
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
