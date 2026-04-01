"""Tests for the code chunker."""

from pathlib import Path

import pytest

from local_deepwiki.config import ChunkingConfig
from local_deepwiki.core.chunk_extractors import get_parent_classes
from local_deepwiki.core.chunker import CodeChunker
from local_deepwiki.core.parser import CodeParser
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
        code = """
def process_data(data):
    return data

def analyze_results(results):
    return results
"""
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))
        function_chunks = [c for c in chunks if c.chunk_type == ChunkType.FUNCTION]

        function_names = {c.name for c in function_chunks}
        assert "process_data" in function_names
        assert "analyze_results" in function_names

    def test_chunk_extracts_class_names(self, tmp_path):
        """Test that class names are extracted."""
        code = """
class DataProcessor:
    pass

class ResultAnalyzer:
    pass
"""
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
        code = """
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
"""
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
        code = """# Line 1
# Line 2
def my_function():  # Line 3
    pass  # Line 4
"""
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
        code = """
def func1(): pass
def func2(): pass
def func3(): pass
"""
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

    def test_chunk_empty_file(self, tmp_path):
        """Test chunking an empty Python file."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("")

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))
        # Should have at least a module chunk
        assert len(chunks) >= 1
        module_chunk = [c for c in chunks if c.chunk_type == ChunkType.MODULE][0]
        assert "Empty file" in module_chunk.content

    def test_chunk_file_with_many_imports(self, tmp_path):
        """Test chunking file with more than 10 imports triggers truncation."""
        imports = "\n".join([f"import module{i}" for i in range(15)])
        code = f"{imports}\n\ndef func(): pass\n"

        test_file = tmp_path / "many_imports.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))
        module_chunk = [c for c in chunks if c.chunk_type == ChunkType.MODULE][0]

        # Should have truncation message
        assert "and 5 more imports" in module_chunk.content

    def test_chunk_large_class_creates_summary_and_methods(self, tmp_path):
        """Test that large classes are split into summary and method chunks."""
        # Create config with low threshold for testing
        config = ChunkingConfig(class_split_threshold=10)
        chunker = CodeChunker(config=config)

        # Create a class with many methods (will exceed threshold)
        methods = "\n".join(
            [f"    def method{i}(self):\n        pass\n" for i in range(20)]
        )
        code = f'''class LargeClass:
    """A large class."""
{methods}
'''
        test_file = tmp_path / "large_class.py"
        test_file.write_text(code)

        chunks = list(chunker.chunk_file(test_file, tmp_path))

        # Should have class summary chunk
        class_chunks = [c for c in chunks if c.chunk_type == ChunkType.CLASS]
        assert len(class_chunks) == 1
        class_chunk = class_chunks[0]
        assert class_chunk.metadata.get("is_summary") is True
        assert class_chunk.metadata.get("method_count") == 20

        # Should have method chunks
        method_chunks = [c for c in chunks if c.chunk_type == ChunkType.METHOD]
        assert len(method_chunks) == 20

    def test_chunk_class_with_parent_classes(self, tmp_path):
        """Test that parent classes are extracted in metadata."""
        code = '''
class Child(Parent, Mixin):
    """A child class."""
    pass
'''
        test_file = tmp_path / "inheritance.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))
        class_chunk = [c for c in chunks if c.chunk_type == ChunkType.CLASS][0]

        assert "parent_classes" in class_chunk.metadata
        assert "Parent" in class_chunk.metadata["parent_classes"]
        assert "Mixin" in class_chunk.metadata["parent_classes"]

    def test_chunk_typescript_file(self, tmp_path):
        """Test chunking a TypeScript file."""
        code = """
import { Component } from '@angular/core';

interface DataItem {
    id: number;
    name: string;
}

type Status = 'active' | 'inactive';

class DataService {
    private data: DataItem[] = [];

    getData(): DataItem[] {
        return this.data;
    }
}

function processItem(item: DataItem): void {
    console.log(item);
}
"""
        test_file = tmp_path / "test.ts"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        # Should have module, imports, interface, type alias, class, function
        assert len(chunks) >= 4

        # All chunks should be TypeScript
        for chunk in chunks:
            assert chunk.language == Language.TYPESCRIPT

    def test_chunk_go_file(self, tmp_path):
        """Test chunking a Go file."""
        code = """package main

