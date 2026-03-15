"""Layer dependency analysis.

Pure static analysis that categorizes source files into architectural layers
(web, handlers, services, generators, core, providers, models) and detects
upward dependency violations where lower layers import from higher layers.

No LLM or external service calls — works entirely from the filesystem.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# Layer order: lower number = higher (closer to user).
# Imports should flow downward: web -> handlers -> services -> core -> providers -> models.
# Importing *upward* (e.g. core -> handlers) is a violation.
LAYER_ORDER: dict[str, int] = {
    "web": 0,
    "handlers": 1,
    "services": 2,
    "generators": 3,
    "core": 4,
    "providers": 5,
    "models": 6,
    "root": 3,  # root-level files treated as mid-tier
}

_KNOWN_LAYERS = frozenset(LAYER_ORDER) - {"root"}

# Python import patterns (reused from dependency_graph_data)
_IMPORT_PATTERNS = (
    re.compile(r"^from\s+([\w.]+)\s+import"),
    re.compile(r"^import\s+([\w.]+)"),
)


def categorize_file_layer(file_path: str) -> str:
    """Determine which architectural layer a file belongs to.

    Scans path parts for known layer directory names and returns the first
    match.  Falls back to ``"root"`` for files not under any known layer.

    Args:
        file_path: Relative file path (e.g. ``"core/indexer.py"``).

    Returns:
        Layer name such as ``"core"``, ``"web"``, ``"handlers"``, etc.
    """
    parts = Path(file_path).parts
    for part in parts:
        if part in _KNOWN_LAYERS:
            return part
    return "root"


def _extract_imports(source: str) -> list[str]:
    """Extract top-level module names from Python import statements.

    Returns the first dotted component of each imported module, which
    corresponds to the top-level package directory.
    """
    modules: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        for pattern in _IMPORT_PATTERNS:
            match = pattern.match(stripped)
            if match:
                full_module = match.group(1)
                top_level = full_module.split(".")[0]
                modules.append(top_level)
                break
    return modules


def _resolve_import_layer(module_name: str) -> str | None:
    """Map a top-level import module name to a layer, if it matches one.

    Returns ``None`` for imports that don't correspond to a known layer
    (e.g. stdlib or third-party packages).
    """
    if module_name in _KNOWN_LAYERS:
        return module_name
    return None


def analyze_layer_dependencies(repo_path: Path, project_name: str) -> dict[str, Any]:
    """Scan Python files and detect layer dependency violations.

    Walks all ``.py`` files under *repo_path*, categorizes them into layers,
    parses their import statements, and flags any import that flows *upward*
    (a lower-order layer importing from a higher-order layer).

    Args:
        repo_path: Root directory of the repository to analyze.
        project_name: Project name (currently unused, reserved for future
            package-name stripping).

    Returns:
        A dict with keys:
        - ``layer_file_counts``: ``{layer_name: file_count}``
        - ``layer_edges``: list of ``{from_layer, to_layer, count}`` dicts
        - ``violations``: list of ``{from_layer, to_layer, file, import_module}``
        - ``total_violations``: integer count of violations
    """
    layer_file_counts: dict[str, int] = defaultdict(int)
    edge_counts: dict[tuple[str, str], int] = defaultdict(int)
    violations: list[dict[str, str]] = []

    py_files = sorted(repo_path.rglob("*.py"))

    for py_file in py_files:
        try:
            rel_path = py_file.relative_to(repo_path)
        except ValueError:
            continue

        file_layer = categorize_file_layer(str(rel_path))
        layer_file_counts[file_layer] += 1

        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning("Could not read %s", py_file)
            continue

        imported_modules = _extract_imports(source)
        for module_name in imported_modules:
            target_layer = _resolve_import_layer(module_name)
            if target_layer is None:
                continue
            if target_layer == file_layer:
                # Same-layer import — not an edge or violation
                continue

            edge_counts[(file_layer, target_layer)] += 1

            file_order = LAYER_ORDER.get(file_layer, 3)
            target_order = LAYER_ORDER.get(target_layer, 3)
            if file_order > target_order:
                # Upward dependency: a lower layer imports from a higher layer
                violations.append(
                    {
                        "from_layer": file_layer,
                        "to_layer": target_layer,
                        "file": str(rel_path),
                        "import_module": module_name,
                    }
                )

    layer_edges = [
        {"from_layer": src, "to_layer": tgt, "count": cnt}
        for (src, tgt), cnt in sorted(edge_counts.items())
    ]

    return {
        "layer_file_counts": dict(layer_file_counts),
        "layer_edges": layer_edges,
        "violations": violations,
        "total_violations": len(violations),
    }
