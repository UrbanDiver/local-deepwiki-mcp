"""Tests for call graph extraction and diagram generation."""

from pathlib import Path
from textwrap import dedent

import pytest

from local_deepwiki.core.parser import CodeParser
from local_deepwiki.generators.callgraph import (
    CallGraphExtractor,
    _is_builtin_or_noise,
    extract_call_name,
    extract_calls_from_function,
    generate_call_graph_diagram,
    get_file_call_graph,
)
from local_deepwiki.models import Language


class TestIsBuiltinOrNoise:
    """Test filtering of built-in functions."""

    def test_common_builtins_filtered(self):
        """Test that common built-ins are filtered."""
        assert _is_builtin_or_noise("print", Language.PYTHON) is True
        assert _is_builtin_or_noise("len", Language.PYTHON) is True
        assert _is_builtin_or_noise("str", Language.PYTHON) is True
        assert _is_builtin_or_noise("isinstance", Language.PYTHON) is True

    def test_python_specific_builtins(self):
        """Test Python-specific built-ins are filtered."""
        assert _is_builtin_or_noise("super", Language.PYTHON) is True
        assert _is_builtin_or_noise("next", Language.PYTHON) is True

    def test_custom_functions_not_filtered(self):
        """Test that custom function names are not filtered."""
        assert _is_builtin_or_noise("my_function", Language.PYTHON) is False
        assert _is_builtin_or_noise("calculate_total", Language.PYTHON) is False
        assert _is_builtin_or_noise("process_data", Language.PYTHON) is False


