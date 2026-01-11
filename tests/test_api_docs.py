"""Tests for API documentation extraction and generation."""

from pathlib import Path
from textwrap import dedent

import pytest

from local_deepwiki.generators.api_docs import (
    APIDocExtractor,
    FunctionSignature,
    ClassSignature,
    Parameter,
    extract_python_parameters,
    extract_python_return_type,
    extract_python_decorators,
    extract_python_docstring,
    parse_google_docstring,
    parse_numpy_docstring,
    parse_docstring,
    extract_function_signature,
    extract_class_signature,
    format_parameter,
    format_function_signature_line,
    generate_api_reference_markdown,
    get_file_api_docs,
)
from local_deepwiki.core.parser import CodeParser
from local_deepwiki.models import Language


class TestParameter:
    """Test Parameter dataclass."""

    def test_basic_parameter(self):
        """Test creating a basic parameter."""
        param = Parameter(name="value")
        assert param.name == "value"
        assert param.type_hint is None
        assert param.default_value is None
        assert param.description is None

    def test_full_parameter(self):
        """Test creating a parameter with all fields."""
        param = Parameter(
            name="count",
            type_hint="int",
            default_value="10",
            description="The number of items.",
        )
        assert param.name == "count"
        assert param.type_hint == "int"
        assert param.default_value == "10"
        assert param.description == "The number of items."


class TestExtractPythonParameters:
    """Test Python parameter extraction."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_simple_parameters(self, parser):
        """Test extracting simple parameters without types."""
        source = dedent("""
            def func(a, b, c):
                pass
        """).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        params = extract_python_parameters(func_node, source.encode())
        assert len(params) == 3
        assert params[0].name == "a"
        assert params[1].name == "b"
        assert params[2].name == "c"

    def test_typed_parameters(self, parser):
        """Test extracting parameters with type hints."""
        source = dedent("""
            def func(name: str, count: int):
                pass
        """).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        params = extract_python_parameters(func_node, source.encode())
        assert len(params) == 2
        assert params[0].name == "name"
        assert params[0].type_hint == "str"
        assert params[1].name == "count"
        assert params[1].type_hint == "int"

    def test_default_parameters(self, parser):
        """Test extracting parameters with default values."""
        source = dedent("""
            def func(name="default", count=10):
                pass
        """).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        params = extract_python_parameters(func_node, source.encode())
        assert len(params) == 2
        assert params[0].name == "name"
        assert params[0].default_value == '"default"'
        assert params[1].name == "count"
        assert params[1].default_value == "10"

    def test_typed_default_parameters(self, parser):
        """Test extracting parameters with types and defaults."""
        source = dedent("""
            def func(name: str = "test", count: int = 5):
                pass
        """).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        params = extract_python_parameters(func_node, source.encode())
        assert len(params) == 2
        assert params[0].name == "name"
        assert params[0].type_hint == "str"
        assert params[0].default_value == '"test"'
        assert params[1].name == "count"
        assert params[1].type_hint == "int"
        assert params[1].default_value == "5"

    def test_excludes_self(self, parser):
        """Test that self is excluded from method parameters."""
        source = dedent("""
            def method(self, value: int):
                pass
        """).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        params = extract_python_parameters(func_node, source.encode())
        assert len(params) == 1
        assert params[0].name == "value"

    def test_excludes_cls(self, parser):
        """Test that cls is excluded from classmethod parameters."""
        source = dedent("""
            def classmethod_func(cls, value: int):
                pass
        """).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        params = extract_python_parameters(func_node, source.encode())
        assert len(params) == 1
        assert params[0].name == "value"


class TestExtractPythonReturnType:
    """Test Python return type extraction."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_simple_return_type(self, parser):
        """Test extracting a simple return type."""
        source = dedent("""
            def func() -> str:
                pass
        """).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        return_type = extract_python_return_type(func_node, source.encode())
        assert return_type == "str"

    def test_complex_return_type(self, parser):
        """Test extracting a complex return type."""
        source = dedent("""
            def func() -> list[str]:
                pass
        """).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        return_type = extract_python_return_type(func_node, source.encode())
        assert return_type == "list[str]"

    def test_no_return_type(self, parser):
        """Test function with no return type."""
        source = dedent("""
            def func():
                pass
        """).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        return_type = extract_python_return_type(func_node, source.encode())
        assert return_type is None


