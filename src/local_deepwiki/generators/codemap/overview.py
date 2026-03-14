"""Overview mode: module-level architecture graph with LLM labeling."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True, slots=True)
class OverviewModule:
    """A module (directory-level group) in the architecture overview."""

    id: str
    label: str
    description: str
    files: tuple[str, ...]
    function_count: int
    hub_functions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OverviewEdge:
    """A relationship between two modules."""

    source: str
    target: str
    weight: int
    description: str


@dataclass(frozen=True, slots=True)
class OverviewResult:
    """Complete overview graph with modules, edges, and summary."""

    modules: tuple[OverviewModule, ...]
    edges: tuple[OverviewEdge, ...]
    summary: str


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def cluster_files_into_modules(
    files: dict[str, list[str]],
) -> list[dict[str, object]]:
    """Group files by parent directory into raw module dicts.

    Args:
        files: mapping of file_path -> list of function names.

    Returns:
        List of dicts with keys: id, dir_label, files.
    """
    if not files:
        return []

    dir_groups: dict[str, list[str]] = defaultdict(list)
    for fpath in files:
        parent = str(PurePosixPath(fpath).parent)
        dir_groups[parent].append(fpath)

    modules: list[dict[str, object]] = []
    for dir_path, dir_files in sorted(dir_groups.items()):
        label = PurePosixPath(dir_path).name or dir_path
        modules.append(
            {
                "id": dir_path,
                "dir_label": label,
                "files": sorted(dir_files),
            }
        )
    return modules


def compute_module_metadata(
    raw_modules: list[dict[str, object]],
    file_functions: dict[str, list[str]],
    edges: list[dict[str, str]],
) -> list[OverviewModule]:
    """Enrich raw module dicts with function counts and hub functions.

    Args:
        raw_modules: output of cluster_files_into_modules.
        file_functions: file_path -> list of function names.
        edges: list of edge dicts with source, target, source_file, target_file.

    Returns:
        List of OverviewModule (without LLM descriptions — empty string).
    """
    # Build degree map across all functions
    degree: dict[str, int] = defaultdict(int)
    for edge in edges:
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1

    result: list[OverviewModule] = []
    for mod in raw_modules:
        mod_files = mod["files"]  # type: ignore[assignment]
        func_count = 0
        mod_functions: list[str] = []
        for fpath in mod_files:  # type: ignore[union-attr]
            funcs = file_functions.get(str(fpath), [])
            func_count += len(funcs)
            mod_functions.extend(funcs)

        # Top 3 by degree
        hub = sorted(mod_functions, key=lambda f: degree.get(f, 0), reverse=True)[:3]

        result.append(
            OverviewModule(
                id=str(mod["id"]),
                label=str(mod["dir_label"]),
                description="",
                files=tuple(str(f) for f in mod_files),  # type: ignore[union-attr]
                function_count=func_count,
                hub_functions=tuple(hub),
            )
        )
    return result
