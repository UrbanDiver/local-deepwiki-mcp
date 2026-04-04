"""Bug detection orchestrator.

Walks repository source files, runs matching bug detectors, and collects
findings. Mirrors the design_smells.py analysis pattern.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from local_deepwiki.core.parser import CodeParser
from local_deepwiki.generators.analysis.bug_patterns import (
    CONFIDENCE_ORDER,
    BugConfidence,
    BugFinding,
    PATTERNS,
)
from local_deepwiki.generators.analysis.source_filter import iter_source_files
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Language mapping (extension -> bug-pattern language string)
# ---------------------------------------------------------------------------
_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "c_sharp",
    ".kt": "kotlin",
    ".swift": "swift",
    ".rb": "ruby",
    ".php": "php",
}

# ---------------------------------------------------------------------------
# AST node types eligible for per-node scanning
# ---------------------------------------------------------------------------
_SCANNABLE_TYPES = frozenset(
    {
        "function_definition",
        "function_declaration",
        "method_definition",
        "method_declaration",
        "arrow_function",
        "function_item",
        "class_definition",
        "class_declaration",
        "struct_item",
        "impl_item",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _collect_scannable_nodes(node: Any) -> list[Any]:
    """Recursively collect AST nodes whose type is in _SCANNABLE_TYPES."""
    results: list[Any] = []

    def _visit(n: Any) -> None:
        if n.type in _SCANNABLE_TYPES:
            results.append(n)
        for child in n.children:
            _visit(child)

    _visit(node)
    return results


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def analyze_bugs(
    repo_path: Path,
    min_confidence: str = "medium",
    languages: list[str] | None = None,
    exclude_tests: bool = True,
    file_path: str | None = None,
    top_n: int = 50,
) -> dict[str, Any]:
    """Scan *repo_path* for bug patterns.

    Args:
        repo_path: Root of the repository to scan.
        min_confidence: Minimum confidence to include (``"low"``,
            ``"medium"``, ``"high"``).
        languages: Optional list of language strings to restrict scanning.
        exclude_tests: When ``True``, skip test files.
        file_path: When set, scope scanning to this single file
            (relative to *repo_path*).
        top_n: Maximum findings to return.

    Returns:
        A dict with ``status``, ``findings``, and summary keys.
    """
    # -- Validate min_confidence ------------------------------------------------
    try:
        min_conf_enum = BugConfidence(min_confidence)
    except ValueError:
        return {
            "status": "error",
            "message": (
                f"Invalid min_confidence '{min_confidence}'. "
                "Valid values: low, medium, high"
            ),
        }
    min_conf_level = CONFIDENCE_ORDER[min_conf_enum]

    # -- Filter patterns by confidence and language ----------------------------
    language_set = frozenset(languages) if languages else None

    active_patterns = [
        p
        for p in PATTERNS
        if CONFIDENCE_ORDER[p.confidence] >= min_conf_level
        and (language_set is None or p.languages & language_set)
    ]

    # -- Collect source files --------------------------------------------------
    if file_path is not None:
        full = repo_path / file_path
        if full.is_file():
            source_files = [(full, Path(file_path))]
        else:
            source_files = []
    else:
        source_files = iter_source_files(repo_path, exclude_tests=exclude_tests)

    # -- Scan each file --------------------------------------------------------
    all_findings: list[BugFinding] = []
    files_scanned = 0
    parser = CodeParser()

    for full_path, rel_path in source_files:
        lang = _EXT_TO_LANG.get(full_path.suffix)
        if lang is None:
            continue

        # Skip if language filter is active and this file's language is excluded
        if language_set is not None and lang not in language_set:
            continue

        # Filter patterns to those matching this file's language
        file_patterns = [p for p in active_patterns if lang in p.languages]
        if not file_patterns:
            files_scanned += 1
            continue

        parse_result = parser.parse_file(full_path)
        if parse_result is None:
            continue

        root_node, _lang_enum, src_bytes = parse_result
        files_scanned += 1

        scannable_nodes = _collect_scannable_nodes(root_node)

        for pattern in file_patterns:
            for node in scannable_nodes:
                findings = pattern.detect(node, src_bytes)
                for finding in findings:
                    all_findings.append(
                        BugFinding(
                            pattern=pattern.name,
                            file=str(rel_path),
                            line=finding["line"],
                            confidence=pattern.confidence.value,
                            message=finding["message"],
                            snippet=finding["snippet"],
                        )
                    )

    # -- Sort: high confidence first, then file, then line ---------------------
    all_findings.sort(
        key=lambda f: (
            -CONFIDENCE_ORDER.get(BugConfidence(f["confidence"]), 0),
            f["file"],
            f["line"],
        )
    )

    # -- Apply top_n limit -----------------------------------------------------
    returned_findings = all_findings[:top_n]

    # -- Build summary counters ------------------------------------------------
    by_confidence: dict[str, int] = Counter(f["confidence"] for f in all_findings)
    by_pattern: dict[str, int] = Counter(f["pattern"] for f in all_findings)

    logger.info(
        "Bug detection: %d findings in %d files (%d patterns checked) in %s",
        len(all_findings),
        files_scanned,
        len(active_patterns),
        repo_path,
    )

    return {
        "status": "success",
        "total_findings": len(all_findings),
        "returned": len(returned_findings),
        "by_confidence": dict(by_confidence),
        "by_pattern": dict(by_pattern),
        "findings": returned_findings,
        "patterns_checked": len(active_patterns),
        "files_scanned": files_scanned,
    }
