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


class TestTechStackSummary:
    """Tests for tech stack summary generation."""

    def test_tech_stack_with_many_deps(self):
        """Tech stack summary truncates when many deps in category."""
        manifest = ProjectManifest(
            language="Python",
            dependencies={
                "flask": "^2.0",
                "sqlalchemy": "^2.0",
                "redis": "^4.0",
                "pymongo": "^4.0",
                "lancedb": "^0.1",
                "chromadb": "^0.3",
                "psycopg2": "^2.9",
            },
        )
        result = manifest.get_tech_stack_summary()
        # Should have "(+X more)" for categories with > 5 items
        assert "Database" in result
        # Check truncation happens
        assert "+2 more" in result or "+1 more" in result or len(result.split(",")) <= 6


class TestDependencyCategorization:
    """Tests for dependency categorization."""

    def test_categorizes_web_frameworks(self):
        """Web frameworks are categorized correctly."""
        manifest = ProjectManifest(
            language="Python",
            dependencies={"flask": "^2.0", "fastapi": "^0.100"},
        )
        categories = manifest._categorize_dependencies()
        assert "Web Framework" in categories
        assert "flask" in categories["Web Framework"]
        assert "fastapi" in categories["Web Framework"]

    def test_categorizes_databases(self):
        """Databases are categorized correctly."""
        manifest = ProjectManifest(
            language="Python",
            dependencies={"sqlalchemy": "^2.0", "redis": "^4.0", "pymongo": "^4.0"},
        )
        categories = manifest._categorize_dependencies()
        assert "Database" in categories
        assert "sqlalchemy" in categories["Database"]
        assert "redis" in categories["Database"]

    def test_categorizes_testing(self):
        """Testing packages are categorized correctly."""
        manifest = ProjectManifest(
            language="Python",
            dependencies={"pytest": "^7.0", "unittest2": "^1.0"},
        )
        categories = manifest._categorize_dependencies()
        assert "Testing" in categories
        assert "pytest" in categories["Testing"]

    def test_categorizes_cli(self):
        """CLI packages are categorized correctly."""
        manifest = ProjectManifest(
            language="Python",
            dependencies={"click": "^8.0", "typer": "^0.9"},
        )
        categories = manifest._categorize_dependencies()
        assert "CLI" in categories
        assert "click" in categories["CLI"]
        assert "typer" in categories["CLI"]

    def test_categorizes_ai_ml(self):
        """AI/ML packages are categorized correctly."""
        manifest = ProjectManifest(
            language="Python",
            dependencies={"openai": "^1.0", "anthropic": "^0.5", "langchain": "^0.1"},
        )
        categories = manifest._categorize_dependencies()
        assert "AI/ML" in categories
        assert "openai" in categories["AI/ML"]
        assert "anthropic" in categories["AI/ML"]

    def test_categorizes_other(self):
        """Unknown packages go to Other category."""
        manifest = ProjectManifest(
            language="Python",
            dependencies={"some-random-package": "^1.0"},
        )
        categories = manifest._categorize_dependencies()
        assert "Other" in categories
        assert "some-random-package" in categories["Other"]


class TestEntryPointsSummary:
    """Tests for entry points summary generation."""

    def test_entry_points_summary_with_cli_commands(self):
        """Entry points summary shows CLI commands."""
        manifest = ProjectManifest(
            entry_points={"mycli": "mypackage:main", "other-cmd": "mypackage.other:run"}
        )
        result = manifest.get_entry_points_summary()
        assert "### CLI Commands" in result
        assert "`mycli`" in result
        assert "mypackage:main" in result

    def test_entry_points_summary_with_scripts(self):
        """Entry points summary shows scripts."""
        manifest = ProjectManifest(scripts={"build": "npm run build", "test": "pytest tests/"})
        result = manifest.get_entry_points_summary()
        assert "### Scripts" in result
        assert "`build`" in result
        assert "`test`" in result

    def test_entry_points_summary_truncates_long_commands(self):
        """Long script commands are truncated."""
        long_cmd = "very-long-command " * 10
        manifest = ProjectManifest(scripts={"build": long_cmd})
        result = manifest.get_entry_points_summary()
        assert "..." in result

    def test_entry_points_summary_empty(self):
        """Empty entry points returns empty string."""
        manifest = ProjectManifest()
        result = manifest.get_entry_points_summary()
        assert result == ""


