"""Onboarding guide generator for repository newcomers.

Scans a repository to produce a structured onboarding guide covering
project overview, entry points, key modules, test layout, and configuration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.generators.dir_tree import get_directory_tree
from local_deepwiki.generators.manifest import ProjectManifest, get_cached_manifest

# Well-known entry point filenames
ENTRY_POINT_PATTERNS: tuple[str, ...] = (
    "__main__.py",
    "main.py",
    "app.py",
    "server.py",
    "cli.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
)

# Well-known configuration files and directories
CONFIG_PATTERNS: tuple[str, ...] = (
    ".github",
    ".gitlab-ci.yml",
    "Dockerfile",
    "docker-compose.yml",
    "Makefile",
    ".pre-commit-config.yaml",
    "pyproject.toml",
    "setup.cfg",
    "tox.ini",
    ".eslintrc",
    "tsconfig.json",
    "Cargo.toml",
    "go.mod",
)

# Maximum key modules by detail level
_KEY_MODULE_LIMITS: dict[str, int] = {
    "summary": 0,
    "standard": 5,
    "full": 8,
}

# Tree depth by detail level
_TREE_DEPTH: dict[str, int] = {
    "summary": 1,
    "standard": 3,
    "full": 5,
}


def _find_entry_points(repo_path: Path) -> list[Path]:
    """Discover entry point files by matching known filename patterns.

    Returns paths relative to repo_path, sorted alphabetically.
    """
    found: list[Path] = []
    for pattern in ENTRY_POINT_PATTERNS:
        for match in sorted(repo_path.rglob(pattern)):
            try:
                relative = match.relative_to(repo_path)
            except ValueError:
                continue
            # Skip hidden directories and common non-source locations
            parts = relative.parts
            if any(part.startswith(".") or part == "__pycache__" for part in parts):
                continue
            found.append(relative)
    return sorted(found)


def _find_key_modules(repo_path: Path, limit: int) -> list[dict[str, Any]]:
    """Identify key source modules by size (line count).

    Returns up to *limit* modules sorted by descending line count.
    Each entry has ``path`` (relative) and ``lines``.
    """
    if limit <= 0:
        return []

    source_extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}
    modules: list[dict[str, Any]] = []

    for ext in source_extensions:
        for filepath in repo_path.rglob(f"*{ext}"):
            try:
                relative = filepath.relative_to(repo_path)
            except ValueError:
                continue
            parts = relative.parts
            if any(
                part.startswith(".") or part in ("__pycache__", "node_modules")
                for part in parts
            ):
                continue
            # Skip test files for key modules listing
            if any(part.startswith("test") for part in parts):
                continue
            try:
                line_count = len(filepath.read_text(errors="replace").splitlines())
            except OSError:
                continue
            modules.append({"path": relative, "lines": line_count})

    modules.sort(key=lambda m: m["lines"], reverse=True)
    return modules[:limit]


def _find_test_layout(repo_path: Path) -> list[Path]:
    """Find test directories and test files.

    Returns relative paths to directories containing test files.
    """
    test_dirs: set[Path] = set()
    test_patterns = ("test_*.py", "*_test.py", "test_*.ts", "*.test.ts", "*.spec.ts")

    for pattern in test_patterns:
        for match in repo_path.rglob(pattern):
            try:
                relative = match.relative_to(repo_path)
            except ValueError:
                continue
            parts = relative.parts
            if any(part.startswith(".") or part == "__pycache__" for part in parts):
                continue
            # Add the parent directory of the test file
            if len(relative.parts) > 1:
                test_dirs.add(Path(*relative.parts[:-1]))
            else:
                test_dirs.add(Path("."))

    return sorted(test_dirs)


def _find_config_files(repo_path: Path) -> list[Path]:
    """Discover configuration files and directories matching known patterns.

    Returns relative paths sorted alphabetically.
    """
    found: list[Path] = []
    for pattern in CONFIG_PATTERNS:
        candidate = repo_path / pattern
        if candidate.exists():
            found.append(Path(pattern))
    return sorted(found)


def generate_onboarding_guide(
    repo_path: Path, *, detail_level: str = "standard"
) -> dict[str, Any]:
    """Scan a repository and return structured onboarding data.

    Args:
        repo_path: Path to the repository root.
        detail_level: One of ``"summary"``, ``"standard"``, or ``"full"``.

    Returns:
        Dictionary with keys: ``manifest``, ``directory_tree``,
        ``entry_points``, ``key_modules``, ``test_layout``,
        ``config_files``, ``detail_level``.
    """
    tree_depth = _TREE_DEPTH.get(detail_level, 3)
    module_limit = _KEY_MODULE_LIMITS.get(detail_level, 5)

    manifest = get_cached_manifest(repo_path)
    directory_tree = get_directory_tree(repo_path, max_depth=tree_depth)
    entry_points = _find_entry_points(repo_path)
    key_modules = _find_key_modules(repo_path, limit=module_limit)
    test_layout = _find_test_layout(repo_path)
    config_files = _find_config_files(repo_path)

    return {
        "manifest": manifest,
        "directory_tree": directory_tree,
        "entry_points": entry_points,
        "key_modules": key_modules,
        "test_layout": test_layout,
        "config_files": config_files,
        "detail_level": detail_level,
    }


def _format_project_overview(manifest: ProjectManifest) -> str:
    """Format the Project Overview section."""
    lines = ["## Project Overview", ""]
    if manifest.name:
        lines.append(f"**{manifest.name}**")
        if manifest.version:
            lines[-1] += f" v{manifest.version}"
        lines.append("")
    if manifest.description:
        lines.append(manifest.description)
        lines.append("")
    tech_summary = manifest.get_tech_stack_summary()
    if tech_summary and tech_summary != "No package manifest found.":
        lines.append("### Tech Stack")
        lines.append("")
        lines.append(tech_summary)
        lines.append("")
    return "\n".join(lines)


def _format_getting_started(manifest: ProjectManifest) -> str:
    """Format the Getting Started section."""
    lines = ["## Getting Started", ""]
    if manifest.scripts:
        lines.append("Available scripts:")
        lines.append("")
        for name, cmd in sorted(manifest.scripts.items()):
            lines.append(f"- `{name}`: `{cmd}`")
        lines.append("")
    elif manifest.language:
        lines.append(f"This is a **{manifest.language}** project.")
        if manifest.manifest_files:
            lines.append(
                f"Check `{manifest.manifest_files[0]}` for build/run instructions."
            )
        lines.append("")
    else:
        lines.append(
            "No package manifest detected. Check the repository for setup instructions."
        )
        lines.append("")
    return "\n".join(lines)


def _format_repository_layout(directory_tree: str) -> str:
    """Format the Repository Layout section."""
    return "\n".join(
        [
            "## Repository Layout",
            "",
            "```",
            directory_tree,
            "```",
            "",
        ]
    )


def _format_entry_points(entry_points: list[Path]) -> str:
    """Format the Entry Points section."""
    lines = ["## Entry Points", ""]
    if entry_points:
        for ep in entry_points:
            lines.append(f"- `{ep}`")
    else:
        lines.append("No standard entry points detected.")
    lines.append("")
    return "\n".join(lines)


def _format_key_modules(key_modules: list[dict[str, Any]]) -> str:
    """Format the Key Modules section."""
    lines = ["## Key Modules", ""]
    if key_modules:
        lines.append("Largest source files (by line count):")
        lines.append("")
        for mod in key_modules:
            lines.append(f"- `{mod['path']}` ({mod['lines']} lines)")
    else:
        lines.append("No source modules detected.")
    lines.append("")
    return "\n".join(lines)


def _format_testing(test_layout: list[Path]) -> str:
    """Format the Testing section."""
    lines = ["## Testing", ""]
    if test_layout:
        lines.append("Test directories:")
        lines.append("")
        for td in test_layout:
            display = str(td) if str(td) != "." else "(root)"
            lines.append(f"- `{display}`")
    else:
        lines.append("No test files detected.")
    lines.append("")
    return "\n".join(lines)


def _format_configuration(config_files: list[Path]) -> str:
    """Format the Configuration section."""
    lines = ["## Configuration", ""]
    if config_files:
        for cf in config_files:
            lines.append(f"- `{cf}`")
    else:
        lines.append("No standard configuration files detected.")
    lines.append("")
    return "\n".join(lines)


def format_onboarding_guide(
    data: dict[str, Any], *, detail_level: str = "standard"
) -> str:
    """Format structured onboarding data into a markdown narrative.

    Args:
        data: Structured data from :func:`generate_onboarding_guide`.
        detail_level: One of ``"summary"``, ``"standard"``, or ``"full"``.

    Returns:
        Markdown string with appropriate sections for the detail level.
    """
    manifest: ProjectManifest = data["manifest"]
    sections = ["# Onboarding Guide", ""]

    # Always included: overview, getting started, layout
    sections.append(_format_project_overview(manifest))
    sections.append(_format_getting_started(manifest))
    sections.append(_format_repository_layout(data["directory_tree"]))

    if detail_level == "summary":
        return "\n".join(sections)

    # Standard and full: entry points, key modules, testing
    sections.append(_format_entry_points(data["entry_points"]))
    sections.append(_format_key_modules(data["key_modules"]))
    sections.append(_format_testing(data["test_layout"]))

    # Full only: configuration
    if detail_level == "full":
        sections.append(_format_configuration(data["config_files"]))

    return "\n".join(sections)
