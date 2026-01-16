"""Tests for type annotation extraction in chunker."""

import pytest

from local_deepwiki.core.chunker import (
    extract_function_type_metadata,
    extract_python_decorators,
    extract_python_parameter_defaults,
    extract_python_parameter_types,
    extract_python_raised_exceptions,
    extract_python_return_type,
    is_async_function,
)
from local_deepwiki.core.parser import CodeParser
from local_deepwiki.models import Language


@pytest.fixture
def parser():
    """Create a code parser for testing."""
    return CodeParser()


def parse_python_function(parser: CodeParser, code: str):
    """Parse Python code and return the first function node."""
    source = code.encode("utf-8")
    tree = parser.parse_source(source, Language.PYTHON)
    # Find first function_definition or async_function_definition
    for child in tree.children:
        if child.type in ("function_definition", "async_function_definition"):
            return child, source
        # Handle decorated functions
        if child.type == "decorated_definition":
            for c in child.children:
                if c.type in ("function_definition", "async_function_definition"):
                    return c, source
    return None, source


class TestExtractPythonParameterTypes:
    """Tests for extract_python_parameter_types function."""

    def test_simple_typed_params(self, parser):
        """Test extracting simple typed parameters."""
        code = "def foo(x: int, y: str): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"x": "int", "y": "str"}

    def test_params_without_types(self, parser):
        """Test extracting parameters without type hints."""
        code = "def foo(x, y): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"x": None, "y": None}

    def test_mixed_typed_and_untyped(self, parser):
        """Test extracting mix of typed and untyped parameters."""
        code = "def foo(x: int, y): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"x": "int", "y": None}

    def test_typed_default_params(self, parser):
        """Test extracting typed parameters with defaults."""
        code = 'def foo(x: int = 5, y: str = "hello"): pass'
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"x": "int", "y": "str"}

    def test_default_params_without_type(self, parser):
        """Test extracting default parameters without type hints."""
        code = 'def foo(x=5, y="hello"): pass'
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"x": None, "y": None}

    def test_complex_type_hints(self, parser):
        """Test extracting complex type hints like generics."""
        code = "def foo(items: list[str], mapping: dict[str, int]): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"items": "list[str]", "mapping": "dict[str, int]"}

    def test_union_types(self, parser):
        """Test extracting union type hints."""
        code = "def foo(value: str | None): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"value": "str | None"}

    def test_excludes_self_and_cls(self, parser):
        """Test that self and cls are excluded from results."""
        code = "def foo(self, x: int, cls, y: str): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"x": "int", "y": "str"}

    def test_star_args(self, parser):
        """Test extracting *args parameters."""
        code = "def foo(*args): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"*args": None}

    def test_star_kwargs(self, parser):
        """Test extracting **kwargs parameters."""
        code = "def foo(**kwargs): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"**kwargs": None}

    def test_typed_star_args(self, parser):
        """Test extracting typed *args parameters."""
        code = "def foo(*args: str): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"*args": "str"}

    def test_typed_star_kwargs(self, parser):
        """Test extracting typed **kwargs parameters."""
        code = "def foo(**kwargs: int): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {"**kwargs": "int"}

    def test_no_params(self, parser):
        """Test function with no parameters."""
        code = "def foo(): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_types(func_node, source)
        assert result == {}


class TestExtractPythonParameterDefaults:
    """Tests for extract_python_parameter_defaults function."""

    def test_simple_defaults(self, parser):
        """Test extracting simple default values."""
        code = 'def foo(x=5, y="hello"): pass'
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_defaults(func_node, source)
        assert result == {"x": "5", "y": '"hello"'}

    def test_typed_defaults(self, parser):
        """Test extracting defaults from typed parameters."""
        code = "def foo(x: int = 10, y: str = None): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_defaults(func_node, source)
        assert result == {"x": "10", "y": "None"}

    def test_no_defaults(self, parser):
        """Test function with no default values."""
        code = "def foo(x, y): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_defaults(func_node, source)
        assert result == {}

    def test_excludes_self_and_cls(self, parser):
        """Test that self and cls are excluded from defaults."""
        code = "def foo(self=None, x=5): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_parameter_defaults(func_node, source)
        assert result == {"x": "5"}


