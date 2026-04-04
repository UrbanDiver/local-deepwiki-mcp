"""Duplication detection: Type 1 (exact) and Type 2 (structural) clone finding.

Uses line-based fingerprinting for exact clones and tree-sitter AST
node-type sequences for structural clones.
No LLM calls -- pure computation on source code.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from local_deepwiki.core.chunk_extractors import FUNCTION_NODE_TYPES
from local_deepwiki.core.parser.ast_utils import find_nodes_by_type, get_node_name
from local_deepwiki.core.parser.code_parser import CodeParser
from local_deepwiki.generators.analysis.source_filter import iter_python_files
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

_MIN_CLONE_LINES = 6
_MIN_AST_NODES = 10  # minimum AST nodes for Type 2 to avoid trivially small functions


def _normalize_line(line: str) -> str | None:
    """Normalize a source line for fingerprinting.

    Strips leading/trailing whitespace, returns None for blank lines
    and comment-only lines.
    """
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("#"):
        return None
    return stripped


def _collect_node_types(node: Any) -> list[str]:
    """Walk all descendants depth-first and collect node type strings."""
    types: list[str] = [node.type]
    for child in node.children:
        types.extend(_collect_node_types(child))
    return types


def _build_fingerprints(
    repo_path: Path,
    min_lines: int,
    exclude_tests: bool,
) -> dict[int, list[dict[str, Any]]]:
    """Build hash -> location mapping from all files.

    Reads each file, normalizes lines, and computes sliding-window hashes.
    Returns a dict mapping fingerprint hash to list of location dicts.
    """
    files = iter_python_files(repo_path, exclude_tests=exclude_tests)
    fingerprints: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for full_path, rel_path in files:
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning("Cannot read %s, skipping", full_path)
            continue

        raw_lines = content.splitlines()

        # Build list of (original_line_number, normalized_text)
        normalized: list[tuple[int, str]] = []
        for i, line in enumerate(raw_lines, start=1):
            norm = _normalize_line(line)
            if norm is not None:
                normalized.append((i, norm))

        if len(normalized) < min_lines:
            continue

        # Sliding window over normalized lines
        for start_idx in range(len(normalized) - min_lines + 1):
            window = normalized[start_idx : start_idx + min_lines]
            key = hash(tuple(entry[1] for entry in window))
            fingerprints[key].append(
                {
                    "file": str(rel_path),
                    "start_line": window[0][0],
                    "end_line": window[-1][0],
                }
            )

    return fingerprints


def _deduplicate_clone_group(
    instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove overlapping windows from a clone group, return unique instances."""
    seen: set[tuple[str, int]] = set()
    unique: list[dict[str, Any]] = []
    for inst in instances:
        loc = (inst["file"], inst["start_line"])
        if loc not in seen:
            seen.add(loc)
            unique.append(inst)
    return unique


def detect_type1_clones(
    repo_path: Path,
    *,
    min_lines: int = _MIN_CLONE_LINES,
    exclude_tests: bool = True,
) -> list[dict[str, Any]]:
    """Detect exact code clones (Type 1) using line-based fingerprinting.

    Args:
        repo_path: Root of the repository to scan.
        min_lines: Minimum consecutive lines for a clone block.
        exclude_tests: Skip test files when True.

    Returns:
        List of clone groups sorted by number of instances descending.
    """
    repo_path = Path(repo_path)
    fingerprints = _build_fingerprints(repo_path, min_lines, exclude_tests)

    # Filter to groups with 2+ instances and deduplicate overlapping windows
    clone_groups: list[dict[str, Any]] = []
    for fp_hash, instances in fingerprints.items():
        if len(instances) < 2:
            continue

        unique_instances = _deduplicate_clone_group(instances)
        if len(unique_instances) < 2:
            continue

        files_in_group = {inst["file"] for inst in unique_instances}
        scope = "intra_file" if len(files_in_group) == 1 else "inter_file"

        clone_groups.append(
            {
                "fingerprint": hex(fp_hash & 0xFFFFFFFFFFFFFFFF),
                "line_count": min_lines,
                "instances": unique_instances,
                "scope": scope,
            }
        )

    # Sort by number of instances descending
    clone_groups.sort(key=lambda g: len(g["instances"]), reverse=True)
    return clone_groups


