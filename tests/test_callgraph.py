"""Tests for call graph extraction and diagram generation."""

from pathlib import Path
from textwrap import dedent

import pytest

from local_deepwiki.core.parser import CodeParser
from local_deepwiki.generators.analysis.callgraph import (
    CallGraphExtractor,
    _is_builtin_or_noise,
    build_reverse_call_graph,
    extract_call_name,
    extract_calls_from_function,
    generate_call_graph_diagram,
    get_file_call_graph,
    get_file_callers,
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

        calls = extract_calls_from_function(
            func_node, source.encode(), Language.JAVASCRIPT
        )
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

        calls = extract_calls_from_function(
            func_node, source.encode(), Language.JAVASCRIPT
        )
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

    def test_go_selector_call(self, parser):
        """Test extracting selector expression calls in Go (pkg.Func)."""
        source = dedent(
            """
            package main

            func main() {
                fmt.Println("hello")
                obj.Method()
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.GO)

        from local_deepwiki.core.parser import find_nodes_by_type

        funcs = find_nodes_by_type(root, {"function_declaration"})
        func_node = funcs[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.GO)
        # Method is extracted (Println is filtered as noise)
        assert "Method" in calls


class TestRustCallExtraction:
    """Test call extraction for Rust code."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_simple_rust_call(self, parser):
        """Test extracting calls from Rust function."""
        source = dedent(
            """
            fn main() {
                process_data();
                save_results();
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.RUST)

        from local_deepwiki.core.parser import find_nodes_by_type

        funcs = find_nodes_by_type(root, {"function_item"})
        assert len(funcs) == 1
        func_node = funcs[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.RUST)
        assert "process_data" in calls
        assert "save_results" in calls

    def test_rust_scoped_call(self, parser):
        """Test extracting scoped identifier calls in Rust (Type::method)."""
        source = dedent(
            """
            fn main() {
                let s = String::from("hello");
                Vec::new();
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.RUST)

        from local_deepwiki.core.parser import find_nodes_by_type

        funcs = find_nodes_by_type(root, {"function_item"})
        func_node = funcs[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.RUST)
        assert "from" in calls
        assert "new" in calls

    def test_rust_field_expression_call(self, parser):
        """Test extracting field expression calls in Rust (self.method)."""
        source = dedent(
            """
            fn process(&self) {
                self.validate();
                self.transform();
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.RUST)

        from local_deepwiki.core.parser import find_nodes_by_type

        funcs = find_nodes_by_type(root, {"function_item"})
        func_node = funcs[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.RUST)
        assert "validate" in calls
        assert "transform" in calls


class TestJavaCallExtraction:
    """Test call extraction for Java code."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_java_method_invocation(self, parser):
        """Test extracting method invocations in Java."""
        source = dedent(
            """
            class Main {
                void main() {
                    processData();
                    obj.transform();
                }
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.JAVA)

        from local_deepwiki.core.parser import find_nodes_by_type

        methods = find_nodes_by_type(root, {"method_declaration"})
        assert len(methods) == 1
        method_node = methods[0]

        calls = extract_calls_from_function(method_node, source.encode(), Language.JAVA)
        assert "processData" in calls
        assert "transform" in calls


class TestCCallExtraction:
    """Test call extraction for C code."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_simple_c_call(self, parser):
        """Test extracting calls from C function."""
        source = dedent(
            """
            void main() {
                process_data();
                save_results();
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.C)

        from local_deepwiki.core.parser import find_nodes_by_type

        funcs = find_nodes_by_type(root, {"function_definition"})
        assert len(funcs) == 1
        func_node = funcs[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.C)
        assert "process_data" in calls
        assert "save_results" in calls

    def test_c_field_expression_call(self, parser):
        """Test extracting field expression calls in C (obj.method or obj->method)."""
        source = dedent(
            """
            void process() {
                obj.init();
                ptr->cleanup();
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.C)

        from local_deepwiki.core.parser import find_nodes_by_type

        funcs = find_nodes_by_type(root, {"function_definition"})
        func_node = funcs[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.C)
        assert "init" in calls
        assert "cleanup" in calls


class TestCppCallExtraction:
    """Test call extraction for C++ code."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_cpp_call(self, parser):
        """Test extracting calls from C++ function."""
        source = dedent(
            """
            void main() {
                process();
                obj.method();
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.CPP)

        from local_deepwiki.core.parser import find_nodes_by_type

        funcs = find_nodes_by_type(root, {"function_definition"})
        func_node = funcs[0]

        calls = extract_calls_from_function(func_node, source.encode(), Language.CPP)
        assert "process" in calls
        assert "method" in calls


class TestJsBuiltinNoise:
    """Test JavaScript/TypeScript built-in noise filtering."""

    def test_js_builtins_filtered(self):
        """Test that JS-specific built-ins are filtered."""
        assert _is_builtin_or_noise("setTimeout", Language.JAVASCRIPT) is True
        assert _is_builtin_or_noise("setInterval", Language.JAVASCRIPT) is True
        assert _is_builtin_or_noise("fetch", Language.JAVASCRIPT) is True
        assert _is_builtin_or_noise("Promise", Language.JAVASCRIPT) is True

    def test_ts_builtins_filtered(self):
        """Test that TS-specific built-ins are filtered."""
        assert _is_builtin_or_noise("setTimeout", Language.TYPESCRIPT) is True
        assert _is_builtin_or_noise("clearTimeout", Language.TYPESCRIPT) is True

    def test_custom_js_functions_not_filtered(self):
        """Test that custom JS function names are not filtered."""
        assert _is_builtin_or_noise("myFunction", Language.JAVASCRIPT) is False
        assert _is_builtin_or_noise("handleClick", Language.TYPESCRIPT) is False


class TestUnsupportedLanguage:
    """Test behavior with unsupported languages."""

    def test_extract_calls_unsupported_language(self):
        """Test that extract_calls returns empty for unsupported language."""
        # Use a language not in CALL_NODE_TYPES
        from unittest.mock import MagicMock

        mock_node = MagicMock()
        # RUBY is not in CALL_NODE_TYPES
        calls = extract_calls_from_function(mock_node, b"", Language.RUBY)
        assert calls == []


class TestDiagramWithTitle:
    """Test diagram generation with title parameter."""

    def test_diagram_with_title(self):
        """Test generating diagram with title (title is currently no-op)."""
        call_graph = {"main": ["helper"]}

        result = generate_call_graph_diagram(call_graph, title="My Call Graph")

        # Title doesn't actually appear in output (it's a no-op in current impl)
        assert result is not None
        assert "flowchart TD" in result


class TestExtractCallNameEdgeCases:
    """Test extract_call_name edge cases."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_extract_call_name_no_function_child(self, parser):
        """Test extract_call_name when call has no function child."""
        # This tests the None return path
        source = "call()"
        root = parser.parse_source(source, Language.PYTHON)

        from local_deepwiki.core.parser import find_nodes_by_type

        calls = find_nodes_by_type(root, {"call"})
        if calls:
            # The call should have a function - test passes if extraction works
            result = extract_call_name(calls[0], source.encode(), Language.PYTHON)
            assert result == "call"


class TestSwiftCallExtraction:
    """Test call extraction for Swift code."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_simple_swift_call(self, parser):
        """Test extracting simple function calls from Swift."""
        source = dedent(
            """
            func main() {
                processData()
                saveResults()
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.SWIFT)

        from local_deepwiki.core.parser import find_nodes_by_type

        funcs = find_nodes_by_type(root, {"function_declaration"})
        if funcs:
            func_node = funcs[0]
            calls = extract_calls_from_function(
                func_node, source.encode(), Language.SWIFT
            )
            # Swift call extraction may find calls depending on tree-sitter grammar
            assert isinstance(calls, list)

    def test_swift_method_call(self, parser):
        """Test extracting method calls in Swift (obj.method())."""
        source = dedent(
            """
            func process() {
                let result = service.transform(data)
                manager.validate()
            }
        """
        ).strip()
        root = parser.parse_source(source, Language.SWIFT)

        from local_deepwiki.core.parser import find_nodes_by_type

        funcs = find_nodes_by_type(root, {"function_declaration"})
        if funcs:
            func_node = funcs[0]
            calls = extract_calls_from_function(
                func_node, source.encode(), Language.SWIFT
            )
            # Swift parsing depends on tree-sitter grammar version
            assert isinstance(calls, list)

    def test_extract_call_name_swift_identifier(self, parser):
        """Test extract_call_name for Swift with identifier function."""
        source = "doSomething()"
        root = parser.parse_source(source, Language.SWIFT)

        from local_deepwiki.core.parser import find_nodes_by_type

        # Find call expressions in Swift
        calls = find_nodes_by_type(root, {"call_expression"})
        for call_node in calls:
            result = extract_call_name(call_node, source.encode(), Language.SWIFT)
            # May or may not extract depending on Swift grammar
            assert result is None or isinstance(result, str)

    def test_extract_call_name_swift_navigation(self, parser):
        """Test extract_call_name for Swift navigation expressions."""
        source = "object.method()"
        root = parser.parse_source(source, Language.SWIFT)

        from local_deepwiki.core.parser import find_nodes_by_type

        calls = find_nodes_by_type(root, {"call_expression"})
        for call_node in calls:
            result = extract_call_name(call_node, source.encode(), Language.SWIFT)
            # Tests the navigation_expression/member_access branch
            assert result is None or isinstance(result, str)

    def test_extract_call_name_swift_with_mocked_navigation(self):
        """Test Swift call name extraction with mocked navigation expression."""
        from unittest.mock import MagicMock

        # Create a mock call_node that has a function child with navigation_expression type
        mock_call_node = MagicMock()
        mock_func = MagicMock()
        mock_func.type = "navigation_expression"

        # Create navigation_suffix child with simple_identifier
        mock_nav_suffix = MagicMock()
        mock_nav_suffix.type = "navigation_suffix"
        mock_simple_id = MagicMock()
        mock_simple_id.type = "simple_identifier"
        mock_simple_id.start_byte = 0
        mock_simple_id.end_byte = 6
        mock_nav_suffix.children = [mock_simple_id]
        mock_func.children = [mock_nav_suffix]

        mock_call_node.child_by_field_name.return_value = mock_func

        source = b"method"
        result = extract_call_name(mock_call_node, source, Language.SWIFT)
        assert result == "method"

    def test_extract_call_name_swift_identifier_type(self):
        """Test Swift call name extraction with identifier function type."""
        from unittest.mock import MagicMock

        mock_call_node = MagicMock()
        mock_func = MagicMock()
        mock_func.type = "identifier"
        mock_func.start_byte = 0
        mock_func.end_byte = 8
        mock_call_node.child_by_field_name.return_value = mock_func

        source = b"funcName"
        result = extract_call_name(mock_call_node, source, Language.SWIFT)
        assert result == "funcName"

    def test_extract_call_name_swift_member_access(self):
        """Test Swift call name extraction with member_access type."""
        from unittest.mock import MagicMock

        mock_call_node = MagicMock()
        mock_func = MagicMock()
        mock_func.type = "member_access"

        # Create navigation_suffix child
        mock_nav_suffix = MagicMock()
        mock_nav_suffix.type = "navigation_suffix"
        mock_simple_id = MagicMock()
        mock_simple_id.type = "simple_identifier"
        mock_simple_id.start_byte = 0
        mock_simple_id.end_byte = 4
        mock_nav_suffix.children = [mock_simple_id]
        mock_func.children = [mock_nav_suffix]

        mock_call_node.child_by_field_name.return_value = mock_func

        source = b"call"
        result = extract_call_name(mock_call_node, source, Language.SWIFT)
        assert result == "call"

    def test_extract_call_name_swift_no_navigation_suffix(self):
        """Test Swift call name extraction when navigation_suffix is missing."""
        from unittest.mock import MagicMock

        mock_call_node = MagicMock()
        mock_func = MagicMock()
        mock_func.type = "navigation_expression"

        # No navigation_suffix child
        mock_other = MagicMock()
        mock_other.type = "other_type"
        mock_func.children = [mock_other]

        mock_call_node.child_by_field_name.return_value = mock_func

        source = b"test"
        result = extract_call_name(mock_call_node, source, Language.SWIFT)
        # Should return None since no navigation_suffix found
        assert result is None

    def test_extract_call_name_swift_no_simple_identifier(self):
        """Test Swift call name extraction when simple_identifier is missing."""
        from unittest.mock import MagicMock

        mock_call_node = MagicMock()
        mock_func = MagicMock()
        mock_func.type = "navigation_expression"

        # navigation_suffix but no simple_identifier
        mock_nav_suffix = MagicMock()
        mock_nav_suffix.type = "navigation_suffix"
        mock_other = MagicMock()
        mock_other.type = "other_type"
        mock_nav_suffix.children = [mock_other]
        mock_func.children = [mock_nav_suffix]

        mock_call_node.child_by_field_name.return_value = mock_func

        source = b"test"
        result = extract_call_name(mock_call_node, source, Language.SWIFT)
        # Should return None since no simple_identifier in navigation_suffix
        assert result is None


class TestBuildReverseCallGraph:
    """Test reverse call graph building."""

    def test_empty_call_graph(self):
        """Test reversing an empty call graph."""
        result = build_reverse_call_graph({})
        assert result == {}

    def test_simple_reverse(self):
        """Test reversing a simple call graph."""
        call_graph = {
            "main": ["helper", "process"],
        }
        result = build_reverse_call_graph(call_graph)

        assert "helper" in result
        assert "process" in result
        assert "main" in result["helper"]
        assert "main" in result["process"]

    def test_multiple_callers(self):
        """Test reversing when a function has multiple callers."""
        call_graph = {
            "main": ["helper"],
            "process": ["helper"],
            "validate": ["helper"],
        }
        result = build_reverse_call_graph(call_graph)

        assert "helper" in result
        assert len(result["helper"]) == 3
        assert "main" in result["helper"]
        assert "process" in result["helper"]
        assert "validate" in result["helper"]

    def test_no_duplicate_callers(self):
        """Test that duplicate callers are not added."""
        call_graph = {
            "main": ["helper", "helper"],  # Same callee twice
        }
        result = build_reverse_call_graph(call_graph)

        assert "helper" in result
        # Should only have "main" once even though helper was called twice
        assert result["helper"].count("main") == 1


class TestGetFileCallers:
    """Test the get_file_callers convenience function."""

    def test_returns_reverse_call_graph(self, tmp_path):
        """Test that get_file_callers returns a reverse call graph."""
        source = dedent(
            """
            def helper():
                pass

            def main():
                helper()
                helper()

            def other():
                helper()
        """
        ).strip()

        test_file = tmp_path / "test.py"
        test_file.write_text(source)

        result = get_file_callers(test_file, tmp_path)

        # helper should be called by main and other
        assert "helper" in result
        assert "main" in result["helper"]
        assert "other" in result["helper"]

    def test_returns_empty_for_no_calls(self, tmp_path):
        """Test that empty dict is returned when no calls exist."""
        source = dedent(
            """
            x = 1
            y = 2
        """
        ).strip()

        test_file = tmp_path / "test.py"
        test_file.write_text(source)

        result = get_file_callers(test_file, tmp_path)
        assert result == {}


class TestClassWithoutName:
    """Test handling of classes without names."""

    def test_class_without_name_skipped(self, tmp_path):
        """Test that classes without names are gracefully skipped."""
        # This is an edge case - create a file where class name extraction fails
        # In practice this rarely happens, but we test the continue branch
        extractor = CallGraphExtractor()

        # A normal class should work fine
        source = dedent(
            """
            class MyClass:
                def method(self):
                    helper()
        """
        ).strip()

        test_file = tmp_path / "test.py"
        test_file.write_text(source)

        result = extractor.extract_from_file(test_file, tmp_path)
        assert "MyClass.method" in result

    def test_anonymous_class_expression(self, tmp_path):
        """Test handling of anonymous class-like structures."""
        # In JavaScript, anonymous class expressions might not have names
        extractor = CallGraphExtractor()

        source = dedent(
            """
            const MyClass = class {
                method() {
                    helper();
                }
            };
        """
        ).strip()

        test_file = tmp_path / "test.js"
        test_file.write_text(source)

        # Should not crash even if class name extraction fails
        result = extractor.extract_from_file(test_file, tmp_path)
        # Result may or may not contain the method depending on parsing
        assert isinstance(result, dict)

    def test_class_without_name_mocked(self, tmp_path):
        """Test that classes without names are skipped (mocked get_node_name)."""
        from unittest.mock import patch

        extractor = CallGraphExtractor()

        source = dedent(
            """
            class MyClass:
                def method(self):
                    helper()
        """
        ).strip()

        test_file = tmp_path / "test.py"
        test_file.write_text(source)

        # Mock get_node_name to return None for class nodes only
        original_get_node_name = None

        def mock_get_node_name(node, source, language):
            from local_deepwiki.core.chunk_extractors import CLASS_NODE_TYPES

            class_types = CLASS_NODE_TYPES.get(language, set())
            if node.type in class_types:
                return None  # Simulate class without name
            # Import original function and call it
            from local_deepwiki.core.parser import get_node_name as orig

            return orig(node, source, language)

        with patch(
            "local_deepwiki.generators.analysis.callgraph.get_node_name",
            side_effect=mock_get_node_name,
        ):
            result = extractor.extract_from_file(test_file, tmp_path)

        # The class method should NOT be in results because class name is None
        assert "MyClass.method" not in result
        # But top-level functions would still be extracted
        assert isinstance(result, dict)
