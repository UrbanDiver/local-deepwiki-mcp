"""Overview mode: module-level architecture graph with LLM labeling."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# LLM-assisted overview builder
# ---------------------------------------------------------------------------

_OVERVIEW_PROMPT_TEMPLATE = """\
You are analyzing a codebase's architecture. Below are the detected modules \
(directory-level groups) with their files and key functions.

{module_descriptions}

Respond with a JSON object containing:
- "modules": a mapping of module_id -> one-line description of what the module does
- "edges": a mapping of "source_id -> target_id" -> description of the relationship \
(only include edges where modules clearly depend on each other)
- "summary": a 1-2 sentence summary of the overall architecture

Respond ONLY with valid JSON, no markdown fencing.
"""


def _build_prompt(modules: list[OverviewModule]) -> str:
    """Build the LLM prompt from computed modules."""
    parts: list[str] = []
    for mod in modules:
        files_str = ", ".join(mod.files) if mod.files else "(no files)"
        hubs_str = ", ".join(mod.hub_functions) if mod.hub_functions else "(none)"
        parts.append(
            f"Module '{mod.id}' (label: {mod.label}): "
            f"{mod.function_count} functions, files: {files_str}, "
            f"hub functions: {hubs_str}"
        )
    return _OVERVIEW_PROMPT_TEMPLATE.format(module_descriptions="\n".join(parts))


def _apply_llm_descriptions(
    modules: list[OverviewModule],
    llm_data: dict,
) -> tuple[tuple[OverviewModule, ...], tuple[OverviewEdge, ...], str]:
    """Apply LLM-generated descriptions to modules and build edges."""
    llm_modules = llm_data.get("modules", {})
    llm_edges = llm_data.get("edges", {})
    summary = llm_data.get("summary", "")

    enriched: list[OverviewModule] = []
    for mod in modules:
        desc = llm_modules.get(mod.id, mod.description)
        enriched.append(
            OverviewModule(
                id=mod.id,
                label=mod.label,
                description=str(desc),
                files=mod.files,
                function_count=mod.function_count,
                hub_functions=mod.hub_functions,
            )
        )

    edges: list[OverviewEdge] = []
    for edge_key, edge_desc in llm_edges.items():
        parts = edge_key.split(" -> ", 1)
        if len(parts) == 2:
            edges.append(
                OverviewEdge(
                    source=parts[0].strip(),
                    target=parts[1].strip(),
                    weight=1,
                    description=str(edge_desc),
                )
            )

    return tuple(enriched), tuple(edges), str(summary)


async def build_overview(
    vector_store: object,
    repo_path: str,
    llm: object,
) -> OverviewResult:
    """Build a module-level architecture overview with LLM labeling.

    Args:
        vector_store: VectorStore instance with get_all_chunks().
        repo_path: Path to the repository root.
        llm: LLM provider with async generate() method.

    Returns:
        OverviewResult with modules, edges, and summary.
    """
    chunks = vector_store.get_all_chunks()  # type: ignore[union-attr]

    if not chunks:
        return OverviewResult(modules=(), edges=(), summary="")

    # Build file -> functions mapping and call edges from chunks
    file_functions: dict[str, list[str]] = defaultdict(list)
    call_edges: list[dict[str, str]] = []

    chunk_file_map: dict[str, str] = {}
    for chunk in chunks:
        if getattr(chunk, "chunk_type", None) and chunk.chunk_type.value == "function":
            file_functions[chunk.file_path].append(chunk.name)
            chunk_file_map[chunk.name] = chunk.file_path

    for chunk in chunks:
        for callee in getattr(chunk, "calls", []):
            if callee in chunk_file_map:
                call_edges.append(
                    {
                        "source": chunk.name,
                        "target": callee,
                        "source_file": chunk.file_path,
                        "target_file": chunk_file_map[callee],
                    }
                )

    # Cluster and compute metadata
    raw_modules = cluster_files_into_modules(dict(file_functions))
    modules = compute_module_metadata(raw_modules, dict(file_functions), call_edges)

    # LLM labeling
    try:
        prompt = _build_prompt(modules)
        response = await llm.generate(prompt)  # type: ignore[union-attr]
        llm_data = json.loads(response)
        enriched_modules, edges, summary = _apply_llm_descriptions(modules, llm_data)
    except Exception:
        logger.warning("LLM labeling failed, returning modules without descriptions")
        enriched_modules = tuple(modules)
        edges = ()
        summary = f"Architecture overview with {len(modules)} modules"

    return OverviewResult(
        modules=enriched_modules,
        edges=edges,
        summary=summary,
    )
