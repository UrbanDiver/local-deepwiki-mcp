"""Tests for complexity metrics generator."""

import pytest
from pathlib import Path
from local_deepwiki.generators.complexity import compute_complexity_metrics


@pytest.mark.asyncio
async def test_simple_function(tmp_path: Path):
    """Test complexity metrics for a simple Python function."""
    # Create a simple Python file
    code = """
def simple_function(x):
    return x + 1
"""
    file_path = tmp_path / "simple.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("simple.py"), tmp_path)

    assert result["status"] == "success"
    assert result["language"] == "python"
    assert result["counts"]["functions"] == 1
    assert result["counts"]["classes"] == 0

    # Check function details
    func = result["functions"][0]
    assert func["name"] == "simple_function"
    assert func["cyclomatic_complexity"] == 1  # No branches
    assert func["param_count"] == 1
    assert func["nesting_depth"] == 0


@pytest.mark.asyncio
async def test_function_with_branches(tmp_path: Path):
    """Test complexity metrics for a function with if/elif/else branches."""
    code = """
def complex_function(x, y):
    if x > 0:
        return x
    elif x < 0:
        return -x
    else:
        return y
"""
    file_path = tmp_path / "branches.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("branches.py"), tmp_path)

    assert result["status"] == "success"
    assert result["counts"]["functions"] == 1

    func = result["functions"][0]
    assert func["name"] == "complex_function"
    assert func["cyclomatic_complexity"] > 1  # Has branches
    assert func["param_count"] == 2


@pytest.mark.asyncio
async def test_nested_loops(tmp_path: Path):
    """Test complexity metrics for a function with nested loops."""
    code = """
def nested_function(matrix):
    result = 0
    for row in matrix:
        for col in row:
            if col > 0:
                result += col
    return result
"""
    file_path = tmp_path / "nested.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("nested.py"), tmp_path)

    assert result["status"] == "success"
    assert result["counts"]["functions"] == 1

    func = result["functions"][0]
    assert func["name"] == "nested_function"
    # nesting_depth is where the function is defined, not max nesting inside it
    assert func["nesting_depth"] == 0  # Top-level function
    assert func["cyclomatic_complexity"] > 1  # Has loops and if
    # Check file-level max_nesting
    assert result["complexity"]["max_nesting_depth"] >= 2  # Nested loops + if


@pytest.mark.asyncio
async def test_class_with_methods(tmp_path: Path):
    """Test complexity metrics for a class containing methods."""
    code = """
class Calculator:
    def add(self, x, y):
        return x + y

    def subtract(self, x, y):
        return x - y

    def multiply(self, x, y):
        result = 0
        for i in range(y):
            result += x
        return result
"""
    file_path = tmp_path / "class_file.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("class_file.py"), tmp_path)

    assert result["status"] == "success"
    assert result["counts"]["classes"] == 1
    assert result["counts"]["functions"] == 3  # 3 methods

    # Check class details
    cls = result["classes"][0]
    assert cls["name"] == "Calculator"

    # Check that parameter counts exclude 'self'
    for func in result["functions"]:
        assert func["param_count"] == 2  # x and y (self excluded)


@pytest.mark.asyncio
async def test_empty_file(tmp_path: Path):
    """Test complexity metrics for an empty Python file."""
    code = ""
    file_path = tmp_path / "empty.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("empty.py"), tmp_path)

    assert result["status"] == "success"
    assert result["counts"]["functions"] == 0
    assert result["counts"]["classes"] == 0
    assert result["complexity"]["avg_cyclomatic"] == 0
    assert result["complexity"]["max_cyclomatic"] == 0


@pytest.mark.asyncio
async def test_comment_only_file(tmp_path: Path):
    """Test complexity metrics for a file with only comments."""
    code = """
# This is a comment
# Another comment
\"\"\"
This is a docstring
\"\"\"
"""
    file_path = tmp_path / "comments.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("comments.py"), tmp_path)

    assert result["status"] == "success"
    assert result["counts"]["functions"] == 0
    assert result["lines"]["comment"] > 0
    assert result["lines"]["code"] >= 0


@pytest.mark.asyncio
async def test_line_counts(tmp_path: Path):
    """Test that line counts are computed correctly."""
    code = """
# Comment
def func():
    x = 1  # inline comment

    # another comment
    return x

"""
    file_path = tmp_path / "lines.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("lines.py"), tmp_path)

    assert result["status"] == "success"
    lines = result["lines"]
    assert lines["total"] > 0
    assert lines["blank"] > 0
    assert lines["comment"] > 0
    assert lines["code"] > 0
    assert lines["total"] == lines["blank"] + lines["comment"] + lines["code"]


