"""Shared path validation utilities to prevent traversal attacks.

Consolidates the repeated resolve-and-check pattern used across handler
modules into reusable helpers.
"""

from __future__ import annotations

from pathlib import Path

from local_deepwiki.errors import ValidationError, path_not_found_error
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


def validate_file_in_repo(repo_path: Path, file_path: str) -> Path:
    """Validate that *file_path* resolves inside *repo_path* and exists.

    Args:
        repo_path: Resolved repository root (must already be ``.resolve()``'d).
        file_path: Relative file path supplied by the caller.

    Returns:
        The resolved absolute path to the file.

    Raises:
        ValidationError: If the path escapes the repo or does not exist.
    """
    resolved = (repo_path / file_path).resolve()
    if not resolved.is_relative_to(repo_path):
        raise ValidationError(
            message="Invalid file path: path traversal not allowed",
            hint="The file path must be within the repository.",
            field="file_path",
            value=file_path,
        )
    if not resolved.exists():
        raise path_not_found_error(file_path, "file")
    return resolved


def validate_sub_path(
    root: Path,
    sub_path: str,
    *,
    field: str = "page",
    value: str | None = None,
    hint: str = "The path must be within the parent directory.",
) -> Path:
    """Validate that *sub_path* resolves inside *root* (no existence check).

    A more general helper used for wiki-page paths and similar cases where
    the file may not exist yet.

    Args:
        root: Resolved root directory.
        sub_path: Relative path supplied by the caller.
        field: Field name for the error payload.
        value: Value for the error payload (defaults to *sub_path*).
        hint: Human-readable hint for the error message.

    Returns:
        The resolved absolute path.

    Raises:
        ValidationError: If the path escapes *root*.
    """
    resolved = (root / sub_path).resolve()
    if not resolved.is_relative_to(root):
        raise ValidationError(
            message="Path traversal not allowed",
            hint=hint,
            field=field,
            value=value if value is not None else sub_path,
        )
    return resolved


def find_deepwiki_dirs(base_path: Path | None = None) -> list[Path]:
    """Find ``.deepwiki`` directories under *base_path* (or cwd).

    Args:
        base_path: Directory to search. Defaults to ``Path.cwd()``.

    Returns:
        Sorted list of resolved paths to ``.deepwiki`` directories.
    """
    root = (base_path or Path.cwd()).resolve()
    results: list[Path] = []
    try:
        for candidate in root.rglob(".deepwiki"):
            if candidate.is_dir():
                results.append(candidate.resolve())
    except (PermissionError, OSError) as e:
        logger.warning("Error scanning for wiki directories: %s", e)
    return sorted(results)
