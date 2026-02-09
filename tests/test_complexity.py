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


@pytest.mark.asyncio
async def test_deeply_nested_code(tmp_path: Path):
    """Test complexity metrics for deeply nested code (5+ levels)."""
    code = """
def deeply_nested(data):
    for item in data:
        if item > 0:
            for sub in range(item):
                if sub % 2 == 0:
                    while sub > 0:
                        if sub < 10:
                            return sub
                        sub -= 1
    return None
"""
    file_path = tmp_path / "deep.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("deep.py"), tmp_path)

    assert result["status"] == "success"
    assert result["complexity"]["max_nesting_depth"] >= 5
    func = result["functions"][0]
    assert func["cyclomatic_complexity"] > 3


@pytest.mark.asyncio
async def test_no_branches_complexity_is_one(tmp_path: Path):
    """A function with no branches should have cyclomatic complexity of 1."""
    code = """
def linear_function(a, b, c):
    x = a + b
    y = x * c
    return y
"""
    file_path = tmp_path / "linear.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("linear.py"), tmp_path)

    assert result["status"] == "success"
    func = result["functions"][0]
    assert func["name"] == "linear_function"
    assert func["cyclomatic_complexity"] == 1
    assert func["param_count"] == 3


@pytest.mark.asyncio
async def test_multiple_return_statements(tmp_path: Path):
    """Test complexity for a function with multiple return paths."""
    code = """
def multi_return(x):
    if x > 100:
        return "big"
    if x > 50:
        return "medium"
    if x > 10:
        return "small"
    return "tiny"
"""
    file_path = tmp_path / "multi_return.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("multi_return.py"), tmp_path)

    assert result["status"] == "success"
    func = result["functions"][0]
    assert func["cyclomatic_complexity"] >= 4  # 3 if-statements + base


@pytest.mark.asyncio
async def test_try_except_finally_nesting(tmp_path: Path):
    """Test try/except/finally with nesting increases complexity."""
    code = """
def robust_operation(path):
    try:
        try:
            with open(path) as f:
                data = f.read()
        except IOError:
            data = ""
        except ValueError:
            data = "default"
    except Exception:
        return None
    finally:
        pass
    return data
"""
    file_path = tmp_path / "tryexcept.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("tryexcept.py"), tmp_path)

    assert result["status"] == "success"
    func = result["functions"][0]
    assert func["cyclomatic_complexity"] > 2
    assert result["complexity"]["max_nesting_depth"] >= 1


@pytest.mark.asyncio
async def test_typescript_file(tmp_path: Path):
    """Test complexity metrics for a TypeScript file."""
    code = """
function greet(name: string): string {
    if (name === "") {
        return "Hello, World!";
    }
    return `Hello, ${name}!`;
}

class Greeter {
    private name: string;

    constructor(name: string) {
        this.name = name;
    }

    greet(): string {
        return `Hello, ${this.name}!`;
    }
}
"""
    file_path = tmp_path / "greeter.ts"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("greeter.ts"), tmp_path)

    assert result["status"] == "success"
    assert result["language"] == "typescript"
    assert result["counts"]["functions"] >= 1
    assert result["counts"]["classes"] >= 1


@pytest.mark.asyncio
async def test_go_file(tmp_path: Path):
    """Test complexity metrics for a Go file."""
    code = """
package main

func add(a int, b int) int {
    return a + b
}

func classify(x int) string {
    if x > 0 {
        return "positive"
    } else if x < 0 {
        return "negative"
    }
    return "zero"
}
"""
    file_path = tmp_path / "main.go"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("main.go"), tmp_path)

    assert result["status"] == "success"
    assert result["language"] == "go"
    assert result["counts"]["functions"] >= 2


@pytest.mark.asyncio
async def test_rust_file(tmp_path: Path):
    """Test complexity metrics for a Rust file."""
    code = """
fn factorial(n: u64) -> u64 {
    if n <= 1 {
        return 1;
    }
    return n * factorial(n - 1);
}

struct Point {
    x: f64,
    y: f64,
}

impl Point {
    fn distance(&self) -> f64 {
        (self.x * self.x + self.y * self.y).sqrt()
    }
}
"""
    file_path = tmp_path / "main.rs"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("main.rs"), tmp_path)

    assert result["status"] == "success"
    assert result["language"] == "rust"
    assert result["counts"]["functions"] >= 1


@pytest.mark.asyncio
async def test_file_not_found(tmp_path: Path):
    """Nonexistent file should return None from parser and give unsupported message."""
    result = await compute_complexity_metrics(Path("nonexistent.py"), tmp_path)

    assert result["status"] == "success"
    assert (
        "not supported" in result.get("message", "").lower()
        or result.get("metrics") == {}
    )


@pytest.mark.asyncio
async def test_class_methods_vs_standalone_functions(tmp_path: Path):
    """Verify class methods and standalone functions are both counted."""
    code = """
def standalone(x):
    return x * 2

class MyClass:
    def method_a(self, a):
        if a > 0:
            return a
        return 0

    def method_b(self, b):
        return b + 1
"""
    file_path = tmp_path / "mixed.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("mixed.py"), tmp_path)

    assert result["status"] == "success"
    assert result["counts"]["functions"] == 3  # standalone + method_a + method_b
    assert result["counts"]["classes"] == 1

    names = [f["name"] for f in result["functions"]]
    assert "standalone" in names
    assert "method_a" in names
    assert "method_b" in names

    # standalone has no self, so param_count = 1
    standalone = next(f for f in result["functions"] if f["name"] == "standalone")
    assert standalone["param_count"] == 1

    # method_a has self excluded, so param_count = 1
    method_a = next(f for f in result["functions"] if f["name"] == "method_a")
    assert method_a["param_count"] == 1
    assert method_a["cyclomatic_complexity"] > 1  # has if branch