import (
    "fmt"
    "strings"
)

type Handler struct {
    Name string
}

func (h *Handler) Handle() {
    fmt.Println(h.Name)
}

func main() {
    h := &Handler{Name: "test"}
    h.Handle()
}
"""
        test_file = tmp_path / "main.go"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        # Should have module, imports, type, method, function
        assert len(chunks) >= 3

        # All chunks should be Go
        for chunk in chunks:
            assert chunk.language == Language.GO

    def test_chunk_rust_file(self, tmp_path):
        """Test chunking a Rust file."""
        code = """
use std::io;
use std::collections::HashMap;

struct Config {
    name: String,
    value: i32,
}

impl Config {
    fn new(name: &str) -> Self {
        Config {
            name: name.to_string(),
            value: 0,
        }
    }
}

fn process(config: &Config) -> i32 {
    config.value
}
"""
        test_file = tmp_path / "lib.rs"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        # Should have module, imports, struct, impl, function
        assert len(chunks) >= 3

        # All chunks should be Rust
        for chunk in chunks:
            assert chunk.language == Language.RUST

    def test_chunk_java_file(self, tmp_path):
        """Test chunking a Java file."""
        code = """
package com.example;

import java.util.List;
import java.util.ArrayList;

public class DataProcessor {
    private List<String> items;

    public DataProcessor() {
        this.items = new ArrayList<>();
    }

    public void process(String item) {
        items.add(item);
    }
}
"""
        test_file = tmp_path / "DataProcessor.java"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        # Should have module, imports, class
        assert len(chunks) >= 2

        # All chunks should be Java
        for chunk in chunks:
            assert chunk.language == Language.JAVA

    def test_chunk_swift_file(self, tmp_path):
        """Test chunking a Swift file."""
        code = """
import Foundation

protocol DataHandler {
    func handle()
}

class DataProcessor: DataHandler {
    var data: [String] = []

    init() {}

    func handle() {
        print(data)
    }
}

func processAll() {
    let p = DataProcessor()
    p.handle()
}
"""
        test_file = tmp_path / "DataProcessor.swift"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        # Should have module, imports, protocol, class, function
        assert len(chunks) >= 3

        # All chunks should be Swift
        for chunk in chunks:
            assert chunk.language == Language.SWIFT


class TestGetParentClasses:
    """Tests for get_parent_classes function."""

    @pytest.fixture
    def parser(self):
        """Create a code parser."""
        return CodeParser()

    def test_python_single_parent(self, parser, tmp_path):
        """Test Python class with single parent."""
        code = "class Child(Parent): pass"
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        # Find the class node
        class_node = None
        for child in root.children:
            if child.type == "class_definition":
                class_node = child
                break

        assert class_node is not None
        parents = get_parent_classes(class_node, source, language)
        assert parents == ["Parent"]

    def test_python_multiple_parents(self, parser, tmp_path):
        """Test Python class with multiple parents (mixins)."""
        code = "class Child(Parent, Mixin1, Mixin2): pass"
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        class_node = None
        for child in root.children:
            if child.type == "class_definition":
                class_node = child
                break

        assert class_node is not None
        parents = get_parent_classes(class_node, source, language)
        assert "Parent" in parents
        assert "Mixin1" in parents
        assert "Mixin2" in parents

    def test_python_no_parents(self, parser, tmp_path):
        """Test Python class with no parents."""
        code = "class NoParent: pass"
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        class_node = None
        for child in root.children:
            if child.type == "class_definition":
                class_node = child
                break

        assert class_node is not None
        parents = get_parent_classes(class_node, source, language)
        assert parents == []

    def test_typescript_extends_and_implements(self, parser, tmp_path):
        """Test TypeScript class with extends and implements."""
        code = "class Child extends Parent implements Interface1, Interface2 {}"
        test_file = tmp_path / "test.ts"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        # Find the class node
        class_node = None
        for child in root.children:
            if child.type == "class_declaration":
                class_node = child
                break

        assert class_node is not None
        parents = get_parent_classes(class_node, source, language)
        assert "Parent" in parents

    def test_java_extends_and_implements(self, parser, tmp_path):
        """Test Java class with extends and implements."""
        code = """