def detect_type2_clones(
    repo_path: Path,
    *,
    exclude_tests: bool = True,
) -> list[dict[str, Any]]:
    """Detect structural clones (Type 2) by comparing function AST structure.

    Args:
        repo_path: Root of the repository to scan.
        exclude_tests: Skip test files when True.

    Returns:
        List of clone groups sorted by group size descending.
    """
    repo_path = Path(repo_path)
    parser = CodeParser()
    files = iter_python_files(repo_path, exclude_tests=exclude_tests)

    # Build mapping: structural_hash -> list of function info dicts
    structural_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for full_path, rel_path in files:
        result = parser.parse_file(full_path)
        if result is None:
            continue

        root, language, source = result
        fn_types = FUNCTION_NODE_TYPES.get(language)
        if fn_types is None:
            continue

        fn_nodes = find_nodes_by_type(root, fn_types)
        for fn_node in fn_nodes:
            node_types = _collect_node_types(fn_node)
            if len(node_types) < _MIN_AST_NODES:
                continue

            struct_hash = hash(tuple(node_types))
            fn_name = get_node_name(fn_node, source, language) or "<anonymous>"
            structural_groups[struct_hash].append(
                {
                    "file": str(rel_path),
                    "function": fn_name,
                    "line": fn_node.start_point[0] + 1,
                    "node_count": len(node_types),
                }
            )

    # Filter to groups with 2+ members
    clone_groups: list[dict[str, Any]] = []
    for s_hash, instances in structural_groups.items():
        if len(instances) < 2:
            continue
        clone_groups.append(
            {
                "structural_hash": hex(s_hash & 0xFFFFFFFFFFFFFFFF),
                "node_count": instances[0]["node_count"],
                "instances": [
                    {
                        "file": inst["file"],
                        "function": inst["function"],
                        "line": inst["line"],
                    }
                    for inst in instances
                ],
            }
        )

    # Sort by group size descending
    clone_groups.sort(key=lambda g: len(g["instances"]), reverse=True)
    return clone_groups


def analyze_duplication(
    repo_path: Path,
    *,
    min_lines: int = _MIN_CLONE_LINES,
    top_n: int = 20,
    exclude_tests: bool = True,
) -> dict[str, Any]:
    """Run both detection types and compute summary statistics.

    Args:
        repo_path: Root of the repository to scan.
        min_lines: Minimum consecutive lines for Type 1 clones.
        top_n: Maximum number of clone groups to return per type.
        exclude_tests: Skip test files when True.

    Returns:
        Dict with status, clone groups, and summary stats.
    """
    repo_path = Path(repo_path)

    # Compute total source lines across all scanned files
    files = iter_python_files(repo_path, exclude_tests=exclude_tests)
    total_lines = 0
    for full_path, _rel_path in files:
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            total_lines += len(content.splitlines())
        except OSError:
            continue

    # Run both detectors
    type1_clones = detect_type1_clones(
        repo_path, min_lines=min_lines, exclude_tests=exclude_tests
    )
    type2_clones = detect_type2_clones(repo_path, exclude_tests=exclude_tests)

    # Compute duplicated lines:
    # Each instance contributes line_count lines, but one copy per group is "original"
    duplicated_lines = sum(
        group["line_count"] * (len(group["instances"]) - 1) for group in type1_clones
    )

    largest_clone_lines = max(
        (group["line_count"] for group in type1_clones), default=0
    )

    duplication_ratio = duplicated_lines / total_lines if total_lines > 0 else 0.0

    inter_file_type1 = [g for g in type1_clones if g.get("scope") == "inter_file"]
    inter_file_duplicated_lines = sum(
        group["line_count"] * (len(group["instances"]) - 1)
        for group in inter_file_type1
    )
    inter_file_ratio = (
        inter_file_duplicated_lines / total_lines if total_lines > 0 else 0.0
    )

    return {
        "status": "success",
        "type1_clones": type1_clones[:top_n],
        "type2_clones": type2_clones[:top_n],
        "stats": {
            "total_lines": total_lines,
            "duplicated_lines": duplicated_lines,
            "duplication_ratio": duplication_ratio,
            "inter_file_duplication_ratio": inter_file_ratio,
            "type1_clone_groups": len(type1_clones),
            "type2_clone_groups": len(type2_clones),
            "inter_file_clone_groups": len(inter_file_type1) + len(type2_clones),
            "largest_clone_lines": largest_clone_lines,
        },
    }