class TestExtractPythonReturnType:
    """Tests for extract_python_return_type function."""

    def test_simple_return_type(self, parser):
        """Test extracting simple return type."""
        code = "def foo() -> int: pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_return_type(func_node, source)
        assert result == "int"

    def test_complex_return_type(self, parser):
        """Test extracting complex return type."""
        code = "def foo() -> list[dict[str, int]]: pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_return_type(func_node, source)
        assert result == "list[dict[str, int]]"

    def test_union_return_type(self, parser):
        """Test extracting union return type."""
        code = "def foo() -> str | None: pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_return_type(func_node, source)
        assert result == "str | None"

    def test_no_return_type(self, parser):
        """Test function with no return type annotation."""
        code = "def foo(): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_return_type(func_node, source)
        assert result is None


class TestExtractPythonDecorators:
    """Tests for extract_python_decorators function."""

    def test_single_decorator(self, parser):
        """Test extracting a single decorator."""
        code = "@property\ndef foo(): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_decorators(func_node, source)
        assert result == ["@property"]

    def test_multiple_decorators(self, parser):
        """Test extracting multiple decorators."""
        code = "@staticmethod\n@property\ndef foo(): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_decorators(func_node, source)
        assert result == ["@staticmethod", "@property"]

    def test_decorator_with_args(self, parser):
        """Test extracting decorator with arguments."""
        code = '@decorator("arg")\ndef foo(): pass'
        func_node, source = parse_python_function(parser, code)
        result = extract_python_decorators(func_node, source)
        assert result == ['@decorator("arg")']

    def test_no_decorators(self, parser):
        """Test function with no decorators."""
        code = "def foo(): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_decorators(func_node, source)
        assert result == []


class TestIsAsyncFunction:
    """Tests for is_async_function function."""

    def test_async_function(self, parser):
        """Test detecting async function."""
        code = "async def foo(): pass"
        func_node, source = parse_python_function(parser, code)
        result = is_async_function(func_node)
        assert result is True

    def test_sync_function(self, parser):
        """Test detecting regular sync function."""
        code = "def foo(): pass"
        func_node, source = parse_python_function(parser, code)
        result = is_async_function(func_node)
        assert result is False


class TestExtractFunctionTypeMetadata:
    """Tests for extract_function_type_metadata function."""

    def test_full_metadata_extraction(self, parser):
        """Test extracting all type metadata from a complex function."""
        code = '''
@decorator
async def process(items: list[str], callback: Callable = None) -> dict[str, int]:
    pass
'''
        func_node, source = parse_python_function(parser, code)
        result = extract_function_type_metadata(func_node, source, Language.PYTHON)

        assert result["parameter_types"] == {
            "items": "list[str]",
            "callback": "Callable",
        }
        assert result["parameter_defaults"] == {"callback": "None"}
        assert result["return_type"] == "dict[str, int]"
        assert result["is_async"] is True
        assert "@decorator" in result["decorators"]

    def test_minimal_function(self, parser):
        """Test extracting metadata from a minimal function."""
        code = "def foo(): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_function_type_metadata(func_node, source, Language.PYTHON)

        # Should be empty or only have keys with empty values
        assert result.get("parameter_types") is None or result.get("parameter_types") == {}
        assert result.get("return_type") is None
        assert result.get("is_async") is None or result.get("is_async") is False

    def test_typed_params_only(self, parser):
        """Test that only typed params are included in parameter_types."""
        code = "def foo(x: int, y, z: str): pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_function_type_metadata(func_node, source, Language.PYTHON)

        # Should only include params that have type hints
        assert result["parameter_types"] == {"x": "int", "z": "str"}

    def test_non_python_returns_empty(self, parser):
        """Test that non-Python languages return empty metadata for now."""
        code = "def foo(x: int) -> str: pass"
        func_node, source = parse_python_function(parser, code)
        result = extract_function_type_metadata(func_node, source, Language.JAVASCRIPT)

        # Should be empty for non-Python languages
        assert result == {}

    def test_extracts_raised_exceptions(self, parser):
        """Test that raised exceptions are extracted."""
        code = '''
def foo(x):
    if x < 0:
        raise ValueError("x must be positive")
    if x > 100:
        raise RuntimeError
'''
        func_node, source = parse_python_function(parser, code)
        result = extract_function_type_metadata(func_node, source, Language.PYTHON)

        assert "raises" in result
        assert sorted(result["raises"]) == ["RuntimeError", "ValueError"]


