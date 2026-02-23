"""Package manifest parser for extracting project metadata.

Parses various package manifest formats to extract factual project information
that can ground LLM documentation generation and reduce hallucinations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

# Re-export extracted directory tree utilities for backward compatibility
from local_deepwiki.generators.dir_tree import (  # noqa: F401
    _load_gitignored_paths,
    get_directory_tree,
)

# Re-export extracted parser functions for backward compatibility
from local_deepwiki.generators.manifest_parsers import (  # noqa: F401
    _parse_build_gradle,
    _parse_cargo_toml,
    _parse_gemfile,
    _parse_go_mod,
    _parse_package_json,
    _parse_pom_xml,
    _parse_pyproject_toml,
    _parse_python_dep,
    _parse_requirements_txt,
    _parse_setup_py,
)

logger = get_logger(__name__)


# Manifest files to check for caching
MANIFEST_FILES = [
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Gemfile",
]


@dataclass(slots=True)
class ManifestCacheEntry:
    """Cache entry storing manifest data and file modification times."""

    manifest_data: dict[str, Any]
    file_mtimes: dict[str, float]  # filename -> mtime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "manifest_data": self.manifest_data,
            "file_mtimes": self.file_mtimes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManifestCacheEntry":
        """Create from dictionary."""
        return cls(
            manifest_data=data.get("manifest_data", {}),
            file_mtimes=data.get("file_mtimes", {}),
        )


@dataclass(slots=True)
class ProjectManifest:
    """Extracted project metadata from package manifests."""

    name: str | None = None
    version: str | None = None
    description: str | None = None
    language: str | None = None
    language_version: str | None = None

    # Dependencies
    dependencies: dict[str, str] = field(default_factory=dict)
    dev_dependencies: dict[str, str] = field(default_factory=dict)

    # Entry points and scripts
    entry_points: dict[str, str] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)

    # Additional metadata
    repository: str | None = None
    license: str | None = None
    authors: list[str] = field(default_factory=list)

    # Source manifest files found
    manifest_files: list[str] = field(default_factory=list)

    def has_data(self) -> bool:
        """Check if any meaningful data was extracted."""
        return bool(
            self.name or self.dependencies or self.dev_dependencies or self.entry_points
        )

    def get_tech_stack_summary(self) -> str:
        """Generate a factual tech stack summary."""
        lines = []

        if self.language:
            version_str = f" {self.language_version}" if self.language_version else ""
            lines.append(f"- **{self.language}{version_str}**")

        # Group dependencies by category (infer from common packages)
        categorized = self._categorize_dependencies()
        for category, deps in categorized.items():
            if deps:
                dep_list = ", ".join(sorted(deps)[:5])
                if len(deps) > 5:
                    dep_list += f" (+{len(deps) - 5} more)"
                lines.append(f"- **{category}**: {dep_list}")

        return "\n".join(lines) if lines else "No package manifest found."

    def _categorize_dependencies(self) -> dict[str, list[str]]:
        """Categorize dependencies by their purpose."""
        categories: dict[str, list[str]] = {
            "Web Framework": [],
            "Database": [],
            "Testing": [],
            "CLI": [],
            "AI/ML": [],
            "Other": [],
        }

        # Known package categories
        web_frameworks = {
            "flask",
            "fastapi",
            "django",
            "starlette",
            "aiohttp",
            "tornado",
            "express",
            "koa",
            "hapi",
        }
        databases = {
            "sqlalchemy",
            "pymongo",
            "redis",
            "lancedb",
            "chromadb",
            "psycopg2",
            "mysql",
            "sqlite",
            "prisma",
            "typeorm",
            "sequelize",
        }
        testing = {"pytest", "unittest", "nose", "jest", "mocha", "vitest"}
        cli = {"click", "typer", "argparse", "commander", "yargs"}
        ai_ml = {
            "openai",
            "anthropic",
            "langchain",
            "transformers",
            "torch",
            "tensorflow",
            "sentence-transformers",
            "ollama",
        }

        for dep in self.dependencies:
            dep_lower = dep.lower().replace("-", "").replace("_", "")
            if any(fw in dep_lower for fw in web_frameworks):
                categories["Web Framework"].append(dep)
            elif any(db in dep_lower for db in databases):
                categories["Database"].append(dep)
            elif any(t in dep_lower for t in testing):
                categories["Testing"].append(dep)
            elif any(c in dep_lower for c in cli):
                categories["CLI"].append(dep)
            elif any(ai in dep_lower for ai in ai_ml):
                categories["AI/ML"].append(dep)
            else:
                categories["Other"].append(dep)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    def get_dependency_list(self) -> str:
        """Get a formatted list of all dependencies."""
        lines = []

        if self.dependencies:
            lines.append("### Dependencies\n")
            for name, version in sorted(self.dependencies.items()):
                version_str = f" ({version})" if version and version != "*" else ""
                lines.append(f"- {name}{version_str}")

        if self.dev_dependencies:
            lines.append("\n### Dev Dependencies\n")
            for name, version in sorted(self.dev_dependencies.items()):
                version_str = f" ({version})" if version and version != "*" else ""
                lines.append(f"- {name}{version_str}")

        return "\n".join(lines) if lines else ""

    def get_entry_points_summary(self) -> str:
        """Get a summary of entry points and scripts."""
        lines = []

        if self.entry_points:
            lines.append("### CLI Commands\n")
            for name, target in sorted(self.entry_points.items()):
                lines.append(f"- `{name}` → {target}")

        if self.scripts:
            lines.append("\n### Scripts\n")
            for name, cmd in sorted(self.scripts.items()):
                # Truncate long commands
                cmd_display = cmd if len(cmd) < 60 else cmd[:57] + "..."
                lines.append(f"- `{name}`: {cmd_display}")

        return "\n".join(lines) if lines else ""


def _get_manifest_mtimes(repo_path: Path) -> dict[str, float]:
    """Get modification times for all manifest files.

    Args:
        repo_path: Path to the repository root.

    Returns:
        Dictionary mapping filename to modification time (0 if file doesn't exist).
    """
    mtimes = {}
    for filename in MANIFEST_FILES:
        filepath = repo_path / filename
        if filepath.exists():
            try:
                mtimes[filename] = filepath.stat().st_mtime
            except OSError as e:
                logger.debug("Could not get mtime for %s: %s", filename, e)
                mtimes[filename] = 0
    return mtimes


def _is_cache_valid(
    cache_entry: ManifestCacheEntry, current_mtimes: dict[str, float]
) -> bool:
    """Check if cached manifest is still valid.

    Args:
        cache_entry: The cached manifest entry.
        current_mtimes: Current modification times of manifest files.

    Returns:
        True if cache is valid, False if any file has changed.
    """
    # Check if same set of files exist
    cached_files = set(cache_entry.file_mtimes.keys())
    current_files = set(current_mtimes.keys())

    if cached_files != current_files:
        logger.debug(
            "Manifest cache invalid: file set changed (%s vs %s)",
            cached_files,
            current_files,
        )
        return False

    # Check if any file has been modified
    for filename, cached_mtime in cache_entry.file_mtimes.items():
        current_mtime = current_mtimes.get(filename, 0)
        if cached_mtime != current_mtime:
            logger.debug("Manifest cache invalid: %s modified", filename)
            return False

    return True


def _load_manifest_cache(cache_path: Path) -> ManifestCacheEntry | None:
    """Load manifest cache from disk.

    Args:
        cache_path: Path to the cache file.

    Returns:
        ManifestCacheEntry or None if not found/invalid.
    """
    if not cache_path.exists():
        return None

    try:
        with open(cache_path) as f:
            data = json.load(f)
        return ManifestCacheEntry.from_dict(data)
    except (json.JSONDecodeError, OSError, KeyError, TypeError) as e:
        # json.JSONDecodeError: Corrupted or invalid JSON
        # OSError: File read issues
        # KeyError/TypeError: Invalid cache structure
        logger.debug("Could not load manifest cache: %s", e)
        return None


def _save_manifest_cache(cache_path: Path, entry: ManifestCacheEntry) -> None:
    """Save manifest cache to disk.

    Args:
        cache_path: Path to the cache file.
        entry: The cache entry to save.
    """
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(entry.to_dict(), f, indent=2)
        logger.debug("Saved manifest cache to %s", cache_path)
    except (OSError, TypeError) as e:
        # OSError: File write or directory creation issues
        # TypeError: Unserializable data in cache entry
        logger.warning("Could not save manifest cache: %s", e)


def _manifest_to_dict(manifest: "ProjectManifest") -> dict[str, Any]:
    """Convert ProjectManifest to dictionary for caching."""
    return {
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "language": manifest.language,
        "language_version": manifest.language_version,
        "dependencies": manifest.dependencies,
        "dev_dependencies": manifest.dev_dependencies,
        "entry_points": manifest.entry_points,
        "scripts": manifest.scripts,
        "repository": manifest.repository,
        "license": manifest.license,
        "authors": manifest.authors,
        "manifest_files": manifest.manifest_files,
    }


def _manifest_from_dict(data: dict[str, Any]) -> "ProjectManifest":
    """Create ProjectManifest from dictionary."""
    return ProjectManifest(
        name=data.get("name"),
        version=data.get("version"),
        description=data.get("description"),
        language=data.get("language"),
        language_version=data.get("language_version"),
        dependencies=data.get("dependencies", {}),
        dev_dependencies=data.get("dev_dependencies", {}),
        entry_points=data.get("entry_points", {}),
        scripts=data.get("scripts", {}),
        repository=data.get("repository"),
        license=data.get("license"),
        authors=data.get("authors", []),
        manifest_files=data.get("manifest_files", []),
    )


def get_cached_manifest(
    repo_path: Path, cache_dir: Path | None = None
) -> ProjectManifest:
    """Get project manifest, using cache if available and valid.

    This function checks if a cached manifest exists and is still valid
    (no manifest files have been modified). If valid, returns cached data.
    Otherwise, parses fresh and updates the cache.

    Args:
        repo_path: Path to the repository root.
        cache_dir: Directory for cache storage (defaults to repo_path/.deepwiki).

    Returns:
        ProjectManifest with extracted metadata.
    """
    if cache_dir is None:
        cache_dir = repo_path / ".deepwiki"

    cache_path = cache_dir / "manifest_cache.json"

    # Get current modification times
    current_mtimes = _get_manifest_mtimes(repo_path)

    # Try to use cache
    cache_entry = _load_manifest_cache(cache_path)
    if cache_entry is not None and _is_cache_valid(cache_entry, current_mtimes):
        logger.debug("Using cached manifest data")
        return _manifest_from_dict(cache_entry.manifest_data)

    # Parse fresh
    logger.debug("Parsing manifest files (cache miss or invalid)")
    manifest = parse_manifest(repo_path)

    # Save to cache
    new_entry = ManifestCacheEntry(
        manifest_data=_manifest_to_dict(manifest),
        file_mtimes=current_mtimes,
    )
    _save_manifest_cache(cache_path, new_entry)

    return manifest


def parse_manifest(repo_path: Path) -> ProjectManifest:
    """Parse all recognized package manifests in a repository.

    Note: For incremental updates, prefer get_cached_manifest() which
    avoids re-parsing when manifest files haven't changed.

    Args:
        repo_path: Path to the repository root.

    Returns:
        ProjectManifest with extracted metadata.
    """
    manifest = ProjectManifest()

    # Try each parser in order of preference
    parsers = [
        ("pyproject.toml", _parse_pyproject_toml),
        ("setup.py", _parse_setup_py),
        ("requirements.txt", _parse_requirements_txt),
        ("package.json", _parse_package_json),
        ("Cargo.toml", _parse_cargo_toml),
        ("go.mod", _parse_go_mod),
        ("pom.xml", _parse_pom_xml),
        ("build.gradle", _parse_build_gradle),
        ("Gemfile", _parse_gemfile),
    ]

    for filename, parser in parsers:
        filepath = repo_path / filename
        if filepath.exists():
            try:
                parser(filepath, manifest)
                manifest.manifest_files.append(filename)
            except (OSError, ValueError, KeyError, TypeError) as e:
                # OSError: File read issues
                # ValueError: Invalid file content or format
                # KeyError/TypeError: Missing or invalid fields
                # Skip files that fail to parse but log the issue
                logger.warning("Failed to parse manifest file %s: %s", filename, e)

    return manifest