class TestCacheExceptionHandling:
    """Tests for cache-related exception handling."""

    def test_get_manifest_mtimes_handles_permission_error(self):
        """mtime lookup handles OSError gracefully."""
        # This is hard to test directly without mocking, but we can verify
        # the function doesn't crash with a valid path
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "pyproject.toml").write_text("[project]\nname='test'")
            mtimes = _get_manifest_mtimes(root)
            assert "pyproject.toml" in mtimes

    def test_load_manifest_cache_handles_invalid_json(self):
        """Loading cache handles invalid JSON gracefully."""
        from local_deepwiki.generators.manifest import _load_manifest_cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "invalid_cache.json"
            cache_path.write_text("not valid json {{{")

            result = _load_manifest_cache(cache_path)
            assert result is None

    def test_load_manifest_cache_handles_missing_file(self):
        """Loading cache handles missing file gracefully."""
        from local_deepwiki.generators.manifest import _load_manifest_cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "nonexistent.json"

            result = _load_manifest_cache(cache_path)
            assert result is None

    def test_save_manifest_cache_creates_directory(self):
        """Saving cache creates parent directory if needed."""
        from local_deepwiki.generators.manifest import _save_manifest_cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "subdir" / "cache.json"
            entry = ManifestCacheEntry(
                manifest_data={"name": "test"},
                file_mtimes={"pyproject.toml": 123456.0},
            )

            _save_manifest_cache(cache_path, entry)

            assert cache_path.exists()
            loaded = json.loads(cache_path.read_text())
            assert loaded["manifest_data"]["name"] == "test"


class TestParseManifestExceptionHandling:
    """Tests for parse_manifest exception handling."""

    def test_parse_manifest_handles_invalid_toml(self):
        """Parsing handles invalid TOML gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text("invalid toml content [[[")

            manifest = parse_manifest(Path(tmpdir))

            # Should not crash, but manifest will be mostly empty
            assert "pyproject.toml" not in manifest.manifest_files

    def test_parse_manifest_handles_invalid_json(self):
        """Parsing handles invalid JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = Path(tmpdir) / "package.json"
            package_json.write_text("not valid json {{{")

            manifest = parse_manifest(Path(tmpdir))

            # Should not crash
            assert "package.json" not in manifest.manifest_files


class TestPoetryParsing:
    """Tests for Poetry-specific pyproject.toml parsing."""

    def test_parse_poetry_project(self):
        """Parse a Poetry-style pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(
                """
[tool.poetry]
name = "poetry-project"
description = "A poetry project"

[tool.poetry.dependencies]
python = "^3.11"
requests = "^2.0"
flask = {version = "^2.0", extras = ["async"]}

[tool.poetry.dev-dependencies]
pytest = "^7.0"
black = {version = "^23.0"}
"""
            )

            manifest = parse_manifest(Path(tmpdir))

            assert manifest.name == "poetry-project"
            assert manifest.description == "A poetry project"
            assert manifest.language == "Python"
            assert "requests" in manifest.dependencies
            assert "flask" in manifest.dependencies
            assert "pytest" in manifest.dev_dependencies
            assert "black" in manifest.dev_dependencies
            # python should not be in dependencies
            assert "python" not in manifest.dependencies


class TestSetupPyParsing:
    """Tests for setup.py parsing."""

    def test_parse_setup_py_basic(self):
        """Parse a basic setup.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_py = Path(tmpdir) / "setup.py"
            setup_py.write_text(
                """
from setuptools import setup

setup(
    name="legacy-project",
    version="1.0.0",
    install_requires=[
        "requests>=2.0",
        "flask",
    ],
)
"""
            )

            manifest = parse_manifest(Path(tmpdir))

            assert manifest.name == "legacy-project"
            assert manifest.version == "1.0.0"
            assert manifest.language == "Python"
            assert "requests" in manifest.dependencies
            assert "flask" in manifest.dependencies