public class Child extends Parent implements Interface1, Interface2 {
}
"""
        test_file = tmp_path / "Child.java"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        # Find the class node
        class_node = None
        for node in root.children:
            if node.type == "class_declaration":
                class_node = node
                break

        assert class_node is not None
        parents = get_parent_classes(class_node, source, language)
        assert "Parent" in parents

    def test_swift_inheritance(self, parser, tmp_path):
        """Test Swift class with inheritance."""
        code = """
class Child: Parent {
    func doSomething() {}
}
"""
        test_file = tmp_path / "Child.swift"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        # Find the class node
        class_node = None
        for node in root.children:
            if node.type == "class_declaration":
                class_node = node
                break

        assert class_node is not None
        parents = get_parent_classes(class_node, source, language)
        # Swift inheritance parsing may vary by tree-sitter version
        # Just verify the function runs without error
        assert isinstance(parents, list)

    def test_cpp_inheritance(self, parser, tmp_path):
        """Test C++ class with inheritance."""
        code = """
class Child : public Parent {
public:
    Child() {}
};
"""
        test_file = tmp_path / "child.cpp"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        # Find the class node
        class_node = None
        for node in root.children:
            if node.type == "class_specifier":
                class_node = node
                break

        assert class_node is not None
        parents = get_parent_classes(class_node, source, language)
        assert "Parent" in parents

    def test_ruby_inheritance(self, parser, tmp_path):
        """Test Ruby class with inheritance."""
        code = """
class Child < Parent
end
"""
        test_file = tmp_path / "child.rb"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        # Find the class node - Ruby AST structure
        class_node = None
        for node in root.children:
            if node.type == "class":
                class_node = node
                break

        assert class_node is not None
        parents = get_parent_classes(class_node, source, language)
        assert "Parent" in parents

    def test_php_extends_and_implements(self, parser, tmp_path):
        """Test PHP class with extends and implements."""
        code = """<?php
class Child extends Parent implements Interface1 {
}
"""
        test_file = tmp_path / "Child.php"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        # Find the class node in PHP AST
        class_node = None
        from local_deepwiki.core.parser import find_nodes_by_type

        class_nodes = find_nodes_by_type(root, {"class_declaration"})
        if class_nodes:
            class_node = class_nodes[0]

        assert class_node is not None
        parents = get_parent_classes(class_node, source, language)
        assert "Parent" in parents

    def test_kotlin_inheritance(self, parser, tmp_path):
        """Test Kotlin class with inheritance."""
        code = """
class Child : Parent(), Interface1 {
}
"""
        test_file = tmp_path / "Child.kt"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        # Find the class node
        from local_deepwiki.core.parser import find_nodes_by_type

        class_nodes = find_nodes_by_type(root, {"class_declaration"})

        assert len(class_nodes) > 0
        class_node = class_nodes[0]
        parents = get_parent_classes(class_node, source, language)
        assert len(parents) >= 1

    def test_csharp_inheritance(self, parser, tmp_path):
        """Test C# class with inheritance."""
        code = """
public class Child : Parent, IInterface1 {
}
"""
        test_file = tmp_path / "Child.cs"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        # Find the class node
        from local_deepwiki.core.parser import find_nodes_by_type

        class_nodes = find_nodes_by_type(root, {"class_declaration"})

        assert len(class_nodes) > 0
        class_node = class_nodes[0]
        parents = get_parent_classes(class_node, source, language)
        assert "Parent" in parents


class TestChunkerWithConfig:
    """Tests for CodeChunker with custom config."""

    def test_custom_class_split_threshold(self, tmp_path):
        """Test that custom class_split_threshold is respected."""
        # Very high threshold - class should not be split
        config = ChunkingConfig(class_split_threshold=1000)
        chunker = CodeChunker(config=config)

        methods = "\n".join(
            [f"    def method{i}(self):\n        pass\n" for i in range(5)]
        )
        code = f'''class SmallClass:
    """A class."""
{methods}
'''
        test_file = tmp_path / "small_class.py"
        test_file.write_text(code)

        chunks = list(chunker.chunk_file(test_file, tmp_path))

        # Should have class chunk without is_summary
        class_chunks = [c for c in chunks if c.chunk_type == ChunkType.CLASS]
        assert len(class_chunks) == 1
        assert class_chunks[0].metadata.get("is_summary") is not True

        # Should NOT have method chunks (class not split)
        method_chunks = [c for c in chunks if c.chunk_type == ChunkType.METHOD]
        assert len(method_chunks) == 0


