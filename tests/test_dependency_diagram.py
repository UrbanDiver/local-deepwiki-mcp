"""Tests for dependency diagram helpers."""

import pytest

from local_deepwiki.generators.diagrams.dependency_diagram import _path_to_module


class TestPathToModule:
    """Test _path_to_module conversion from file paths to module names."""

    def test_standard_src_layout(self):
        """Path with src/ prefix strips src and package directory."""
        result = _path_to_module("src/local_deepwiki/core/indexer.py")
        assert result == "core.indexer"

    def test_no_src_prefix_nested(self):
        """Path without src/ and enough nesting still skips top-level package."""
        result = _path_to_module("mypackage/core/indexer.py")
        assert result == "core.indexer"

    def test_no_src_prefix_shallow(self):
        """Path without src/ and only package/file.py keeps the package name.

        When there is no nesting beyond package/file.py, skipping the
        top-level directory would lose all meaningful context.
        """
        result = _path_to_module("mypackage/utils.py")
        assert result == "mypackage.utils"

    def test_src_layout_shallow(self):
        """src/package/file.py should keep the package name when shallow.

        After stripping src/, only package/file.py remains — the package
        dir is meaningful and must not be dropped.
        """
        result = _path_to_module("src/pkg/utils.py")
        assert result == "pkg.utils"

    def test_deeply_nested(self):
        """Deeply nested path should return full dotted module from subpackage."""
        result = _path_to_module(
            "src/mypackage/generators/diagrams/dependency_diagram.py"
        )
        assert result == "generators.diagrams.dependency_diagram"

    def test_single_file_at_root(self):
        """A single .py file at root should return the module name."""
        result = _path_to_module("setup.py")
        assert result == "setup"

    def test_dunder_files_skipped(self):
        """Files starting with __ should return None."""
        assert _path_to_module("src/pkg/__init__.py") is None
        assert _path_to_module("mypackage/__main__.py") is None

    def test_non_python_skipped(self):
        """Non-.py files should return None."""
        assert _path_to_module("src/pkg/README.md") is None
        assert _path_to_module("Makefile") is None
        assert _path_to_module("src/pkg/data.json") is None