@pytest.mark.asyncio
async def test_aggregate_metrics(tmp_path: Path):
    """Test aggregate complexity metrics computation."""
    code = """
def simple():
    return 1

def complex(x, y, z):
    if x:
        for i in range(y):
            if i > z:
                return i
    return 0
"""
    file_path = tmp_path / "aggregate.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("aggregate.py"), tmp_path)

    assert result["status"] == "success"
    complexity = result["complexity"]

    # Should have averages and maxes
    assert complexity["avg_cyclomatic"] > 0
    assert complexity["max_cyclomatic"] >= complexity["avg_cyclomatic"]
    assert complexity["avg_params"] >= 0
    assert complexity["max_params"] >= complexity["avg_params"]
    assert complexity["avg_nesting_depth"] >= 0
    assert complexity["max_nesting_depth"] >= complexity["avg_nesting_depth"]


@pytest.mark.asyncio
async def test_unsupported_file_type(tmp_path: Path):
    """Test handling of unsupported file types."""
    # Create a text file (not a supported language)
    file_path = tmp_path / "readme.txt"
    file_path.write_text("This is not code")

    result = await compute_complexity_metrics(Path("readme.txt"), tmp_path)

    assert result["status"] == "success"
    assert "message" in result
    assert "not supported" in result["message"].lower()
    assert result.get("metrics") == {}


@pytest.mark.asyncio
async def test_javascript_file(tmp_path: Path):
    """Test complexity metrics for a JavaScript file."""
    code = """
function add(a, b) {
    return a + b;
}

const multiply = (x, y) => {
    let result = 0;
    for (let i = 0; i < y; i++) {
        result += x;
    }
    return result;
};
"""
    file_path = tmp_path / "code.js"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("code.js"), tmp_path)

    assert result["status"] == "success"
    assert result["language"] == "javascript"
    assert result["counts"]["functions"] >= 1  # At least one function


@pytest.mark.asyncio
async def test_function_limit(tmp_path: Path):
    """Test that only first 50 functions are returned."""
    # Create a file with many functions
    code = "\n".join([f"def func_{i}():\n    pass\n" for i in range(60)])
    file_path = tmp_path / "many.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("many.py"), tmp_path)

    assert result["status"] == "success"
    assert result["counts"]["functions"] == 60
    assert len(result["functions"]) == 50  # Limited to 50


@pytest.mark.asyncio
async def test_try_except_complexity(tmp_path: Path):
    """Test that try/except blocks increase complexity."""
    code = """
def error_handler(x):
    try:
        result = 1 / x
    except ZeroDivisionError:
        return 0
    except ValueError:
        return -1
    else:
        return result
"""
    file_path = tmp_path / "error.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("error.py"), tmp_path)

    assert result["status"] == "success"
    func = result["functions"][0]
    assert func["cyclomatic_complexity"] > 1  # try/except adds complexity


@pytest.mark.asyncio
async def test_logical_operators(tmp_path: Path):
    """Test that logical operators increase complexity."""
    code = """
def check(x, y, z):
    if x and y or z:
        return True
    return False
"""
    file_path = tmp_path / "logic.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("logic.py"), tmp_path)

    assert result["status"] == "success"
    func = result["functions"][0]
    assert func["cyclomatic_complexity"] > 1  # and/or add complexity


@pytest.mark.asyncio
async def test_match_statement(tmp_path: Path):
    """Test that match statements are recognized (Python 3.10+)."""
    code = """
def matcher(value):
    match value:
        case 1:
            return "one"
        case 2:
            return "two"
        case _:
            return "other"
"""
    file_path = tmp_path / "match.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("match.py"), tmp_path)

    assert result["status"] == "success"
    # Match statement should increase complexity
    func = result["functions"][0]
    assert func["cyclomatic_complexity"] >= 1


@pytest.mark.asyncio
async def test_parameter_count_excludes_self_cls(tmp_path: Path):
    """Test that 'self' and 'cls' are excluded from parameter counts."""
    code = """
class MyClass:
    def instance_method(self, x, y):
        return x + y

    @classmethod
    def class_method(cls, x):
        return x * 2
"""
    file_path = tmp_path / "params.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("params.py"), tmp_path)

    assert result["status"] == "success"

    # Both methods should have param counts excluding self/cls
    for func in result["functions"]:
        if func["name"] == "instance_method":
            assert func["param_count"] == 2  # x, y (self excluded)
        elif func["name"] == "class_method":
            assert func["param_count"] == 1  # x (cls excluded)