class TestExtractPythonRaisedExceptions:
    """Tests for extract_python_raised_exceptions function."""

    def test_simple_raise(self, parser):
        """Test extracting simple raise statement."""
        code = "def foo(): raise ValueError"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_raised_exceptions(func_node, source)
        assert result == ["ValueError"]

    def test_raise_with_message(self, parser):
        """Test extracting raise with message."""
        code = 'def foo(): raise ValueError("error message")'
        func_node, source = parse_python_function(parser, code)
        result = extract_python_raised_exceptions(func_node, source)
        assert result == ["ValueError"]

    def test_multiple_raises(self, parser):
        """Test extracting multiple different exceptions."""
        code = '''
def foo(x):
    if x < 0:
        raise ValueError
    if x > 100:
        raise TypeError
    raise RuntimeError
'''
        func_node, source = parse_python_function(parser, code)
        result = extract_python_raised_exceptions(func_node, source)
        assert sorted(result) == ["RuntimeError", "TypeError", "ValueError"]

    def test_no_raises(self, parser):
        """Test function with no raise statements."""
        code = "def foo(): return 42"
        func_node, source = parse_python_function(parser, code)
        result = extract_python_raised_exceptions(func_node, source)
        assert result == []

    def test_raise_from_exception(self, parser):
        """Test extracting raise with 'from' clause."""
        code = '''
def foo():
    try:
        pass
    except Exception as e:
        raise CustomError("failed") from e
'''
        func_node, source = parse_python_function(parser, code)
        result = extract_python_raised_exceptions(func_node, source)
        assert result == ["CustomError"]

    def test_raise_attribute_exception(self, parser):
        """Test extracting raise with module.Exception pattern."""
        code = 'def foo(): raise errors.CustomError("msg")'
        func_node, source = parse_python_function(parser, code)
        result = extract_python_raised_exceptions(func_node, source)
        assert result == ["errors.CustomError"]

    def test_deduplicates_same_exception(self, parser):
        """Test that same exception raised multiple times is only listed once."""
        code = '''
def foo(x):
    if x < 0:
        raise ValueError("negative")
    if x > 100:
        raise ValueError("too large")
'''
        func_node, source = parse_python_function(parser, code)
        result = extract_python_raised_exceptions(func_node, source)
        assert result == ["ValueError"]

    def test_ignores_nested_functions(self, parser):
        """Test that exceptions in nested functions are not included."""
        code = '''
def outer():
    def inner():
        raise InnerError
    raise OuterError
'''
        func_node, source = parse_python_function(parser, code)
        result = extract_python_raised_exceptions(func_node, source)
        # Should only include OuterError, not InnerError
        assert result == ["OuterError"]

    def test_bare_raise(self, parser):
        """Test that bare 'raise' (re-raise) doesn't extract anything."""
        code = '''
def foo():
    try:
        pass
    except:
        raise
'''
        func_node, source = parse_python_function(parser, code)
        result = extract_python_raised_exceptions(func_node, source)
        assert result == []