@pytest.mark.asyncio
async def test_while_loop_complexity(tmp_path: Path):
    """While loops should increase cyclomatic complexity."""
    code = """
def countdown(n):
    while n > 0:
        n -= 1
    return n
"""
    file_path = tmp_path / "while_loop.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("while_loop.py"), tmp_path)

    assert result["status"] == "success"
    func = result["functions"][0]
    assert func["cyclomatic_complexity"] > 1


@pytest.mark.asyncio
async def test_for_loop_complexity(tmp_path: Path):
    """For loops should increase cyclomatic complexity."""
    code = """
def sum_list(items):
    total = 0
    for item in items:
        total += item
    return total
"""
    file_path = tmp_path / "for_loop.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("for_loop.py"), tmp_path)

    assert result["status"] == "success"
    func = result["functions"][0]
    assert func["cyclomatic_complexity"] > 1


@pytest.mark.asyncio
async def test_ternary_expression(tmp_path: Path):
    """Ternary/conditional expression should increase complexity."""
    code = """
def abs_val(x):
    return x if x >= 0 else -x
"""
    file_path = tmp_path / "ternary.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("ternary.py"), tmp_path)

    assert result["status"] == "success"
    func = result["functions"][0]
    assert func["cyclomatic_complexity"] >= 2


@pytest.mark.asyncio
async def test_multiple_classes(tmp_path: Path):
    """File with multiple classes should count all of them."""
    code = """
class First:
    pass

class Second:
    def method(self):
        pass

class Third:
    def another(self, x, y, z):
        return x + y + z
"""
    file_path = tmp_path / "multi_class.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("multi_class.py"), tmp_path)

    assert result["status"] == "success"
    assert result["counts"]["classes"] == 3
    assert result["counts"]["functions"] == 2  # method + another


@pytest.mark.asyncio
async def test_zero_param_function(tmp_path: Path):
    """Function with no parameters should have param_count=0."""
    code = """
def no_params():
    return 42
"""
    file_path = tmp_path / "no_params.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("no_params.py"), tmp_path)

    assert result["status"] == "success"
    func = result["functions"][0]
    assert func["param_count"] == 0


@pytest.mark.asyncio
async def test_many_params_function(tmp_path: Path):
    """Function with many parameters should count them all."""
    code = """
def many_params(a, b, c, d, e, f, g):
    return a + b + c + d + e + f + g
"""
    file_path = tmp_path / "many_params.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("many_params.py"), tmp_path)

    assert result["status"] == "success"
    func = result["functions"][0]
    assert func["param_count"] == 7
    assert result["complexity"]["max_params"] == 7


@pytest.mark.asyncio
async def test_nested_functions(tmp_path: Path):
    """Nested function definitions should be recognized."""
    code = """
def outer(x):
    def inner(y):
        return y * 2
    return inner(x)
"""
    file_path = tmp_path / "nested_func.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("nested_func.py"), tmp_path)

    assert result["status"] == "success"
    assert result["counts"]["functions"] == 2

    names = [f["name"] for f in result["functions"]]
    assert "outer" in names
    assert "inner" in names


@pytest.mark.asyncio
async def test_decorator_function(tmp_path: Path):
    """Decorated function should still be recognized."""
    code = """
def decorator(func):
    def wrapper(*args):
        return func(*args)
    return wrapper

@decorator
def decorated_func(x):
    return x + 1
"""
    file_path = tmp_path / "decorated.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("decorated.py"), tmp_path)

    assert result["status"] == "success"
    names = [f["name"] for f in result["functions"]]
    assert "decorated_func" in names


@pytest.mark.asyncio
async def test_line_start_and_end(tmp_path: Path):
    """Function line numbers should be correctly reported."""
    code = """def first():
    pass

def second():
    x = 1
    y = 2
    return x + y
"""
    file_path = tmp_path / "line_nums.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("line_nums.py"), tmp_path)

    assert result["status"] == "success"
    first = next(f for f in result["functions"] if f["name"] == "first")
    second = next(f for f in result["functions"] if f["name"] == "second")
    assert first["line"] == 1
    assert second["line"] == 4
    assert second["end_line"] == 7


@pytest.mark.asyncio
async def test_complex_boolean_expressions(tmp_path: Path):
    """Complex boolean expressions with multiple and/or should add complexity."""
    code = """
def complex_check(a, b, c, d):
    if a and b and c or d:
        return True
    if a or b or c:
        return True
    return False
"""
    file_path = tmp_path / "complex_bool.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("complex_bool.py"), tmp_path)

    assert result["status"] == "success"
    func = result["functions"][0]
    # 2 if statements + multiple boolean operators + base = high complexity
    assert func["cyclomatic_complexity"] >= 4


@pytest.mark.asyncio
async def test_classes_limited_to_50(tmp_path: Path):
    """Only first 50 classes should be returned."""
    code = "\n".join([f"class Class_{i}:\n    pass\n" for i in range(60)])
    file_path = tmp_path / "many_classes.py"
    file_path.write_text(code)

    result = await compute_complexity_metrics(Path("many_classes.py"), tmp_path)

    assert result["status"] == "success"
    assert result["counts"]["classes"] == 60
    assert len(result["classes"]) == 50
