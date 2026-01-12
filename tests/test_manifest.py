"""Tests for the manifest parser module."""

import json
import tempfile
from pathlib import Path

from local_deepwiki.generators.manifest import (
    ProjectManifest,
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
            pyproject.write_text("""
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
""")
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
            package_json.write_text(json.dumps({
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
            }))
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
            requirements.write_text("""
# Main dependencies
requests>=2.0
flask==2.0.0
pydantic

# Skip these
-r other-requirements.txt
""")
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
            cargo.write_text("""
[package]
name = "test-crate"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0"
tokio = { version = "1.0", features = ["full"] }

[dev-dependencies]
criterion = "0.5"
""")
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
            go_mod.write_text("""
module github.com/user/test-project

go 1.21

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/stretchr/testify v1.8.0
)
""")
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
            pyproject.write_text("""
[project]
name = "from-pyproject"
dependencies = ["flask"]
""")
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
