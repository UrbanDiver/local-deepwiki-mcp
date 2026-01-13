"""Tests for the code parser."""

import tempfile
from pathlib import Path

import pytest

from local_deepwiki.core.parser import (
    HASH_CHUNK_SIZE,
    MMAP_THRESHOLD_BYTES,
    CodeParser,
    _collect_preceding_comments,
    _compute_file_hash,
    _read_file_content,
    _strip_line_comment_prefix,
    find_nodes_by_type,
    get_docstring,
    get_node_name,
    get_node_text,
)
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


class TestCommentHelpers:
    """Tests for comment collection helper functions."""

    def test_strip_line_comment_prefix_single_line(self):
        """Test stripping prefix from single comment."""
        lines = ["// Hello world"]
        result = _strip_line_comment_prefix(lines, "//")
        assert result == "Hello world"

    def test_strip_line_comment_prefix_multi_line(self):
        """Test stripping prefix from multiple comments."""
        lines = ["// First line", "// Second line", "// Third line"]
        result = _strip_line_comment_prefix(lines, "//")
        assert result == "First line\nSecond line\nThird line"

    def test_strip_line_comment_prefix_with_space(self):
        """Test stripping prefix preserves content after space."""
        lines = ["/// Documentation here"]
        result = _strip_line_comment_prefix(lines, "///")
        assert result == "Documentation here"

    def test_strip_line_comment_prefix_no_space(self):
        """Test stripping prefix without space after prefix."""
        lines = ["///NoSpace"]
        result = _strip_line_comment_prefix(lines, "///")
        assert result == "NoSpace"


class TestDocstringExtraction:
    """Tests for docstring extraction from various languages."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CodeParser()

    def test_python_docstring(self):
        """Test extracting Python docstring."""
        code = b'''def hello():
    """This is a docstring."""
    pass'''
        root = self.parser.parse_source(code, Language.PYTHON)
        func_node = root.children[0]

        docstring = get_docstring(func_node, code, Language.PYTHON)
        assert docstring == "This is a docstring."

    def test_go_single_line_comment(self):
        """Test Go single-line doc comment."""
        code = b"""// HelloWorld says hello
func HelloWorld() {}"""
        root = self.parser.parse_source(code, Language.GO)
        func_nodes = find_nodes_by_type(root, {"function_declaration"})
        assert len(func_nodes) == 1

        docstring = get_docstring(func_nodes[0], code, Language.GO)
        assert docstring == "HelloWorld says hello"

    def test_go_multi_line_comments(self):
        """Test Go multi-line doc comments."""
        code = b"""// HelloWorld says hello to the world.
// It takes no arguments and returns nothing.
// This is a detailed description.
func HelloWorld() {}"""
        root = self.parser.parse_source(code, Language.GO)
        func_nodes = find_nodes_by_type(root, {"function_declaration"})
        assert len(func_nodes) == 1

        docstring = get_docstring(func_nodes[0], code, Language.GO)
        assert "HelloWorld says hello to the world." in docstring
        assert "It takes no arguments and returns nothing." in docstring
        assert "This is a detailed description." in docstring

    def test_rust_single_line_doc_comment(self):
        """Test Rust single-line doc comment."""
        code = b"""/// This function does something
fn do_something() {}"""
        root = self.parser.parse_source(code, Language.RUST)
        func_nodes = find_nodes_by_type(root, {"function_item"})
        assert len(func_nodes) == 1

        docstring = get_docstring(func_nodes[0], code, Language.RUST)
        assert docstring == "This function does something"

    def test_rust_multi_line_doc_comments(self):
        """Test Rust multi-line doc comments."""
        code = b"""/// This function does something important.
/// # Arguments
/// * `x` - The first argument
fn do_something(x: i32) {}"""
        root = self.parser.parse_source(code, Language.RUST)
        func_nodes = find_nodes_by_type(root, {"function_item"})
        assert len(func_nodes) == 1

        docstring = get_docstring(func_nodes[0], code, Language.RUST)
        assert "This function does something important." in docstring
        assert "# Arguments" in docstring
        assert "`x` - The first argument" in docstring

    def test_ruby_single_line_comment(self):
        """Test Ruby single-line doc comment."""
        code = b"""# Says hello
def hello
end"""
        root = self.parser.parse_source(code, Language.RUBY)
        func_nodes = find_nodes_by_type(root, {"method"})
        assert len(func_nodes) == 1

        docstring = get_docstring(func_nodes[0], code, Language.RUBY)
        assert docstring == "Says hello"

    def test_ruby_multi_line_comments(self):
        """Test Ruby multi-line doc comments."""
        code = b"""# Says hello to the given name.
# @param name [String] The name to greet
# @return [String] The greeting message
def hello(name)
end"""
        root = self.parser.parse_source(code, Language.RUBY)
        func_nodes = find_nodes_by_type(root, {"method"})
        assert len(func_nodes) == 1

        docstring = get_docstring(func_nodes[0], code, Language.RUBY)
        assert "Says hello to the given name." in docstring
        assert "@param name" in docstring
        assert "@return" in docstring

    def test_javascript_jsdoc_block(self):
        """Test JavaScript JSDoc block comment."""
        code = b"""/** Says hello to someone */
