"""Standalone file-processing helpers for RepositoryIndexer.

These functions encapsulate the logic for discovering source files, computing
which files need re-processing, and detecting deleted files.  They are imported
and delegated to by ``RepositoryIndexer``; external callers should go through
the indexer, not import from here directly.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_deepwiki.config import Config
    from local_deepwiki.core.parser import CodeParser
    from local_deepwiki.models import FileInfo, ProgressCallback


def should_include_file(
    file_path: Path,
    repo_path: Path,
    max_file_size: int,
    compiled_patterns: list,
    parser: "CodeParser",
    languages: list[str],
) -> bool:
    """Return True if the file should be included in the index.

    Checks file size, compiled exclude patterns, language support, and whether
    the language is in the configured list.

    Args:
        file_path: Absolute path to the candidate file.
        repo_path: Root of the repository (used to compute the relative path).
        max_file_size: Maximum file size in bytes; larger files are skipped.
        compiled_patterns: Pre-compiled regex patterns for exclude matching.
        parser: CodeParser used to detect the file's language.
        languages: List of language values that are enabled in config.

    Returns:
        True if the file passes all checks and should be indexed.
    """
    rel_path = str(file_path.relative_to(repo_path))

    if any(p.match(rel_path) for p in compiled_patterns):
        return False

    try:
        if file_path.stat().st_size > max_file_size:
            return False
    except OSError:
        return False

    language = parser.detect_language(file_path)
    if language is None:
        return False

    if language.value not in languages:
        return False

    return True


def find_source_files(
    repo_path: Path,
    parser: "CodeParser",
    max_file_size: int,
    skip_dirs: set[str],
    compiled_patterns: list,
    languages: list[str],
) -> list[Path]:
    """Walk the repository and return all indexable source files.

    Uses ``os.walk`` with early directory filtering to avoid traversing excluded
    directories (e.g. ``node_modules``, ``.git``, ``vendor``) entirely.

    Args:
        repo_path: Root of the repository to scan.
        parser: CodeParser used to detect file languages.
        max_file_size: Maximum file size in bytes; larger files are skipped.
        skip_dirs: Directory names (or relative paths) to skip entirely.
        compiled_patterns: Pre-compiled regex patterns for exclude matching.
        languages: List of language values enabled in config.

    Returns:
        List of absolute paths to source files that should be indexed.
    """
    files: list[Path] = []

    for root, dirs, filenames in os.walk(repo_path):
        root_path = Path(root)
        rel_root = root_path.relative_to(repo_path)

        # Early directory filtering — modify dirs in-place to skip subdirs.
        dirs[:] = [
            d
            for d in dirs
            if d not in skip_dirs
            and str(rel_root / d) not in skip_dirs
            and not d.startswith(".")  # Skip hidden directories
        ]

        for filename in filenames:
            file_path = root_path / filename
            if should_include_file(
                file_path,
                repo_path,
                max_file_size,
                compiled_patterns,
                parser,
                languages,
            ):
                files.append(file_path)

    return files


def compute_files_to_process(
    source_files: list[Path],
    parser: "CodeParser",
    repo_path: Path,
    prev_files_by_path: dict[str, "FileInfo"],
) -> tuple[list[Path], list["FileInfo"]]:
    """Determine which source files need (re)processing and which are unchanged.

    Compares the current on-disk state with the previous index using file
    hashes.  Files absent from the previous index or whose hash has changed are
    returned as ``files_to_process``.

    Args:
        source_files: All candidate source files discovered on disk.
        parser: CodeParser used to compute ``FileInfo`` (including hash).
        repo_path: Root of the repository (for relative path computation).
        prev_files_by_path: Mapping from relative path to ``FileInfo`` from
            the previous index.  An empty dict means full rebuild.

    Returns:
        Tuple of (files_to_process, files_unchanged).
        ``files_to_process`` contains paths that must be parsed and embedded.
        ``files_unchanged`` contains ``FileInfo`` objects for unchanged files.
    """
    files_to_process: list[Path] = []
    files_unchanged: list["FileInfo"] = []

    for file_path in source_files:
        file_info = parser.get_file_info(file_path, repo_path)

        if prev_files_by_path:
            prev_file = prev_files_by_path.get(file_info.path)
            if prev_file and prev_file.hash == file_info.hash:
                files_unchanged.append(prev_file)
                continue

        files_to_process.append(file_path)

    return files_to_process, files_unchanged


def detect_deleted_files(
    prev_files_by_path: dict[str, "FileInfo"],
    current_file_paths: set[str],
) -> list[str]:
    """Return relative paths of files that existed in the previous index but are gone.

    Args:
        prev_files_by_path: Mapping from relative path to ``FileInfo`` from
            the previous index.
        current_file_paths: Set of relative paths discovered on disk in this run.

    Returns:
        List of relative file paths that are no longer present on disk.
    """
    return [path for path in prev_files_by_path if path not in current_file_paths]