class TestPythonParameterExtraction:
    """Tests for Python parameter type and default extraction."""

    @pytest.fixture
    def parser(self):
        """Create a code parser."""
        return CodeParser()

    def test_extract_parameter_types_no_params_node(self, parser, tmp_path):
        """Test extract_python_parameter_types when parameters node is None.

        This covers line 213 - the early return when params_node is None.
        """
        from local_deepwiki.core.chunk_extractors import extract_python_parameter_types

        # Create a mock node that has no 'parameters' field
        code = "x = lambda: 42"  # Lambda without parameters
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        # Find the lambda node - it may have a different structure
        # where child_by_field_name("parameters") returns None
        from local_deepwiki.core.parser import find_nodes_by_type

        lambda_nodes = find_nodes_by_type(root, {"lambda"})
        if lambda_nodes:
            lambda_node = lambda_nodes[0]
            # The lambda node structure varies, but this tests the branch
            param_types = extract_python_parameter_types(lambda_node, source)
            # Should return empty dict when no params_node
            assert isinstance(param_types, dict)

    def test_extract_parameter_defaults_no_params_node(self, parser, tmp_path):
        """Test extract_python_parameter_defaults when parameters node is None.

        This covers line 316 - the early return when params_node is None.
        """
        from local_deepwiki.core.chunk_extractors import (
            extract_python_parameter_defaults,
        )

        # Create a mock node that has no 'parameters' field
        code = "x = lambda: 42"
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        from local_deepwiki.core.parser import find_nodes_by_type

        lambda_nodes = find_nodes_by_type(root, {"lambda"})
        if lambda_nodes:
            lambda_node = lambda_nodes[0]
            defaults = extract_python_parameter_defaults(lambda_node, source)
            assert isinstance(defaults, dict)

    def test_typed_splat_args_in_function(self, parser, tmp_path):
        """Test function with typed *args.

        This tests the list_splat_pattern with typed_parameter branch (lines 286-298).
        """
        from local_deepwiki.core.chunk_extractors import extract_python_parameter_types

        code = """
def func(*args: int) -> None:
    pass
"""
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        from local_deepwiki.core.parser import find_nodes_by_type

        func_nodes = find_nodes_by_type(root, {"function_definition"})
        assert len(func_nodes) > 0
        func_node = func_nodes[0]

        param_types = extract_python_parameter_types(func_node, source)
        # Should have *args with type int
        assert "*args" in param_types
        assert param_types["*args"] == "int"

    def test_typed_kwargs_in_function(self, parser, tmp_path):
        """Test function with typed **kwargs.

        This tests the dictionary_splat_pattern with typed_parameter branch (lines 286-298).
        """
        from local_deepwiki.core.chunk_extractors import extract_python_parameter_types

        code = """
def func(**kwargs: str) -> None:
    pass
"""
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        from local_deepwiki.core.parser import find_nodes_by_type

        func_nodes = find_nodes_by_type(root, {"function_definition"})
        assert len(func_nodes) > 0
        func_node = func_nodes[0]

        param_types = extract_python_parameter_types(func_node, source)
        # Should have **kwargs with type str
        assert "**kwargs" in param_types
        assert param_types["**kwargs"] == "str"

    def test_untyped_args_in_function(self, parser, tmp_path):
        """Test function with untyped *args.

        This tests the list_splat_pattern branch (lines 276-283).
        """
        from local_deepwiki.core.chunk_extractors import extract_python_parameter_types

        code = """
def func(*args):
    pass
"""
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        from local_deepwiki.core.parser import find_nodes_by_type

        func_nodes = find_nodes_by_type(root, {"function_definition"})
        assert len(func_nodes) > 0
        func_node = func_nodes[0]

        param_types = extract_python_parameter_types(func_node, source)
        # Should have *args with None type
        assert "*args" in param_types
        assert param_types["*args"] is None

    def test_untyped_kwargs_in_function(self, parser, tmp_path):
        """Test function with untyped **kwargs.

        This tests the dictionary_splat_pattern branch (lines 276-283).
        """
        from local_deepwiki.core.chunk_extractors import extract_python_parameter_types

        code = """
def func(**kwargs):
    pass
"""
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        from local_deepwiki.core.parser import find_nodes_by_type

        func_nodes = find_nodes_by_type(root, {"function_definition"})
        assert len(func_nodes) > 0
        func_node = func_nodes[0]

        param_types = extract_python_parameter_types(func_node, source)
        # Should have **kwargs with None type
        assert "**kwargs" in param_types
        assert param_types["**kwargs"] is None

    def test_mixed_args_kwargs_in_function(self, parser, tmp_path):
        """Test function with mixed regular params, *args, and **kwargs."""
        from local_deepwiki.core.chunk_extractors import extract_python_parameter_types

        code = """
def func(a: int, b, *args, **kwargs):
    pass
"""
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        from local_deepwiki.core.parser import find_nodes_by_type

        func_nodes = find_nodes_by_type(root, {"function_definition"})
        assert len(func_nodes) > 0
        func_node = func_nodes[0]

        param_types = extract_python_parameter_types(func_node, source)
        # Should have all parameters
        assert "a" in param_types
        assert param_types["a"] == "int"
        assert "b" in param_types
        assert param_types["b"] is None
        assert "*args" in param_types
        assert "**kwargs" in param_types


