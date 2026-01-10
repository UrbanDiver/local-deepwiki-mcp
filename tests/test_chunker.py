"""Tests for the code chunker."""

from pathlib import Path

import pytest

from local_deepwiki.core.chunker import CodeChunker
from local_deepwiki.models import ChunkType, Language


class TestCodeChunker:
    """Test suite for CodeChunker."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = CodeChunker()

    def test_chunk_python_file(self, tmp_path):
        """Test chunking a Python file."""
        code = '''"""Module docstring."""

import os
from pathlib import Path

def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

class Greeter:
    """A class that greets people."""

    def __init__(self, prefix: str = "Hello"):
        self.prefix = prefix

    def greet(self, name: str) -> str:
        """Greet someone."""
        return f"{self.prefix}, {name}!"
'''
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        # Should have: module, imports, function, class
        assert len(chunks) >= 3

        # Check chunk types
        chunk_types = {c.chunk_type for c in chunks}
        assert ChunkType.MODULE in chunk_types
        assert ChunkType.IMPORT in chunk_types

        # Check that we have a function or class chunk
        assert ChunkType.FUNCTION in chunk_types or ChunkType.CLASS in chunk_types

    def test_chunk_extracts_function_names(self, tmp_path):
        """Test that function names are extracted."""
        code = '''
def process_data(data):
    return data

def analyze_results(results):
    return results
'''
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))
        function_chunks = [c for c in chunks if c.chunk_type == ChunkType.FUNCTION]

        function_names = {c.name for c in function_chunks}
        assert "process_data" in function_names
        assert "analyze_results" in function_names

    def test_chunk_extracts_class_names(self, tmp_path):
        """Test that class names are extracted."""
        code = '''
class DataProcessor:
    pass

class ResultAnalyzer:
    pass
'''
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))
        class_chunks = [c for c in chunks if c.chunk_type == ChunkType.CLASS]

        class_names = {c.name for c in class_chunks}
        assert "DataProcessor" in class_names
        assert "ResultAnalyzer" in class_names

    def test_chunk_extracts_docstrings(self, tmp_path):
        """Test that docstrings are extracted."""
        code = '''
def documented_function():
    """This function is well documented."""
    pass
'''
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))
        function_chunks = [c for c in chunks if c.chunk_type == ChunkType.FUNCTION]

        assert len(function_chunks) > 0
        func = function_chunks[0]
        assert func.docstring is not None
        assert "well documented" in func.docstring

    def test_chunk_javascript_file(self, tmp_path):
        """Test chunking a JavaScript file."""
        code = '''
import { something } from 'somewhere';

function processData(data) {
    return data.map(x => x * 2);
}

class DataHandler {
    constructor() {
        this.data = [];
    }

    process() {
        return processData(this.data);
    }
}
'''
        test_file = tmp_path / "test.js"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        # Should have at least module and some code chunks
        assert len(chunks) >= 2

        # All chunks should be JavaScript
        for chunk in chunks:
            assert chunk.language == Language.JAVASCRIPT

    def test_chunk_sets_line_numbers(self, tmp_path):
        """Test that line numbers are set correctly."""
        code = '''# Line 1
# Line 2
def my_function():  # Line 3
    pass  # Line 4
'''
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))
        function_chunks = [c for c in chunks if c.chunk_type == ChunkType.FUNCTION]

        assert len(function_chunks) > 0
        func = function_chunks[0]
        assert func.start_line == 3
        assert func.end_line >= 3

    def test_chunk_generates_unique_ids(self, tmp_path):
        """Test that chunk IDs are unique."""
        code = '''
def func1(): pass
def func2(): pass
def func3(): pass
'''
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))
        ids = [c.id for c in chunks]

        # All IDs should be unique
        assert len(ids) == len(set(ids))

    def test_chunk_unsupported_file_returns_empty(self, tmp_path):
        """Test that unsupported files return no chunks."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Just some text")

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))
        assert len(chunks) == 0
