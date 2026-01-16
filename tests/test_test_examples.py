"""Tests for the test_examples module."""

from pathlib import Path
from textwrap import dedent

import pytest

from local_deepwiki.generators.test_examples import (
    UsageExample,
    extract_examples_for_entities,
    find_test_file,
    format_examples_markdown,
    get_file_examples,
)


class TestFindTestFile:
    """Tests for find_test_file function."""

    def test_find_test_file_direct_match(self, tmp_path: Path) -> None:
        """Test finding test file with direct naming convention."""
        # Create source file
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        source_file = src_dir / "api_docs.py"
        source_file.write_text("# source")

        # Create matching test file
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_api_docs.py"
        test_file.write_text("# test")

        result = find_test_file(source_file, tmp_path)
        assert result == test_file

    def test_find_test_file_in_test_dir(self, tmp_path: Path) -> None:
        """Test finding test file in 'test' directory (singular)."""
        source_file = tmp_path / "utils.py"
        source_file.write_text("# source")

        test_dir = tmp_path / "test"
        test_dir.mkdir()
        test_file = test_dir / "test_utils.py"
        test_file.write_text("# test")

        result = find_test_file(source_file, tmp_path)
        assert result == test_file

    def test_find_test_file_not_found(self, tmp_path: Path) -> None:
        """Test returns None when no test file exists."""
        source_file = tmp_path / "foo.py"
        source_file.write_text("# source")

        result = find_test_file(source_file, tmp_path)
        assert result is None

    def test_find_test_file_skips_test_files(self, tmp_path: Path) -> None:
        """Test that test files themselves return None."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_something.py"
        test_file.write_text("# test")

        result = find_test_file(test_file, tmp_path)
        assert result is None


class TestExtractExamplesForEntities:
    """Tests for extract_examples_for_entities function."""

    def test_extract_simple_function_call(self, tmp_path: Path) -> None:
        """Test extracting example that calls a simple function."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                '''
            def test_process_data():
                """Test the process_data function."""
                result = process_data("input")
                assert result == "expected"
        '''
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["process_data"],
            max_examples_per_entity=2,
        )

        assert len(examples) == 1
        example = examples[0]
        assert example.entity_name == "process_data"
        assert example.test_name == "test_process_data"
        assert "process_data" in example.code
        assert example.description == "Test the process_data function."

    def test_extract_class_instantiation(self, tmp_path: Path) -> None:
        """Test extracting example that instantiates a class."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                """
            def test_my_class():
                obj = MyClass(name="test")
                assert obj.name == "test"
        """
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["MyClass"],
        )

        assert len(examples) == 1
        assert examples[0].entity_name == "MyClass"
        assert "MyClass" in examples[0].code

    def test_extract_with_dedent_setup(self, tmp_path: Path) -> None:
        """Test extracting example with dedent pattern captures from dedent."""
        test_file = tmp_path / "test_example.py"
        # When the entity appears in a line with dedent, both are captured
        test_file.write_text(
            dedent(
                '''
            def test_parse_code():
                code = dedent("""
                    def foo():
                        pass
                """)
                result = parse_code(code)
                assert result is not None
        '''
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["parse_code"],
        )

        assert len(examples) == 1
        # The extraction starts from where parse_code is found
        assert "parse_code" in examples[0].code
        assert "result" in examples[0].code

    def test_filters_mock_heavy_tests(self, tmp_path: Path) -> None:
        """Test that tests using extensive mocking are filtered out."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                """
            def test_with_mocks():
                mock_obj = MagicMock()
                mock_obj.method = MagicMock(return_value="test")
                with patch("module.something"):
                    result = my_function(mock_obj)
                assert result == "expected"
        """
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["my_function"],
        )

        # Mock-heavy tests should be excluded
        assert len(examples) == 0

    def test_respects_max_examples_per_entity(self, tmp_path: Path) -> None:
        """Test that max_examples_per_entity is respected."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                """
            def test_func_1():
                result = my_func(1)
                assert result == 1

            def test_func_2():
                result = my_func(2)
                assert result == 2

            def test_func_3():
                result = my_func(3)
                assert result == 3
        """
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["my_func"],
            max_examples_per_entity=2,
        )

        assert len(examples) == 2

    def test_multiple_entities(self, tmp_path: Path) -> None:
        """Test extracting examples for multiple entities."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                """
            def test_foo():
                result = foo()
                assert result == "foo"

            def test_bar():
                result = bar()
                assert result == "bar"
        """
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["foo", "bar"],
        )

        assert len(examples) == 2
        entity_names = {e.entity_name for e in examples}
        assert entity_names == {"foo", "bar"}


class TestFormatExamplesMarkdown:
    """Tests for format_examples_markdown function."""

    def test_format_single_example(self) -> None:
        """Test formatting a single example."""
        examples = [
            UsageExample(
                entity_name="my_func",
                test_name="test_my_func",
                test_file="test_example.py",
                code="result = my_func()\nassert result == 42",
                description=None,
            )
        ]

        result = format_examples_markdown(examples)

        assert "## Usage Examples" in result
        assert "Example: `my_func`" in result
        assert "test_example.py::test_my_func" in result
        assert "```python" in result
        assert "my_func()" in result

    def test_format_with_description(self) -> None:
        """Test that docstring becomes the section title."""
        examples = [
            UsageExample(
                entity_name="process",
                test_name="test_process",
                test_file="test_proc.py",
                code="process(data)",
                description="Process input data correctly",
            )
        ]

        result = format_examples_markdown(examples)

        assert "### Process input data correctly" in result

    def test_format_multiple_examples(self) -> None:
        """Test formatting multiple examples."""
        examples = [
            UsageExample(
                entity_name="func1",
                test_name="test_func1",
                test_file="test.py",
                code="func1()",
                description=None,
            ),
            UsageExample(
                entity_name="func2",
                test_name="test_func2",
                test_file="test.py",
                code="func2()",
                description=None,
            ),
        ]

        result = format_examples_markdown(examples)

        assert result.count("### Example:") == 2

    def test_format_empty_list(self) -> None:
        """Test formatting empty list returns empty string."""
        result = format_examples_markdown([])
        assert result == ""

    def test_respects_max_examples(self) -> None:
        """Test that max_examples limits output."""
        examples = [
            UsageExample(
                entity_name=f"func{i}",
                test_name=f"test_func{i}",
                test_file="test.py",
                code=f"func{i}()",
                description=None,
            )
            for i in range(10)
        ]

        result = format_examples_markdown(examples, max_examples=3)

        assert result.count("### Example:") == 3


class TestGetFileExamples:
    """Tests for get_file_examples function."""

    def test_get_file_examples_returns_markdown(self, tmp_path: Path) -> None:
        """Test that get_file_examples returns formatted markdown."""
        # Create source file
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        source_file = src_dir / "mymodule.py"
        source_file.write_text(
            dedent(
                """
            def calculate(x, y):
                return x + y
        """
            )
        )

        # Create test file
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_mymodule.py"
        test_file.write_text(
            dedent(
                '''
            def test_calculate():
                """Test basic calculation."""
                result = calculate(1, 2)
                assert result == 3
        '''
            )
        )

        result = get_file_examples(
            source_file=source_file,
            repo_root=tmp_path,
            entity_names=["calculate"],
        )

        assert result is not None
        assert "## Usage Examples" in result
        assert "calculate" in result

    def test_get_file_examples_no_test_file(self, tmp_path: Path) -> None:
        """Test returns None when no test file exists."""
        source_file = tmp_path / "orphan.py"
        source_file.write_text("def orphan(): pass")

        result = get_file_examples(
            source_file=source_file,
            repo_root=tmp_path,
            entity_names=["orphan"],
        )

        assert result is None

    def test_get_file_examples_non_python(self, tmp_path: Path) -> None:
        """Test returns None for non-Python files."""
        source_file = tmp_path / "module.ts"
        source_file.write_text("export function foo() {}")

        result = get_file_examples(
            source_file=source_file,
            repo_root=tmp_path,
            entity_names=["foo"],
        )

        assert result is None

    def test_get_file_examples_filters_short_names(self, tmp_path: Path) -> None:
        """Test that very short entity names are filtered."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        source_file = src_dir / "mod.py"
        source_file.write_text("def fn(): pass")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_mod.py"
        test_file.write_text(
            dedent(
                """
            def test_fn():
                fn()
        """
            )
        )

        result = get_file_examples(
            source_file=source_file,
            repo_root=tmp_path,
            entity_names=["fn", "x"],  # "fn" is 2 chars, "x" is 1 char
        )

        # Both names are too short (<=2 chars)
        assert result is None

    def test_get_file_examples_no_matching_tests(self, tmp_path: Path) -> None:
        """Test returns None when test file has no matching examples."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        source_file = src_dir / "api.py"
        source_file.write_text("def my_api(): pass")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_api.py"
        test_file.write_text(
            dedent(
                """
            def test_other_function():
                other_function()
        """
            )
        )

        result = get_file_examples(
            source_file=source_file,
            repo_root=tmp_path,
            entity_names=["my_api"],
        )

        assert result is None
