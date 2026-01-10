"""Tests for the code parser."""

import tempfile
from pathlib import Path

import pytest

from local_deepwiki.core.parser import CodeParser, get_node_text, get_node_name
from local_deepwiki.models import Language


class TestCodeParser:
    """Test suite for CodeParser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CodeParser()

    def test_detect_language_python(self):
        """Test Python language detection."""
        assert self.parser.detect_language(Path("test.py")) == Language.PYTHON
        assert self.parser.detect_language(Path("test.pyi")) == Language.PYTHON

    def test_detect_language_javascript(self):
        """Test JavaScript language detection."""
        assert self.parser.detect_language(Path("test.js")) == Language.JAVASCRIPT
        assert self.parser.detect_language(Path("test.jsx")) == Language.JAVASCRIPT
        assert self.parser.detect_language(Path("test.mjs")) == Language.JAVASCRIPT

    def test_detect_language_typescript(self):
        """Test TypeScript language detection."""
        assert self.parser.detect_language(Path("test.ts")) == Language.TYPESCRIPT
        assert self.parser.detect_language(Path("test.tsx")) == Language.TYPESCRIPT

    def test_detect_language_go(self):
        """Test Go language detection."""
        assert self.parser.detect_language(Path("test.go")) == Language.GO

    def test_detect_language_rust(self):
        """Test Rust language detection."""
        assert self.parser.detect_language(Path("test.rs")) == Language.RUST

    def test_detect_language_unsupported(self):
        """Test unsupported file extensions."""
        assert self.parser.detect_language(Path("test.txt")) is None
        assert self.parser.detect_language(Path("test.md")) is None
        assert self.parser.detect_language(Path("test.json")) is None

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
        code = '''
function greet(name) {
    return `Hello, ${name}!`;
}

class Greeter {
    greet(name) {
        return greet(name);
    }
}
'''
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


class TestNodeHelpers:
    """Test node helper functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CodeParser()

    def test_get_node_text(self):
        """Test extracting text from nodes."""
        code = b"def foo(): pass"
        root = self.parser.parse_source(code, Language.PYTHON)

        # Get the function definition node
        func_node = root.children[0]
        text = get_node_text(func_node, code)
        assert text == "def foo(): pass"

    def test_get_node_name_python_function(self):
        """Test getting name from Python function."""
        code = b"def my_function(): pass"
        root = self.parser.parse_source(code, Language.PYTHON)
        func_node = root.children[0]

        name = get_node_name(func_node, code, Language.PYTHON)
        assert name == "my_function"

    def test_get_node_name_python_class(self):
        """Test getting name from Python class."""
        code = b"class MyClass: pass"
        root = self.parser.parse_source(code, Language.PYTHON)
        class_node = root.children[0]

        name = get_node_name(class_node, code, Language.PYTHON)
        assert name == "MyClass"