class TestExtractPythonDocstring:
    """Test Python docstring extraction."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_triple_quote_docstring(self, parser):
        """Test extracting triple-quoted docstring."""
        source = dedent('''
            def func():
                """This is the docstring."""
                pass
        ''').strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        docstring = extract_python_docstring(func_node, source.encode())
        assert docstring == "This is the docstring."

    def test_multiline_docstring(self, parser):
        """Test extracting multiline docstring."""
        source = dedent('''
            def func():
                """
                This is a multiline
                docstring.
                """
                pass
        ''').strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        docstring = extract_python_docstring(func_node, source.encode())
        assert "multiline" in docstring
        assert "docstring" in docstring

    def test_no_docstring(self, parser):
        """Test function with no docstring."""
        source = dedent("""
            def func():
                x = 1
        """).strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        docstring = extract_python_docstring(func_node, source.encode())
        assert docstring is None


class TestParseGoogleDocstring:
    """Test Google-style docstring parsing."""

    def test_simple_description(self):
        """Test parsing simple description."""
        docstring = "This is a simple description."
        result = parse_google_docstring(docstring)
        assert result["description"] == "This is a simple description."

    def test_args_section(self):
        """Test parsing Args section."""
        docstring = dedent("""
            Do something.

            Args:
                name: The name to use.
                count: How many items.
        """).strip()
        result = parse_google_docstring(docstring)

        assert "name" in result["args"]
        assert result["args"]["name"]["description"] == "The name to use."
        assert "count" in result["args"]
        assert result["args"]["count"]["description"] == "How many items."

    def test_args_with_types(self):
        """Test parsing Args with type annotations."""
        docstring = dedent("""
            Do something.

            Args:
                name (str): The name to use.
                count (int): How many items.
        """).strip()
        result = parse_google_docstring(docstring)

        assert result["args"]["name"]["type"] == "str"
        assert result["args"]["count"]["type"] == "int"

    def test_returns_section(self):
        """Test parsing Returns section."""
        docstring = dedent("""
            Do something.

            Returns:
                The result string.
        """).strip()
        result = parse_google_docstring(docstring)
        assert result["returns"] == "The result string."


class TestParseNumpyDocstring:
    """Test NumPy-style docstring parsing."""

    def test_simple_description(self):
        """Test parsing simple description."""
        docstring = "This is a simple description."
        result = parse_numpy_docstring(docstring)
        assert result["description"] == "This is a simple description."

    def test_parameters_section(self):
        """Test parsing Parameters section."""
        docstring = dedent("""
            Do something.

            Parameters
            ----------
            name : str
                The name to use.
            count : int
                How many items.
        """).strip()
        result = parse_numpy_docstring(docstring)

        assert "name" in result["args"]
        assert result["args"]["name"]["type"] == "str"
        assert "count" in result["args"]
        assert result["args"]["count"]["type"] == "int"


class TestExtractFunctionSignature:
    """Test function signature extraction."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_simple_function(self, parser):
        """Test extracting simple function signature."""
        source = dedent('''
            def greet(name: str) -> str:
                """Say hello."""
                return f"Hello, {name}"
        ''').strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        sig = extract_function_signature(func_node, source.encode(), Language.PYTHON)

        assert sig is not None
        assert sig.name == "greet"
        assert len(sig.parameters) == 1
        assert sig.parameters[0].name == "name"
        assert sig.parameters[0].type_hint == "str"
        assert sig.return_type == "str"
        assert sig.description == "Say hello."

    def test_async_function(self, parser):
        """Test extracting async function signature."""
        source = dedent('''
            async def fetch_data(url: str) -> bytes:
                """Fetch data from URL."""
                pass
        ''').strip()
        root = parser.parse_source(source, Language.PYTHON)
        func_node = root.children[0]

        sig = extract_function_signature(func_node, source.encode(), Language.PYTHON)

        assert sig is not None
        assert sig.is_async is True
        assert sig.name == "fetch_data"


class TestExtractClassSignature:
    """Test class signature extraction."""

    @pytest.fixture
    def parser(self):
        return CodeParser()

    def test_simple_class(self, parser):
        """Test extracting simple class signature."""
        source = dedent('''
            class MyClass:
                """A simple class."""

                def method(self, value: int) -> bool:
                    """A method."""
                    pass
        ''').strip()
        root = parser.parse_source(source, Language.PYTHON)
        class_node = root.children[0]

        sig = extract_class_signature(class_node, source.encode(), Language.PYTHON)

        assert sig is not None
        assert sig.name == "MyClass"
        assert sig.description == "A simple class."
        assert len(sig.methods) == 1
        assert sig.methods[0].name == "method"

    def test_class_with_inheritance(self, parser):
        """Test extracting class with base classes."""
        source = dedent('''
            class Child(Parent, Mixin):
                """A child class."""
                pass
        ''').strip()
        root = parser.parse_source(source, Language.PYTHON)
        class_node = root.children[0]

        sig = extract_class_signature(class_node, source.encode(), Language.PYTHON)

        assert sig is not None
        assert "Parent" in sig.bases
        assert "Mixin" in sig.bases


class TestFormatParameter:
    """Test parameter formatting."""

    def test_simple_param(self):
        """Test formatting simple parameter."""
        param = Parameter(name="value")
        assert format_parameter(param) == "value"

    def test_typed_param(self):
        """Test formatting typed parameter."""
        param = Parameter(name="value", type_hint="int")
        assert format_parameter(param) == "value: int"

    def test_default_param(self):
        """Test formatting parameter with default."""
        param = Parameter(name="value", default_value="10")
        assert format_parameter(param) == "value = 10"

    def test_full_param(self):
        """Test formatting parameter with type and default."""
        param = Parameter(name="value", type_hint="int", default_value="10")
        assert format_parameter(param) == "value: int = 10"


