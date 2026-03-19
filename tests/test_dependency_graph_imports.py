"""Tests for import pattern detection, extraction, and resolution."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from local_deepwiki.generators.analysis.dependency_graph import (
    DependencyGraphGenerator,
)


@pytest.fixture
def generator():
    """Create a generator with mock store."""
    store = AsyncMock()
    return DependencyGraphGenerator(store)


@pytest.fixture
def generator_with_project(generator):
    """Create a generator with project name set."""
    generator._project_name = "myproject"
    return generator


class TestImportParsing:
    """Tests for import parsing functionality."""

    def test_parses_python_from_import(self, generator):
        """Test parsing Python 'from X import Y'."""
        content = "from mypackage.core import parser"
        imports = generator._parse_imports(content, "python")
        assert "mypackage.core" in imports

    def test_parses_python_import(self, generator):
        """Test parsing Python 'import X'."""
        content = "import pathlib"
        imports = generator._parse_imports(content, "python")
        assert "pathlib" in imports

    def test_parses_javascript_import(self, generator):
        """Test parsing JavaScript import."""
        content = 'import { something } from "./module"'
        imports = generator._parse_imports(content, "javascript")
        assert "./module" in imports

    def test_parses_typescript_import(self, generator):
        """Test parsing TypeScript import."""
        content = 'import type { Type } from "module"'
        imports = generator._parse_imports(content, "typescript")
        assert "module" in imports

    def test_handles_multiple_imports(self, generator):
        """Test handling multiple imports."""
        content = """import os
from pathlib import Path
import json"""
        imports = generator._parse_imports(content, "python")
        assert "os" in imports
        assert "pathlib" in imports
        assert "json" in imports

    def test_handles_empty_content(self, generator):
        """Test handling empty content."""
        imports = generator._parse_imports("", "python")
        assert len(imports) == 0


class TestInternalImportResolution:
    """Tests for internal import resolution."""

    def test_identifies_internal_import(self, generator_with_project):
        """Test identification of internal import."""
        internal_modules = {"core.parser", "core.chunker", "utils.helpers"}
        assert (
            generator_with_project._is_internal_import("core.parser", internal_modules)
            is True
        )

    def test_identifies_external_import(self, generator_with_project):
        """Test identification of external import."""
        internal_modules = {"core.parser", "core.chunker"}
        assert (
            generator_with_project._is_internal_import("pathlib", internal_modules)
            is False
        )

    def test_resolves_internal_import(self, generator_with_project):
        """Test resolving internal import to module."""
        internal_modules = {"core.parser", "core.chunker", "utils.helpers"}
        result = generator_with_project._resolve_internal_import(
            "core.parser", internal_modules
        )
        assert result == "core.parser"

    def test_resolves_import_by_last_component(self, generator_with_project):
        """Test resolving import by matching last component."""
        internal_modules = {"core.parser", "core.chunker"}
        result = generator_with_project._resolve_internal_import(
            "myproject.core.parser", internal_modules
        )
        assert result == "core.parser"


class TestInternalImportEdgeCases:
    """Tests for _is_internal_import edge cases (lines 559, 567, 569)."""

    @pytest.fixture
    def gen(self):
        """Create a generator with project name set."""
        store = AsyncMock()
        gen = DependencyGraphGenerator(store)
        gen._project_name = "myproject"
        return gen

    def test_import_starts_with_project_name(self, gen):
        """Test import that starts with project name (line 559)."""
        internal_modules = {"core.parser", "core.chunker"}
        # Import starts with project name
        assert (
            gen._is_internal_import("myproject.core.parser", internal_modules) is True
        )

    def test_import_parts_match_module_last_component(self, gen):
        """Test when import parts match module by last component (line 567)."""
        internal_modules = {"core.parser"}
        # Import "parser" should match "core.parser" by last component
        assert gen._is_internal_import("utils.parser", internal_modules) is True

    def test_import_ends_with_module(self, gen):
        """Test when import ends with module name (line 569)."""
        internal_modules = {"parser"}
        # Import that ends with the module
        assert gen._is_internal_import("myproject.parser", internal_modules) is True


class TestResolveInternalImportEdgeCases:
    """Tests for _resolve_internal_import edge cases (lines 597-603)."""

    @pytest.fixture
    def gen(self):
        """Create a generator with project name set."""
        store = AsyncMock()
        gen = DependencyGraphGenerator(store)
        gen._project_name = "myproject"
        return gen

    def test_strips_project_prefix(self, gen):
        """Test stripping project prefix from import (lines 591-594)."""
        internal_modules = {"core.parser"}
        # Import with project prefix should be resolved
        result = gen._resolve_internal_import("myproject.core.parser", internal_modules)
        assert result == "core.parser"

    def test_matches_by_last_component(self, gen):
        """Test matching by last component when prefix doesn't match (lines 597-601)."""
        internal_modules = {"core.parser", "utils.helpers"}
        # Import where only last component matches
        result = gen._resolve_internal_import("somepackage.parser", internal_modules)
        assert result == "core.parser"

    def test_returns_none_for_no_match(self, gen):
        """Test returns None when no match found (line 603)."""
        internal_modules = {"core.parser"}
        result = gen._resolve_internal_import("completely.unrelated", internal_modules)
        assert result is None


class TestInternalImportEndsWithModule:
    """Test for line 569 - import ends with module."""

    @pytest.fixture
    def gen(self):
        """Create a generator with project name."""
        store = AsyncMock()
        gen = DependencyGraphGenerator(store)
        gen._project_name = "myproject"
        return gen

    def test_import_ending_with_dot_module(self, gen):
        """Test import that ends with '.' + module name."""
        internal_modules = {"chunker"}
        # Import ending with ".chunker"
        result = gen._is_internal_import("some.package.chunker", internal_modules)
        assert result is True
