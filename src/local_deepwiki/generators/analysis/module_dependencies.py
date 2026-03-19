"""Cross-module dependency analysis.

Builds an inter-module import graph from Python source files.  Modules are
identified as second-level packages (e.g. ``core.indexer``, ``generators.wiki``)
relative to the project root.  Edge weights reflect how many times one module
imports from another.

No LLM or external service calls — pure filesystem + regex analysis.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# Matches ``from x.y.z import ...`` and ``import x.y.z``
_IMPORT_PATTERNS = (
    re.compile(r"^from\s+([\w.]+)\s+import"),
    re.compile(r"^import\s+([\w.]+)"),
)


def _extract_full_imports(source: str) -> list[str]:
    """Return full dotted module paths from all import statements in *source*."""
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

    ``src/local_deepwiki/core/indexer.py`` -> ``core.indexer``

    We take up to the first two meaningful package parts (skipping ``src``
    and single top-level project wrappers) so that siblings like
    ``core/indexer.py`` and ``core/vectorstore/base.py`` both map to
    ``core``.
    """
    parts = list(rel_path.with_suffix("").parts)
    # Drop common wrapper dirs.
    while parts and parts[0] in ("src", "lib", "pkg"):
        parts = parts[1:]
    if not parts:
        return "root"
    return ".".join(parts[:2]) if len(parts) >= 2 else parts[0]


def _top_level(dotted: str) -> str:
    """Return the first component of a dotted module name."""
    return dotted.split(".")[0]


def analyze_cross_module_dependencies(
    repo_path: Path,
    module_filter: str | None = None,
    include_external: bool = False,
    min_edge_weight: int = 1,
) -> dict[str, Any]:
    """Build and return the inter-module import graph for *repo_path*.

    Args:
        repo_path: Root of the repository to scan.
        module_filter: When given, only include modules whose label starts with
            this prefix (e.g. ``"core"``).
        include_external: When ``False`` (default), third-party and stdlib
            imports are excluded.
        min_edge_weight: Minimum number of import occurrences to include an
            edge in the output.

    Returns:
        A dict with ``status``, ``modules``, ``edges``, ``mermaid``, and
        ``stats`` keys.
    """
    # Discover project package name(s) from the top-level Python dirs.
    project_tops: set[str] = set()
    for item in repo_path.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            project_tops.add(item.name)
    src_dir = repo_path / "src"
    if src_dir.is_dir():
        for item in src_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                project_tops.add(item.name)

    module_file_counts: dict[str, int] = defaultdict(int)
    module_line_counts: dict[str, int] = defaultdict(int)
    edge_counts: dict[tuple[str, str], int] = defaultdict(int)
    edge_imports: dict[tuple[str, str], list[str]] = defaultdict(list)

    py_files = sorted(repo_path.rglob("*.py"))

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

        src_module = _module_label(rel_path)
        if module_filter and not src_module.startswith(module_filter):
            continue

        module_file_counts[src_module] += 1

        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning("Could not read %s", py_file)
            continue

        module_line_counts[src_module] += source.count("\n") + 1

        for dotted in _extract_full_imports(source):
            top = _top_level(dotted)

            is_internal = top in project_tops

            if not include_external and not is_internal:
                continue

            # Determine target module label.
            if is_internal:
                parts = dotted.split(".")
                if parts[0] in project_tops:
                    parts = parts[1:]
                if not parts:
                    continue
                tgt_module = ".".join(parts[:2]) if len(parts) >= 2 else parts[0]
            else:
                # stdlib or third-party: use top-level name only
                tgt_module = top

            if tgt_module == src_module:
                continue  # self-import

            if module_filter and not tgt_module.startswith(module_filter):
                if not include_external:
                    continue

            edge = (src_module, tgt_module)
            edge_counts[edge] += 1
            if dotted not in edge_imports[edge]:
                edge_imports[edge].append(dotted)

    # Build output structures.
    all_module_names = set(module_file_counts.keys()) | {
        tgt for (_, tgt) in edge_counts
    }
    modules = [
        {
            "name": m,
            "file_count": module_file_counts.get(m, 0),
            "total_lines": module_line_counts.get(m, 0),
        }
        for m in sorted(all_module_names)
    ]

    edges = [
        {
            "source": src,
            "target": tgt,
            "weight": cnt,
            "imports": edge_imports[(src, tgt)][:10],
        }
        for (src, tgt), cnt in sorted(edge_counts.items())
        if cnt >= min_edge_weight
    ]

    # Afferent (Ca) = how many modules import this module.
    ca: dict[str, int] = defaultdict(int)
    ce: dict[str, int] = defaultdict(int)
    for edge in edges:
        ca[edge["target"]] += 1
        ce[edge["source"]] += 1

    most_depended_on = sorted(ca.items(), key=lambda x: x[1], reverse=True)[:3]
    most_dependent = sorted(ce.items(), key=lambda x: x[1], reverse=True)[:3]

    mermaid = _build_mermaid(edges)

    logger.info(
        "Cross-module deps: %d modules, %d edges in %s",
        len(modules),
        len(edges),
        repo_path,
    )

    return {
        "status": "success",
        "modules": modules,
        "edges": edges,
        "mermaid": mermaid,
        "stats": {
            "total_modules": len(modules),
            "total_edges": len(edges),
            "most_depended_on": [
                {"module": m, "afferent": c} for m, c in most_depended_on
            ],
            "most_dependent": [{"module": m, "efferent": c} for m, c in most_dependent],
        },
    }


def _build_mermaid(edges: list[dict[str, Any]]) -> str:
    """Render a Mermaid ``graph LR`` diagram from the edge list."""
    if not edges:
        return "graph LR\n  %% No edges to display"

    lines = ["graph LR"]
    for edge in edges:
        src = _sanitize_id(edge["source"])
        tgt = _sanitize_id(edge["target"])
        weight = edge["weight"]
        lines.append(f"  {src} -->|{weight}| {tgt}")

    return "\n".join(lines)


def _sanitize_id(name: str) -> str:
    """Convert a dotted module name to a valid Mermaid node ID."""
    return name.replace(".", "_").replace("-", "_")