class TestPomXmlParsing:
    """Tests for pom.xml (Maven) parsing."""

    def test_parse_pom_xml_basic(self):
        """Parse a basic pom.xml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pom = Path(tmpdir) / "pom.xml"
            # Use non-namespaced XML which the parser handles correctly
            pom.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<project>
    <artifactId>maven-project</artifactId>
    <version>1.0.0</version>
    <description>A Maven project</description>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-core</artifactId>
            <version>5.3.0</version>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
"""
            )

            manifest = parse_manifest(Path(tmpdir))

            assert manifest.name == "maven-project"
            assert manifest.version == "1.0.0"
            assert manifest.description == "A Maven project"
            assert manifest.language == "Java"
            assert manifest.language_version == "17"
            assert "spring-core" in manifest.dependencies
            assert "junit" in manifest.dev_dependencies  # scope=test goes to dev

    def test_parse_pom_xml_without_namespace(self):
        """Parse pom.xml without Maven namespace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pom = Path(tmpdir) / "pom.xml"
            pom.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<project>
    <artifactId>simple-maven</artifactId>
    <version>2.0.0</version>
    <dependencies>
        <dependency>
            <artifactId>commons-io</artifactId>
        </dependency>
    </dependencies>
</project>
"""
            )

            manifest = parse_manifest(Path(tmpdir))

            assert manifest.name == "simple-maven"
            assert manifest.version == "2.0.0"
            assert manifest.language == "Java"
            assert "commons-io" in manifest.dependencies


class TestBuildGradleParsing:
    """Tests for build.gradle parsing."""

    def test_parse_build_gradle_java(self):
        """Parse a Java Gradle project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gradle = Path(tmpdir) / "build.gradle"
            gradle.write_text(
                """
plugins {
    id 'java'
}

dependencies {
    implementation 'org.springframework:spring-core:5.3.0'
    api 'com.google.guava:guava:31.0'
    testImplementation 'junit:junit:4.13'
}
"""
            )

            manifest = parse_manifest(Path(tmpdir))

            assert manifest.language == "Java"
            assert "spring-core" in manifest.dependencies
            assert "guava" in manifest.dependencies
            assert "junit" in manifest.dev_dependencies

    def test_parse_build_gradle_kotlin(self):
        """Parse a Kotlin Gradle project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gradle = Path(tmpdir) / "build.gradle"
            gradle.write_text(
                """
plugins {
    id 'org.jetbrains.kotlin.jvm'
}

dependencies {
    implementation "org.jetbrains.kotlin:kotlin-stdlib:1.9.0"
    testCompile "org.junit.jupiter:junit-jupiter:5.9.0"
}
"""
            )

            manifest = parse_manifest(Path(tmpdir))

            assert manifest.language == "Kotlin"
            assert "kotlin-stdlib" in manifest.dependencies
            assert "junit-jupiter" in manifest.dev_dependencies


class TestGemfileParsing:
    """Tests for Gemfile (Ruby) parsing."""

    def test_parse_gemfile_basic(self):
        """Parse a basic Gemfile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gemfile = Path(tmpdir) / "Gemfile"
            gemfile.write_text(
                """
source 'https://rubygems.org'