function hello(name) {}"""
        root = self.parser.parse_source(code, Language.JAVASCRIPT)
        func_nodes = find_nodes_by_type(root, {"function_declaration"})
        assert len(func_nodes) == 1

        docstring = get_docstring(func_nodes[0], code, Language.JAVASCRIPT)
        assert docstring == "Says hello to someone"

    def test_java_javadoc_block(self):
        """Test Java Javadoc block comment."""
        code = b"""class Test {
    /** Says hello to someone */
    public void hello() {}
}"""
        root = self.parser.parse_source(code, Language.JAVA)
        func_nodes = find_nodes_by_type(root, {"method_declaration"})
        assert len(func_nodes) == 1

        docstring = get_docstring(func_nodes[0], code, Language.JAVA)
        assert docstring == "Says hello to someone"

    def test_cpp_doxygen_triple_slash(self):
        """Test C++ Doxygen triple-slash comments."""
        code = b"""/// Brief description.
/// Detailed description.
void hello() {}"""
        root = self.parser.parse_source(code, Language.CPP)
        func_nodes = find_nodes_by_type(root, {"function_definition"})
        assert len(func_nodes) == 1

        docstring = get_docstring(func_nodes[0], code, Language.CPP)
        assert "Brief description." in docstring
        assert "Detailed description." in docstring

    def test_no_docstring(self):
        """Test function without docstring."""
        code = b"""func NoDoc() {}"""
        root = self.parser.parse_source(code, Language.GO)
        func_nodes = find_nodes_by_type(root, {"function_declaration"})
        assert len(func_nodes) == 1

        docstring = get_docstring(func_nodes[0], code, Language.GO)
        assert docstring is None


class TestLargeFileHandling:
    """Tests for memory-efficient large file handling."""

    def test_mmap_threshold_constant(self):
        """Test that MMAP threshold is set to 1 MB."""
        assert MMAP_THRESHOLD_BYTES == 1 * 1024 * 1024

    def test_hash_chunk_size_constant(self):
        """Test that hash chunk size is set to 64 KB."""
        assert HASH_CHUNK_SIZE == 64 * 1024

    def test_read_small_file_directly(self):
        """Test that small files are read directly."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as f:
            content = b"print('hello world')"
            f.write(content)
            f.flush()

            result = _read_file_content(Path(f.name))
            assert result == content

    def test_read_file_content_preserves_bytes(self):
        """Test that file content is preserved exactly."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as f:
            # Include various byte patterns
            content = b"\x00\x01\x02\xff\xfe\xfd hello \xc0\xc1"
            f.write(content)
            f.flush()

            result = _read_file_content(Path(f.name))
            assert result == content

    def test_compute_hash_small_file(self):
        """Test hash computation for small file."""
        import hashlib

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as f:
            content = b"def hello(): pass"
            f.write(content)
            f.flush()

            result = _compute_file_hash(Path(f.name))
            expected = hashlib.sha256(content).hexdigest()
            assert result == expected

    def test_compute_hash_empty_file(self):
        """Test hash computation for empty file."""
        import hashlib

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as f:
            f.flush()

            result = _compute_file_hash(Path(f.name))
            expected = hashlib.sha256(b"").hexdigest()
            assert result == expected

    def test_parser_handles_large_file(self):
        """Test that parser can handle files above mmap threshold."""
        # Create a file slightly above threshold
        parser = CodeParser()
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as f:
            # Create a valid Python file with content above threshold
            content = b"# Large file\n" + b"x = 1\n" * (MMAP_THRESHOLD_BYTES // 6 + 1000)
            f.write(content)
            f.flush()

            # Should be able to parse without memory issues
            result = parser.parse_file(Path(f.name))
            assert result is not None
            root, lang, source = result
            assert lang == Language.PYTHON
            assert len(source) > MMAP_THRESHOLD_BYTES

    def test_get_file_info_large_file(self):
        """Test get_file_info uses chunked hashing for large files."""
        import hashlib

        parser = CodeParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            large_file = root / "large.py"

            # Create file above threshold
            content = b"# Large file\n" + b"y = 2\n" * (MMAP_THRESHOLD_BYTES // 6 + 1000)
            large_file.write_bytes(content)

            file_info = parser.get_file_info(large_file, root)

            # Hash should be correct
            expected_hash = hashlib.sha256(content).hexdigest()
            assert file_info.hash == expected_hash
            assert file_info.size_bytes > MMAP_THRESHOLD_BYTES

    def test_hash_consistency_small_and_large(self):
        """Test that hash is consistent regardless of file size."""
        import hashlib

        content = b"Same content for both"

        # Small file (below threshold)
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(content)
            f.flush()
            small_hash = _compute_file_hash(Path(f.name))

        # Large file (above threshold, padded)
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            # Same content but padded to exceed threshold
            large_content = content + b"\n" * MMAP_THRESHOLD_BYTES
            f.write(large_content)
            f.flush()
            large_hash = _compute_file_hash(Path(f.name))

        # Hashes should be different since content is different
        assert small_hash != large_hash
        # But each should match standard hashlib
        assert small_hash == hashlib.sha256(content).hexdigest()
        assert large_hash == hashlib.sha256(large_content).hexdigest()