class TestExtractCallsPython:
    """Test call extraction for Python code."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_simple_function_call(self, parser):
        """Test extracting a simple function call."""
        source = dedent(
            """
            def main():
                process_data()
        """
        ).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]  # function_definition

        calls = extract_calls_from_function(func_node, source.encode(), Language.PYTHON)
        assert "process_data" in calls

    def test_multiple_function_calls(self, parser):
        """Test extracting multiple function calls."""
        source = dedent(
            """
            def main():
                load_data()
                process_data()
                save_results()
        """
        ).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.PYTHON)
        assert "load_data" in calls
        assert "process_data" in calls
        assert "save_results" in calls

    def test_method_call(self, parser):
        """Test extracting method calls."""
        source = dedent(
            """
            def process():
                data = loader.load()
                result = processor.transform(data)
        """
        ).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.PYTHON)
        assert "load" in calls
        assert "transform" in calls

    def test_nested_calls(self, parser):
        """Test extracting nested function calls."""
        source = dedent(
            """
            def complex():
                result = outer(inner(value))
        """
        ).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.PYTHON)
        assert "outer" in calls
        assert "inner" in calls

    def test_filters_builtins(self, parser):
        """Test that built-ins are filtered out."""
        source = dedent(
            """
            def main():
                items = list(range(10))
                process(items)
                print(len(items))
        """
        ).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.PYTHON)
        assert "process" in calls
        assert "list" not in calls
        assert "range" not in calls
        assert "print" not in calls
        assert "len" not in calls

    def test_deduplicates_calls(self, parser):
        """Test that duplicate calls are removed."""
        source = dedent(
            """
            def main():
                process()
                process()
                process()
        """
        ).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.PYTHON)
        assert calls.count("process") == 1


class TestCallGraphExtractor:
    """Test the CallGraphExtractor class."""

    @pytest.fixture
    def extractor(self):
        return CallGraphExtractor()

    def test_extract_from_simple_file(self, tmp_path, extractor):
        """Test extracting call graph from a simple Python file."""
        source = dedent(
            """
            def helper():
                pass

            def main():
                helper()
                process()
        """
        ).strip()

        test_file = tmp_path / "test.py"
        test_file.write_text(source)

        call_graph = extractor.extract_from_file(test_file, tmp_path)

        assert "main" in call_graph
        assert "helper" in call_graph["main"]
        assert "process" in call_graph["main"]
        # helper has no calls, so it shouldn't be in the graph as a caller
        assert "helper" not in call_graph

    def test_extract_class_methods(self, tmp_path, extractor):
        """Test extracting call graph with class methods."""
        source = dedent(
            """
            class Processor:
                def process(self):
                    self.validate()
                    self.transform()

                def validate(self):
                    pass

                def transform(self):
                    pass
        """
        ).strip()

        test_file = tmp_path / "test.py"
        test_file.write_text(source)

        call_graph = extractor.extract_from_file(test_file, tmp_path)

        assert "Processor.process" in call_graph
        assert "validate" in call_graph["Processor.process"]
        assert "transform" in call_graph["Processor.process"]

    def test_extract_mixed_functions_and_methods(self, tmp_path, extractor):
        """Test extracting from file with both functions and class methods."""
        source = dedent(
            """
            def standalone():
                helper()

            class MyClass:
                def method(self):
                    external_func()
        """
        ).strip()

        test_file = tmp_path / "test.py"
        test_file.write_text(source)

        call_graph = extractor.extract_from_file(test_file, tmp_path)

        assert "standalone" in call_graph
        assert "helper" in call_graph["standalone"]
        assert "MyClass.method" in call_graph
        assert "external_func" in call_graph["MyClass.method"]


class TestGenerateCallGraphDiagram:
    """Test Mermaid diagram generation."""

    def test_empty_graph_returns_none(self):
        """Test that empty call graph returns None."""
        result = generate_call_graph_diagram({})
        assert result is None

    def test_simple_diagram(self):
        """Test generating a simple diagram."""
        call_graph = {
            "main": ["helper", "process"],
        }

        result = generate_call_graph_diagram(call_graph)

        assert result is not None
        assert "flowchart TD" in result
        assert "main" in result
        assert "helper" in result
        assert "process" in result
        assert "-->" in result

    def test_diagram_with_methods(self):
        """Test diagram distinguishes functions from methods."""
        call_graph = {
            "MyClass.method": ["helper"],
            "standalone": ["MyClass.method"],
        }

        result = generate_call_graph_diagram(call_graph)

        assert result is not None
        # Should have styling for both func and method classes
        assert "classDef func" in result
        assert "classDef method" in result

    def test_limits_nodes(self):
        """Test that diagram limits number of nodes."""
        # Create a large call graph
        call_graph = {f"func_{i}": [f"callee_{i}"] for i in range(50)}

        result = generate_call_graph_diagram(call_graph, max_nodes=10)

        assert result is not None
        # Should have limited nodes
        node_count = result.count("[")  # Each node definition has [name]
        assert node_count <= 10

    def test_sanitizes_long_names(self):
        """Test that long names are truncated."""
        call_graph = {
            "very_long_function_name_that_exceeds_thirty_characters": ["short"],
        }

        result = generate_call_graph_diagram(call_graph)

        assert result is not None
        # Long name should be truncated with ...
        assert "..." in result


class TestGetFileCallGraph:
    """Test the convenience function for getting file call graph."""

    def test_returns_diagram_for_file_with_calls(self, tmp_path):
        """Test that diagram is returned for file with function calls."""
        source = dedent(
            """
            def main():
                helper()

            def helper():
                pass
        """
        ).strip()

        test_file = tmp_path / "test.py"
        test_file.write_text(source)

        result = get_file_call_graph(test_file, tmp_path)

        assert result is not None
        assert "flowchart TD" in result

    def test_returns_none_for_file_without_calls(self, tmp_path):
        """Test that None is returned for file without function calls."""
        source = dedent(
            """
            x = 1
            y = 2
        """
        ).strip()

        test_file = tmp_path / "test.py"
        test_file.write_text(source)

        result = get_file_call_graph(test_file, tmp_path)

        assert result is None

    def test_returns_none_for_unsupported_file(self, tmp_path):
        """Test that None is returned for unsupported file types."""
        test_file = tmp_path / "readme.txt"
        test_file.write_text("This is not code")

        result = get_file_call_graph(test_file, tmp_path)

        assert result is None


class TestJavaScriptCallExtraction:
    """Test call extraction for JavaScript code."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_simple_js_call(self, parser):
        """Test extracting calls from JavaScript function."""
        source = dedent(
            """
            function main() {
                processData();
                saveResults();
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.JAVASCRIPT)
        func_node = root.children[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.JAVASCRIPT)
        assert "processData" in calls
        assert "saveResults" in calls

    def test_js_method_call(self, parser):
        """Test extracting method calls in JavaScript."""
        source = dedent(
            """
            function process() {
                const result = service.transform(data);
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.JAVASCRIPT)
        func_node = root.children[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.JAVASCRIPT)
        assert "transform" in calls


class TestGoCallExtraction:
    """Test call extraction for Go code."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_simple_go_call(self, parser):
        """Test extracting calls from Go function."""
        source = dedent(
            """
            package main

            func main() {
                processData()
                saveResults()
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.GO)

        # Find the function declaration
        from local_deepwiki.core.parser import find_nodes_by_type

        funcs = find_nodes_by_type(root, {"function_declaration"})
        assert len(funcs) == 1
        func_node = funcs[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.GO)
        assert "processData" in calls
        assert "saveResults" in calls
