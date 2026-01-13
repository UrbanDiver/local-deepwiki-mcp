"""Tests for the manifest parser module."""

import json
import tempfile
import time
from pathlib import Path

from local_deepwiki.generators.manifest import (
    ManifestCacheEntry,
    ProjectManifest,
    _get_manifest_mtimes,
    _is_cache_valid,
    get_cached_manifest,
    get_directory_tree,
    parse_manifest,
)


class TestProjectManifest:
    """Tests for ProjectManifest dataclass."""

    def test_has_data_empty(self):
        """Empty manifest has no data."""
        manifest = ProjectManifest()
        assert not manifest.has_data()

    def test_has_data_with_name(self):
        """Manifest with name has data."""
        manifest = ProjectManifest(name="test-project")
        assert manifest.has_data()

    def test_has_data_with_dependencies(self):
        """Manifest with dependencies has data."""
        manifest = ProjectManifest(dependencies={"requests": "^2.0"})
        assert manifest.has_data()

    def test_get_tech_stack_summary_empty(self):
        """Empty manifest returns default message."""
        manifest = ProjectManifest()
        result = manifest.get_tech_stack_summary()
        assert result == "No package manifest found."

    def test_get_tech_stack_summary_with_language(self):
        """Manifest with language shows it in summary."""
        manifest = ProjectManifest(language="Python", language_version=">=3.11")
        result = manifest.get_tech_stack_summary()
        assert "Python" in result
        assert ">=3.11" in result

    def test_get_dependency_list_formatted(self):
        """Dependencies are formatted correctly."""
        manifest = ProjectManifest(
            dependencies={"requests": "^2.0", "flask": ">=2.0"},
            dev_dependencies={"pytest": "^7.0"},
        )
        result = manifest.get_dependency_list()
        assert "### Dependencies" in result
        assert "requests" in result
        assert "flask" in result
        assert "### Dev Dependencies" in result
        assert "pytest" in result


class TestParsePyprojectToml:
    """Tests for parsing pyproject.toml files."""

    def test_parse_basic_pyproject(self):
        """Parse a basic pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[project]
name = "test-project"
version = "1.0.0"
description = "A test project"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.0",
    "flask",
]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[project.scripts]
test-cli = "test_project:main"
"""
            )
            manifest = parse_manifest(Path(tmpdir))

            assert manifest.name == "test-project"
            assert manifest.version == "1.0.0"
            assert manifest.description == "A test project"
            assert manifest.language == "Python"
            assert manifest.language_version == ">=3.11"
            assert "requests" in manifest.dependencies
            assert "flask" in manifest.dependencies
            assert "pytest" in manifest.dev_dependencies
            assert "test-cli" in manifest.entry_points


class TestParsePackageJson:
    """Tests for parsing package.json files."""

    def test_parse_basic_package_json(self):
        """Parse a basic package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = Path(tmpdir) / "package.json"
            package_json.write_text(
                json.dumps(
                    {
                        "name": "test-package",
                        "version": "1.0.0",
                        "description": "A test package",
                        "dependencies": {
                            "express": "^4.0.0",
                            "lodash": "^4.0.0",
                        },
                        "devDependencies": {
                            "typescript": "^5.0.0",
                            "jest": "^29.0.0",
                        },
                        "scripts": {
                            "build": "tsc",
                            "test": "jest",
                        },
                        "main": "index.js",
                    }
                )
            )
            manifest = parse_manifest(Path(tmpdir))

            assert manifest.name == "test-package"
            assert manifest.version == "1.0.0"
            assert manifest.language == "TypeScript"  # Due to typescript dep
            assert "express" in manifest.dependencies
            assert "lodash" in manifest.dependencies
            assert "typescript" in manifest.dev_dependencies
            assert "jest" in manifest.dev_dependencies
            assert "build" in manifest.scripts
            assert "test" in manifest.scripts


class TestParseRequirementsTxt:
    """Tests for parsing requirements.txt files."""

    def test_parse_basic_requirements(self):
        """Parse a basic requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            requirements = Path(tmpdir) / "requirements.txt"
            requirements.write_text(
                """
# Main dependencies
requests>=2.0
flask==2.0.0
pydantic

# Skip these
-r other-requirements.txt
"""
            )
            manifest = parse_manifest(Path(tmpdir))

            assert manifest.language == "Python"
            assert "requests" in manifest.dependencies
            assert "flask" in manifest.dependencies
            assert "pydantic" in manifest.dependencies


