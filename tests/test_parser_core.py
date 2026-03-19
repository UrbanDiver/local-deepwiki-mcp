"""Tests for core parsing, parse_file, and language detection."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from local_deepwiki.core.parser import (
    CodeParser,
)
from local_deepwiki.models import Language


class TestCodeParser:
    """Test suite for CodeParser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CodeParser()

    @pytest.mark.parametrize(
        "filename, expected_language",
        [
            pytest.param("test.py", Language.PYTHON, id="python-py"),
            pytest.param("test.pyi", Language.PYTHON, id="python-pyi"),
            pytest.param("test.js", Language.JAVASCRIPT, id="javascript-js"),
            pytest.param("test.jsx", Language.JAVASCRIPT, id="javascript-jsx"),
            pytest.param("test.mjs", Language.JAVASCRIPT, id="javascript-mjs"),
            pytest.param("test.ts", Language.TYPESCRIPT, id="typescript-ts"),
            pytest.param("test.tsx", Language.TSX, id="tsx"),
            pytest.param("test.go", Language.GO, id="go"),
            pytest.param("test.rs", Language.RUST, id="rust"),
            pytest.param("test.txt", None, id="unsupported-txt"),
            pytest.param("test.md", None, id="unsupported-md"),
            pytest.param("test.json", None, id="unsupported-json"),
        ],
    )
    def test_detect_language(self, filename, expected_language):
        """Test language detection for various file extensions."""
        assert self.parser.detect_language(Path(filename)) == expected_language

    def test_parse_python_file(self, tmp_path):
        """Test parsing a Python file."""
        code = '''
def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

class Greeter:
    """A class that greets people."""

    def greet(self, name: str) -> str:
        return hello(name)
'''
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        result = self.parser.parse_file(test_file)
        assert result is not None

        root, language, source = result
        assert language == Language.PYTHON
        assert root.type == "module"

    def test_parse_javascript_file(self, tmp_path):
        """Test parsing a JavaScript file."""
        code = """
function greet(name) {
    return `Hello, ${name}!`;
}

class Greeter {
    greet(name) {
        return greet(name);
    }
}
"""
        test_file = tmp_path / "test.js"
        test_file.write_text(code)

        result = self.parser.parse_file(test_file)
        assert result is not None

        root, language, source = result
        assert language == Language.JAVASCRIPT
        assert root.type == "program"

    def test_parse_source_string(self):
        """Test parsing source code from a string."""
        code = "def foo(): pass"
        root = self.parser.parse_source(code, Language.PYTHON)
        assert root.type == "module"

    def test_get_file_info(self, tmp_path):
        """Test getting file info."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): pass")

        info = self.parser.get_file_info(test_file, tmp_path)

        assert info.path == "test.py"
        assert info.language == Language.PYTHON
        assert info.size_bytes > 0
        assert info.hash is not None


class TestUnsupportedFileType:
    """Test handling of unsupported file types."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CodeParser()

    def test_parse_unsupported_file_returns_none(self, tmp_path):
        """Test that parsing unsupported file type returns None."""
        # Create a markdown file
        md_file = tmp_path / "readme.md"
        md_file.write_text("# Hello World")

        result = self.parser.parse_file(md_file)
        assert result is None

    def test_parse_json_file_returns_none(self, tmp_path):
        """Test that parsing JSON file returns None."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"key": "value"}')

        result = self.parser.parse_file(json_file)
        assert result is None