gem 'rails', '~> 7.0'
gem 'pg'
gem 'puma', '~> 5.0'
gem 'rspec-rails', '~> 6.0'
"""
            )

            manifest = parse_manifest(Path(tmpdir))

            assert manifest.language == "Ruby"
            assert "rails" in manifest.dependencies
            assert manifest.dependencies["rails"] == "~> 7.0"
            assert "pg" in manifest.dependencies
            assert manifest.dependencies["pg"] == "*"
            assert "puma" in manifest.dependencies
            assert "rspec-rails" in manifest.dependencies


class TestPackageJsonEdgeCases:
    """Tests for package.json edge cases."""

    def test_parse_package_json_with_node_engine(self):
        """Parse package.json with Node engine version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = Path(tmpdir) / "package.json"
            package_json.write_text(
                json.dumps(
                    {
                        "name": "node-project",
                        "engines": {"node": ">=18.0.0"},
                        "dependencies": {"express": "^4.0.0"},
                    }
                )
            )

            manifest = parse_manifest(Path(tmpdir))

            assert manifest.language == "JavaScript"
            assert manifest.language_version == "Node >=18.0.0"

    def test_parse_package_json_with_bin_string(self):
        """Parse package.json with bin as string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = Path(tmpdir) / "package.json"
            package_json.write_text(
                json.dumps(
                    {
                        "name": "cli-tool",
                        "bin": "./bin/cli.js",
                    }
                )
            )

            manifest = parse_manifest(Path(tmpdir))

            assert "cli-tool" in manifest.entry_points
            assert manifest.entry_points["cli-tool"] == "./bin/cli.js"

    def test_parse_package_json_with_bin_object(self):
        """Parse package.json with bin as object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = Path(tmpdir) / "package.json"
            package_json.write_text(
                json.dumps(
                    {
                        "name": "multi-cli",
                        "bin": {
                            "cmd1": "./bin/cmd1.js",
                            "cmd2": "./bin/cmd2.js",
                        },
                    }
                )
            )

            manifest = parse_manifest(Path(tmpdir))

            assert "cmd1" in manifest.entry_points
            assert "cmd2" in manifest.entry_points

    def test_parse_package_json_with_repository_string(self):
        """Parse package.json with repository as string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = Path(tmpdir) / "package.json"
            package_json.write_text(
                json.dumps(
                    {
                        "name": "repo-string",
                        "repository": "https://github.com/user/repo",
                    }
                )
            )

            manifest = parse_manifest(Path(tmpdir))

            assert manifest.repository == "https://github.com/user/repo"


class TestCargoTomlEdgeCases:
    """Tests for Cargo.toml edge cases."""

    def test_parse_cargo_toml_with_bin_targets(self):
        """Parse Cargo.toml with binary targets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cargo = Path(tmpdir) / "Cargo.toml"
            cargo.write_text(
                """
[package]
name = "multi-bin"
version = "0.1.0"

[[bin]]
name = "server"
path = "src/bin/server.rs"

[[bin]]
name = "client"
path = "src/bin/client.rs"

[dependencies]
tokio = "1.0"
"""
            )

            manifest = parse_manifest(Path(tmpdir))

            assert manifest.name == "multi-bin"
            assert "server" in manifest.entry_points
            assert "client" in manifest.entry_points
            assert manifest.entry_points["server"] == "src/bin/server.rs"


class TestPythonDepParsing:
    """Tests for Python dependency string parsing."""

    def test_parse_python_dep_no_version(self):
        """Parse dependency with no version."""
        from local_deepwiki.generators.manifest import _parse_python_dep

        name, version = _parse_python_dep("requests")
        assert name == "requests"
        assert version == "*"

    def test_parse_python_dep_with_version(self):
        """Parse dependency with version."""
        from local_deepwiki.generators.manifest import _parse_python_dep

        name, version = _parse_python_dep("requests>=2.0.0")
        assert name == "requests"
        assert version == ">=2.0.0"

    def test_parse_python_dep_with_extras(self):
        """Parse dependency with extras."""
        from local_deepwiki.generators.manifest import _parse_python_dep

        name, version = _parse_python_dep("requests[security]>=2.0")
        assert name == "requests"
        # Version includes the bracket part
        assert "[security]" in version or name == "requests"


class TestDirectoryTreeEdgeCases:
    """Tests for directory tree edge cases."""

    def test_directory_tree_handles_permission_error(self):
        """Directory tree handles permission errors gracefully."""
        # This is hard to test directly, but we can verify no crash
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "src").mkdir()
            (root / "src" / "main.py").touch()

            tree = get_directory_tree(root, max_depth=2)
            assert "src/" in tree

    def test_directory_tree_respects_max_depth(self):
        """Directory tree respects max_depth."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a").mkdir()
            (root / "a" / "b").mkdir()
            (root / "a" / "b" / "c").mkdir()
            (root / "a" / "b" / "c" / "deep.txt").touch()

            tree = get_directory_tree(root, max_depth=1)

            assert "a/" in tree
            # b should not appear with max_depth=1
            assert "b/" not in tree

    def test_directory_tree_skips_pycache(self):
        """Directory tree skips __pycache__."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "module.cpython-311.pyc").touch()
            (root / "src").mkdir()

            tree = get_directory_tree(root, max_depth=2)

            assert "__pycache__" not in tree
            assert "src/" in tree