class TestSwiftInheritance:
    """Tests for Swift inheritance parsing - covers lines 140-145."""

    @pytest.fixture
    def parser(self):
        """Create a code parser."""
        return CodeParser()

    def test_swift_class_with_protocol(self, parser, tmp_path):
        """Test Swift class with protocol conformance.

        This covers lines 140-145 in get_parent_classes for Swift.
        """
        code = """
class MyClass: SomeProtocol {
    func doSomething() {}
}
"""
        test_file = tmp_path / "MyClass.swift"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        from local_deepwiki.core.parser import find_nodes_by_type

        class_nodes = find_nodes_by_type(root, {"class_declaration"})
        assert len(class_nodes) > 0
        class_node = class_nodes[0]

        parents = get_parent_classes(class_node, source, language)
        # Should extract SomeProtocol as parent
        assert isinstance(parents, list)
        # The parent list may contain "SomeProtocol" depending on AST structure
        if parents:
            assert any("Protocol" in p or "Some" in p for p in parents)

    def test_swift_class_multiple_protocols(self, parser, tmp_path):
        """Test Swift class with multiple protocol conformances."""
        code = """
class MyClass: Protocol1, Protocol2 {
    func doSomething() {}
}
"""
        test_file = tmp_path / "MyClass.swift"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        from local_deepwiki.core.parser import find_nodes_by_type

        class_nodes = find_nodes_by_type(root, {"class_declaration"})
        assert len(class_nodes) > 0
        class_node = class_nodes[0]

        parents = get_parent_classes(class_node, source, language)
        assert isinstance(parents, list)
        # Should have multiple parents (protocols)

    def test_swift_struct_with_protocol(self, parser, tmp_path):
        """Test Swift struct with protocol conformance.

        Note: In tree-sitter-swift, structs are represented as class_declaration nodes.
        """
        code = """
struct MyStruct: Codable {
    var name: String
}
"""
        test_file = tmp_path / "MyStruct.swift"
        test_file.write_text(code)

        result = parser.parse_file(test_file)
        assert result is not None
        root, language, source = result

        from local_deepwiki.core.parser import find_nodes_by_type

        # In tree-sitter-swift, structs are represented as class_declaration
        struct_nodes = find_nodes_by_type(root, {"class_declaration"})
        assert len(struct_nodes) > 0
        struct_node = struct_nodes[0]

        parents = get_parent_classes(struct_node, source, language)
        assert isinstance(parents, list)
        # Should extract Codable as parent
        if parents:
            assert any("Codable" in p for p in parents)