class TestParseCargoToml:
    """Tests for parsing Cargo.toml files."""

    def test_parse_basic_cargo(self):
        """Parse a basic Cargo.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cargo = Path(tmpdir) / "Cargo.toml"
            cargo.write_text(
                """
[package]
name = "test-crate"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0"
tokio = { version = "1.0", features = ["full"] }

[dev-dependencies]
criterion = "0.5"
"""
            )
            manifest = parse_manifest(Path(tmpdir))

            assert manifest.name == "test-crate"
            assert manifest.version == "0.1.0"
            assert manifest.language == "Rust"
            assert manifest.language_version == "Edition 2021"
            assert "serde" in manifest.dependencies
            assert "tokio" in manifest.dependencies
            assert "criterion" in manifest.dev_dependencies


class TestParseGoMod:
    """Tests for parsing go.mod files."""

    def test_parse_basic_go_mod(self):
        """Parse a basic go.mod."""
        with tempfile.TemporaryDirectory() as tmpdir:
            go_mod = Path(tmpdir) / "go.mod"
            go_mod.write_text(
                """
module github.com/user/test-project

go 1.21

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/stretchr/testify v1.8.0
)
"""
            )
            manifest = parse_manifest(Path(tmpdir))

            assert manifest.name == "test-project"
            assert manifest.language == "Go"
            assert manifest.language_version == "1.21"
            assert "gin" in manifest.dependencies
            assert "testify" in manifest.dependencies


class TestGetDirectoryTree:
    """Tests for directory tree generation."""

    def test_basic_tree(self):
        """Generate a basic directory tree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "src").mkdir()
            (root / "src" / "main.py").touch()
            (root / "tests").mkdir()
            (root / "tests" / "test_main.py").touch()
            (root / "README.md").touch()

            tree = get_directory_tree(root, max_depth=2)

            assert "src/" in tree
            assert "main.py" in tree
            assert "tests/" in tree
            assert "test_main.py" in tree
            assert "README.md" in tree

    def test_skips_hidden_dirs(self):
        """Hidden directories are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".git").mkdir()
            (root / ".git" / "config").touch()
            (root / "src").mkdir()
            (root / "src" / "main.py").touch()

            tree = get_directory_tree(root, max_depth=2)

            assert ".git" not in tree
            assert "config" not in tree
            assert "src/" in tree
            assert "main.py" in tree

    def test_skips_node_modules(self):
        """node_modules is skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "express").mkdir()
            (root / "src").mkdir()

            tree = get_directory_tree(root, max_depth=2)

            assert "node_modules" not in tree
            assert "src/" in tree

    def test_respects_max_items(self):
        """Respects max_items limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for i in range(20):
                (root / f"file{i}.txt").touch()

            tree = get_directory_tree(root, max_depth=1, max_items=5)

            # Should have truncation indicator
            assert "..." in tree


class TestMultipleManifests:
    """Tests for handling multiple manifest files."""

    def test_pyproject_takes_precedence(self):
        """pyproject.toml takes precedence over requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[project]
