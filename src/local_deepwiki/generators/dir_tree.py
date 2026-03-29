"""Directory tree generation utilities.

Generates a formatted directory tree structure for repositories,
respecting ``.gitignore`` rules when inside a git repository.
"""

from __future__ import annotations

from pathlib import Path


def _load_gitignored_paths(repo_path: Path) -> set[str]:
    """Load the set of gitignored top-level entries using git.

    Uses ``git ls-files --others --ignored --exclude-standard --directory``
    to discover ignored directories/files, returning their names so the
    directory tree can skip them.

    Args:
        repo_path: Path to the repository root.

    Returns:
        Set of names (relative to *repo_path*) that are gitignored.
        Returns an empty set if not a git repo or if the command fails.
    """
    import subprocess  # noqa: PLC0415

    try:
        result = subprocess.run(
            [
                "git",
                "ls-files",
                "--others",
                "--ignored",
                "--exclude-standard",
                "--directory",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return set()
        ignored: set[str] = set()
        for line in result.stdout.splitlines():
            # git outputs trailing '/' for directories -- strip it
            name = line.strip().rstrip("/")
            if name:
                # Only keep top-level entries (no path separators)
                if "/" not in name:
                    ignored.add(name)
        return ignored
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return set()


# Common directories/files to always skip
_ALWAYS_SKIP: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        ".env",
        ".idea",
        ".vscode",
        "dist",
        "build",
        "target",
        ".egg-info",
        "*.egg",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".ruff_cache",
    }
)


def _should_skip_entry(name: str, gitignored: set[str]) -> bool:
    """Return True if a directory entry should be excluded from the tree."""
    if name in _ALWAYS_SKIP or name in gitignored:
        return True
    if name.startswith("."):
        return True
    # Skip names that look like Python repr strings (e.g. MagicMock dirs)
    if name.startswith(("<", "'", '"')):
        return True
    return False


def _traverse_directory(
    path: Path,
    prefix: str,
    depth: int,
    max_depth: int,
    max_items: int,
    gitignored: set[str],
    lines: list[str],
    items_shown_ref: list[int],
) -> None:
    """Recursively traverse *path* and append tree lines to *lines*.

    Uses a single-element list *items_shown_ref* to pass the mutable
    counter across recursive calls without a nonlocal closure.
    """
    if depth > max_depth or items_shown_ref[0] >= max_items:
        return

    try:
        items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
    except PermissionError:
        return

    items = [i for i in items if not _should_skip_entry(i.name, gitignored)]

    for i, item in enumerate(items):
        if items_shown_ref[0] >= max_items:
            lines.append(f"{prefix}...")
            return

        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        new_prefix = prefix + ("    " if is_last else "│   ")

        if item.is_dir():
            lines.append(f"{prefix}{connector}{item.name}/")
        else:
            lines.append(f"{prefix}{connector}{item.name}")
        items_shown_ref[0] += 1

        if item.is_dir():
            _traverse_directory(
                item,
                new_prefix,
                depth + 1,
                max_depth,
                max_items,
                gitignored,
                lines,
                items_shown_ref,
            )


def get_directory_tree(repo_path: Path, max_depth: int = 3, max_items: int = 50) -> str:
    """Generate a directory tree structure for the repository.

    Respects ``.gitignore`` when inside a git repository so that build
    artifacts, coverage reports, and other non-source directories are
    excluded.  Falls back to a hardcoded skip-list for non-git repos.

    Args:
        repo_path: Path to repository root.
        max_depth: Maximum depth to traverse.
        max_items: Maximum total items to include.

    Returns:
        Formatted directory tree string.
    """
    gitignored = _load_gitignored_paths(repo_path)
    lines: list[str] = [f"{repo_path.name}/"]
    items_shown_ref = [1]  # count root entry

    _traverse_directory(
        repo_path, "", 1, max_depth, max_items, gitignored, lines, items_shown_ref
    )

    return "\n".join(lines)