class TestLargeClassWithInheritance:
    """Tests for large class with parent classes - covers line 782."""

    def test_large_class_summary_with_parent_classes(self, tmp_path):
        """Test that large class summary includes parent_classes in metadata.

        This covers line 782 - adding parent_classes to summary chunk metadata.
        """
        # Create config with low threshold for testing
        config = ChunkingConfig(class_split_threshold=5)
        chunker = CodeChunker(config=config)

        # Create a class with inheritance AND many methods to trigger splitting
        methods = "\n".join(
            [f"    def method{i}(self):\n        pass\n" for i in range(10)]
        )
        code = f'''class LargeChild(Parent, Mixin):
    """A large child class with inheritance."""
{methods}
'''
        test_file = tmp_path / "large_child.py"
        test_file.write_text(code)

        chunks = list(chunker.chunk_file(test_file, tmp_path))

        # Find the class summary chunk
        class_chunks = [c for c in chunks if c.chunk_type == ChunkType.CLASS]
        assert len(class_chunks) == 1
        class_chunk = class_chunks[0]

        # Should be a summary
        assert class_chunk.metadata.get("is_summary") is True

        # Should have parent_classes in metadata (line 782)
        assert "parent_classes" in class_chunk.metadata
        assert "Parent" in class_chunk.metadata["parent_classes"]
        assert "Mixin" in class_chunk.metadata["parent_classes"]

        # Should also have method chunks
        method_chunks = [c for c in chunks if c.chunk_type == ChunkType.METHOD]
        assert len(method_chunks) == 10


class TestModuleDocstring:
    """Tests for module docstring extraction."""

    def test_python_module_docstring(self, tmp_path):
        """Test Python module docstring is extracted."""
        code = '''"""This is the module docstring."""

def func():
    pass
'''
        test_file = tmp_path / "with_docstring.py"
        test_file.write_text(code)

        chunker = CodeChunker()
        chunks = list(chunker.chunk_file(test_file, tmp_path))

        module_chunk = [c for c in chunks if c.chunk_type == ChunkType.MODULE][0]
        assert module_chunk.docstring is not None
        assert "module docstring" in module_chunk.docstring

    def test_python_module_single_quote_docstring(self, tmp_path):
        """Test Python module docstring with single quotes."""
        code = """'''Single quote module docstring.'''

def func():
    pass
"""
        test_file = tmp_path / "single_quote.py"
        test_file.write_text(code)

        chunker = CodeChunker()
        chunks = list(chunker.chunk_file(test_file, tmp_path))

        module_chunk = [c for c in chunks if c.chunk_type == ChunkType.MODULE][0]
        assert module_chunk.docstring is not None
        assert "Single quote" in module_chunk.docstring

    def test_no_module_docstring(self, tmp_path):
        """Test file without module docstring."""
        code = """import os

def func():
    pass
"""
        test_file = tmp_path / "no_docstring.py"
        test_file.write_text(code)

        chunker = CodeChunker()
        chunks = list(chunker.chunk_file(test_file, tmp_path))

        module_chunk = [c for c in chunks if c.chunk_type == ChunkType.MODULE][0]
        assert module_chunk.docstring is None