class TestFormatFunctionSignatureLine:
    """Test function signature line formatting."""

    def test_simple_function(self):
        """Test formatting simple function."""
        sig = FunctionSignature(name="func")
        result = format_function_signature_line(sig)
        assert result == "def func()"

    def test_function_with_params(self):
        """Test formatting function with parameters."""
        sig = FunctionSignature(
            name="func",
            parameters=[
                Parameter(name="a", type_hint="int"),
                Parameter(name="b", type_hint="str", default_value='"x"'),
            ],
        )
        result = format_function_signature_line(sig)
        assert result == 'def func(a: int, b: str = "x")'

    def test_function_with_return_type(self):
        """Test formatting function with return type."""
        sig = FunctionSignature(name="func", return_type="bool")
        result = format_function_signature_line(sig)
        assert result == "def func() -> bool"

    def test_async_function(self):
        """Test formatting async function."""
        sig = FunctionSignature(name="func", is_async=True)
        result = format_function_signature_line(sig)
        assert result == "async def func()"


class TestGenerateApiReferenceMarkdown:
    """Test API reference markdown generation."""

    def test_empty_input(self):
        """Test with no functions or classes."""
        result = generate_api_reference_markdown([], [])
        assert result == ""

    def test_function_documentation(self):
        """Test generating function documentation."""
        functions = [
            FunctionSignature(
                name="process",
                parameters=[
                    Parameter(name="data", type_hint="str", description="Input data."),
                ],
                return_type="bool",
                description="Process the input data.",
            )
        ]
        result = generate_api_reference_markdown(functions, [])

        assert "### Functions" in result
        assert "#### `process`" in result
        assert "def process(data: str) -> bool" in result
        assert "Process the input data." in result
        assert "| `data` |" in result
        assert "**Returns:** `bool`" in result

    def test_class_documentation(self):
        """Test generating class documentation."""
        classes = [
            ClassSignature(
                name="MyClass",
                bases=["BaseClass"],
                description="A test class.",
                methods=[
                    FunctionSignature(
                        name="run",
                        parameters=[Parameter(name="value", type_hint="int")],
                        return_type="None",
                        description="Run the process.",
                        is_method=True,
                    ),
                ],
            )
        ]
        result = generate_api_reference_markdown([], classes)

        assert "### class `MyClass`" in result
        assert "**Inherits from:** `BaseClass`" in result
        assert "A test class." in result
        assert "#### `run`" in result

    def test_filters_private_items(self):
        """Test that private items are filtered by default."""
        functions = [
            FunctionSignature(name="_private_func"),
            FunctionSignature(name="public_func"),
        ]
        classes = [
            ClassSignature(name="_PrivateClass"),
            ClassSignature(name="PublicClass"),
        ]
        result = generate_api_reference_markdown(functions, classes)

        assert "_private_func" not in result
        assert "public_func" in result
        assert "_PrivateClass" not in result
        assert "PublicClass" in result

    def test_includes_private_when_requested(self):
        """Test including private items when specified."""
        functions = [FunctionSignature(name="_private_func")]
        result = generate_api_reference_markdown(functions, [], include_private=True)

        assert "_private_func" in result


class TestAPIDocExtractor:
    """Test APIDocExtractor class."""

    @pytest.fixture
    def extractor(self):
        return APIDocExtractor()

    def test_extract_from_file(self, tmp_path, extractor):
        """Test extracting docs from a Python file."""
        source = dedent('''
            """Module docstring."""

            def helper(value: int) -> bool:
                """A helper function."""
                return value > 0

            class MyClass:
                """A sample class."""

                def __init__(self, name: str):
                    """Initialize with name."""
                    self.name = name

                def process(self, data: list) -> dict:
                    """Process the data."""
                    return {}
        ''').strip()

        test_file = tmp_path / "test_module.py"
        test_file.write_text(source)

        functions, classes = extractor.extract_from_file(test_file)

        assert len(functions) == 1
        assert functions[0].name == "helper"

        assert len(classes) == 1
        assert classes[0].name == "MyClass"
        assert len(classes[0].methods) == 2  # __init__ and process

    def test_extract_unsupported_file(self, tmp_path, extractor):
        """Test extracting from unsupported file type."""
        test_file = tmp_path / "readme.txt"
        test_file.write_text("Not code")

        functions, classes = extractor.extract_from_file(test_file)

        assert functions == []
        assert classes == []


class TestGetFileApiDocs:
    """Test the convenience function."""

    def test_file_with_content(self, tmp_path):
        """Test getting API docs for a file with content."""
        source = dedent('''
            def process(value: int = 10) -> str:
                """Process a value.

                Args:
                    value: The value to process.

                Returns:
                    The processed string.
                """
                return str(value)
        ''').strip()

        test_file = tmp_path / "processor.py"
        test_file.write_text(source)

        result = get_file_api_docs(test_file)

        assert result is not None
        assert "process" in result
        assert "value: int = 10" in result
        assert "-> str" in result

    def test_file_without_functions(self, tmp_path):
        """Test getting API docs for file without functions."""
        source = dedent("""
            X = 1
            Y = 2
        """).strip()

        test_file = tmp_path / "constants.py"
        test_file.write_text(source)

        result = get_file_api_docs(test_file)
        assert result is None