name = "from-pyproject"
dependencies = ["flask"]
"""
            )
            requirements = Path(tmpdir) / "requirements.txt"
            requirements.write_text("requests")

            manifest = parse_manifest(Path(tmpdir))

            # Name comes from pyproject
            assert manifest.name == "from-pyproject"
            # But both deps are collected
            assert "flask" in manifest.dependencies
            assert "requests" in manifest.dependencies
            # Both manifest files recorded
            assert "pyproject.toml" in manifest.manifest_files
            assert "requirements.txt" in manifest.manifest_files


class TestManifestCaching:
    """Tests for manifest caching functionality."""

    def test_get_manifest_mtimes_empty_repo(self):
        """Empty repo returns no mtimes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mtimes = _get_manifest_mtimes(Path(tmpdir))
            assert mtimes == {}

    def test_get_manifest_mtimes_with_files(self):
        """Returns mtimes for existing manifest files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "pyproject.toml").write_text("[project]\nname = 'test'")
            (root / "package.json").write_text('{"name": "test"}')

            mtimes = _get_manifest_mtimes(root)

            assert "pyproject.toml" in mtimes
            assert "package.json" in mtimes
            assert mtimes["pyproject.toml"] > 0
            assert mtimes["package.json"] > 0

    def test_cache_entry_serialization(self):
        """Cache entry can be serialized and deserialized."""
        entry = ManifestCacheEntry(
            manifest_data={"name": "test", "dependencies": {"flask": "^2.0"}},
            file_mtimes={"pyproject.toml": 1234567890.0},
        )

        # Serialize
        data = entry.to_dict()
        assert "manifest_data" in data
        assert "file_mtimes" in data

        # Deserialize
        restored = ManifestCacheEntry.from_dict(data)
        assert restored.manifest_data == entry.manifest_data
        assert restored.file_mtimes == entry.file_mtimes

    def test_cache_valid_when_unchanged(self):
        """Cache is valid when files haven't changed."""
        mtimes = {"pyproject.toml": 1234567890.0}
        entry = ManifestCacheEntry(
            manifest_data={"name": "test"},
            file_mtimes=mtimes,
        )

        assert _is_cache_valid(entry, mtimes) is True

    def test_cache_invalid_when_file_modified(self):
        """Cache is invalid when a file is modified."""
        old_mtimes = {"pyproject.toml": 1234567890.0}
        new_mtimes = {"pyproject.toml": 1234567899.0}  # Different mtime

        entry = ManifestCacheEntry(
            manifest_data={"name": "test"},
            file_mtimes=old_mtimes,
        )

        assert _is_cache_valid(entry, new_mtimes) is False

    def test_cache_invalid_when_file_added(self):
        """Cache is invalid when a new manifest file is added."""
        old_mtimes = {"pyproject.toml": 1234567890.0}
        new_mtimes = {"pyproject.toml": 1234567890.0, "package.json": 1234567890.0}

        entry = ManifestCacheEntry(
            manifest_data={"name": "test"},
            file_mtimes=old_mtimes,
        )

        assert _is_cache_valid(entry, new_mtimes) is False

    def test_cache_invalid_when_file_removed(self):
        """Cache is invalid when a manifest file is removed."""
        old_mtimes = {"pyproject.toml": 1234567890.0, "package.json": 1234567890.0}
        new_mtimes = {"pyproject.toml": 1234567890.0}

        entry = ManifestCacheEntry(
            manifest_data={"name": "test"},
            file_mtimes=old_mtimes,
        )

        assert _is_cache_valid(entry, new_mtimes) is False

    def test_get_cached_manifest_creates_cache(self):
        """get_cached_manifest creates cache file on first call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cache_dir = root / ".deepwiki"

            (root / "pyproject.toml").write_text(
                """
[project]
name = "cached-project"
dependencies = ["requests"]
"""
            )

            manifest = get_cached_manifest(root, cache_dir=cache_dir)

            assert manifest.name == "cached-project"
            assert (cache_dir / "manifest_cache.json").exists()

    def test_get_cached_manifest_uses_cache(self):
        """get_cached_manifest uses cache on subsequent calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cache_dir = root / ".deepwiki"

            (root / "pyproject.toml").write_text(
                """
[project]
name = "cached-project"
dependencies = ["requests"]
"""
            )

            # First call creates cache
            manifest1 = get_cached_manifest(root, cache_dir=cache_dir)

            # Modify the file content but keep same mtime (simulate using cache)
            # Since we can't easily control mtime, we verify cache file exists
            assert (cache_dir / "manifest_cache.json").exists()

            # Second call should use cache
            manifest2 = get_cached_manifest(root, cache_dir=cache_dir)

            assert manifest1.name == manifest2.name
            assert manifest1.dependencies == manifest2.dependencies

    def test_get_cached_manifest_invalidates_on_change(self):
        """get_cached_manifest re-parses when file changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cache_dir = root / ".deepwiki"

            pyproject = root / "pyproject.toml"
            pyproject.write_text(
                """
[project]
name = "original-name"
"""
            )

            # First call
            manifest1 = get_cached_manifest(root, cache_dir=cache_dir)
            assert manifest1.name == "original-name"

            # Wait a tiny bit to ensure different mtime
            time.sleep(0.01)

            # Modify the file
            pyproject.write_text(
                """
[project]
name = "updated-name"
"""
            )

            # Second call should re-parse
            manifest2 = get_cached_manifest(root, cache_dir=cache_dir)
            assert manifest2.name == "updated-name"

    def test_get_cached_manifest_default_cache_dir(self):
        """get_cached_manifest uses .deepwiki in repo by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            (root / "package.json").write_text('{"name": "test-pkg"}')

            # Call without explicit cache_dir
            manifest = get_cached_manifest(root)

            assert manifest.name == "test-pkg"
            assert (root / ".deepwiki" / "manifest_cache.json").exists()