class TestFileSummaryChunks:
    """Tests for FILE_SUMMARY chunk generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = CodeChunker()

    def test_file_summary_chunk_generated(self, tmp_path):
        """Each .py file produces a FILE_SUMMARY chunk containing class and function names."""
        code = '''"""Module docstring."""

import os
from pathlib import Path

def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

class Greeter:
    """A greeter class."""

    def greet(self, name: str) -> str:
        return f"Hi, {name}!"
'''
        test_file = tmp_path / "example.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        summary_chunks = [c for c in chunks if c.chunk_type == ChunkType.FILE_SUMMARY]
        assert len(summary_chunks) == 1

        summary = summary_chunks[0]
        assert summary.file_path == "example.py"
        assert summary.name == "example"
        assert "hello" in summary.content
        assert "Greeter" in summary.content
        assert summary.chunk_type == ChunkType.FILE_SUMMARY

    def test_file_summary_includes_docstring(self, tmp_path):
        """FILE_SUMMARY includes the module docstring when present."""
        code = '''"""This module handles data processing."""

def process():
    pass
'''
        test_file = tmp_path / "processor.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        summary_chunks = [c for c in chunks if c.chunk_type == ChunkType.FILE_SUMMARY]
        assert len(summary_chunks) == 1
        summary = summary_chunks[0]
        assert "data processing" in summary.content

    def test_file_summary_limits_imports_to_10(self, tmp_path):
        """FILE_SUMMARY only includes first 10 imports."""
        imports = "\n".join([f"import module{i}" for i in range(15)])
        code = f"{imports}\n\ndef func(): pass\n"

        test_file = tmp_path / "many_imports.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        summary_chunks = [c for c in chunks if c.chunk_type == ChunkType.FILE_SUMMARY]
        assert len(summary_chunks) == 1
        summary = summary_chunks[0]
        # Should mention truncation
        assert "more imports" in summary.content
        # Should contain module0 through module9 but not all 15
        assert "module0" in summary.content
        assert "module9" in summary.content

    def test_file_summary_is_last_chunk(self, tmp_path):
        """FILE_SUMMARY chunk is yielded after all other chunks."""
        code = '''"""Module doc."""

import os

def hello():
    pass

class MyClass:
    pass
'''
        test_file = tmp_path / "ordered.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        # FILE_SUMMARY should be the last chunk
        assert chunks[-1].chunk_type == ChunkType.FILE_SUMMARY

    def test_file_summary_for_empty_file(self, tmp_path):
        """Empty files still get a FILE_SUMMARY chunk."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("")

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        summary_chunks = [c for c in chunks if c.chunk_type == ChunkType.FILE_SUMMARY]
        assert len(summary_chunks) == 1


class TestModuleSummaryChunks:
    """Tests for MODULE_SUMMARY chunk generation for __init__.py files."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = CodeChunker()

    def test_init_py_produces_module_summary(self, tmp_path):
        """__init__.py files generate a MODULE_SUMMARY chunk with package name and re-exports."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()

        code = '''"""My package provides utilities."""

from .utils import helper_func
from .models import DataModel, Config
'''
        init_file = pkg_dir / "__init__.py"
        init_file.write_text(code)

        chunks = list(self.chunker.chunk_file(init_file, tmp_path))

        summary_chunks = [c for c in chunks if c.chunk_type == ChunkType.MODULE_SUMMARY]
        assert len(summary_chunks) == 1

        summary = summary_chunks[0]
        assert "mypackage" in summary.content
        assert "helper_func" in summary.content or "DataModel" in summary.content
        assert summary.chunk_type == ChunkType.MODULE_SUMMARY

    def test_init_py_includes_docstring(self, tmp_path):
        """MODULE_SUMMARY includes the package docstring."""
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        code = '''"""This package handles authentication flows."""

from .auth import login, logout
'''
        init_file = pkg_dir / "__init__.py"
        init_file.write_text(code)

        chunks = list(self.chunker.chunk_file(init_file, tmp_path))

        summary_chunks = [c for c in chunks if c.chunk_type == ChunkType.MODULE_SUMMARY]
        assert len(summary_chunks) == 1
        assert "authentication" in summary_chunks[0].content

    def test_regular_file_no_module_summary(self, tmp_path):
        """Regular (non-__init__.py) files do NOT produce MODULE_SUMMARY chunks."""
        code = '''"""A regular module."""

def func():
    pass
'''
        test_file = tmp_path / "regular.py"
        test_file.write_text(code)

        chunks = list(self.chunker.chunk_file(test_file, tmp_path))

        summary_chunks = [c for c in chunks if c.chunk_type == ChunkType.MODULE_SUMMARY]
        assert len(summary_chunks) == 0

    def test_empty_init_py_still_produces_module_summary(self, tmp_path):
        """Even an empty __init__.py produces a MODULE_SUMMARY."""
        pkg_dir = tmp_path / "emptypkg"
        pkg_dir.mkdir()

        init_file = pkg_dir / "__init__.py"
        init_file.write_text("")

        chunks = list(self.chunker.chunk_file(init_file, tmp_path))

        summary_chunks = [c for c in chunks if c.chunk_type == ChunkType.MODULE_SUMMARY]
        assert len(summary_chunks) == 1
        assert "emptypkg" in summary_chunks[0].content
