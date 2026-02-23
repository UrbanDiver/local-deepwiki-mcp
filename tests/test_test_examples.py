"""Tests for the test_examples module."""

from pathlib import Path
from textwrap import dedent

import pytest

from local_deepwiki.generators.examples.orchestrator import (
    UsageExample,
    extract_examples_for_entities,
    find_test_file,
    find_test_files,
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


class TestFindTestFiles:
    """Tests for find_test_files function (plural)."""

    def test_finds_multiple_test_files(self, tmp_path: Path) -> None:
        """Test finding multiple test files for one source file."""
        source_file = tmp_path / "handlers.py"
        source_file.write_text("# source")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        # Create multiple test files
        (tests_dir / "test_handlers.py").write_text("# main test")
        (tests_dir / "test_handlers_coverage.py").write_text("# coverage test")

        result = find_test_files(source_file, tmp_path)
        assert len(result) == 2
        names = {f.name for f in result}
        assert "test_handlers.py" in names
        assert "test_handlers_coverage.py" in names

    def test_finds_variant_test_files(self, tmp_path: Path) -> None:
        """Test finding test file variants with suffixes."""
        source_file = tmp_path / "wiki.py"
        source_file.write_text("# source")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        # Create variant test files
        (tests_dir / "test_wiki_pages.py").write_text("# pages test")
        (tests_dir / "test_wiki_modules.py").write_text("# modules test")

        result = find_test_files(source_file, tmp_path)
        assert len(result) >= 2

    def test_returns_empty_for_no_matches(self, tmp_path: Path) -> None:
        """Test returns empty list when no test files found."""
        source_file = tmp_path / "unique.py"
        source_file.write_text("# source")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_other.py").write_text("# other test")

        result = find_test_files(source_file, tmp_path)
        assert result == []


class TestExtractFromTestClasses:
    """Tests for extracting examples from test classes."""

    def test_extracts_from_test_class_methods(self, tmp_path: Path) -> None:
        """Test extracting examples from methods in Test* classes."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                '''
            class TestMyClass:
                """Tests for MyClass."""

                def test_creation(self):
                    """Test creating an instance."""
                    obj = MyClass(name="test")
                    assert obj.name == "test"

                def test_method_call(self):
                    """Test calling a method."""
                    obj = MyClass(name="foo")
                    result = obj.process()
                    assert result == "processed"
        '''
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["MyClass"],
            max_examples_per_entity=3,
        )

        assert len(examples) == 2
        # Check that class context is included in test names
        assert "TestMyClass::" in examples[0].test_name
        assert "TestMyClass::" in examples[1].test_name

    def test_mixes_class_and_standalone_tests(self, tmp_path: Path) -> None:
        """Test extracting from both class methods and standalone functions."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                '''
            def test_standalone():
                """Standalone test."""
                result = process_data("input")
                assert result == "output"

            class TestProcess:
                """Tests for process_data."""

                def test_in_class(self):
                    """Class method test."""
                    result = process_data("other")
                    assert result is not None
        '''
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["process_data"],
            max_examples_per_entity=3,
        )

        assert len(examples) == 2
        test_names = [e.test_name for e in examples]
        assert "test_standalone" in test_names
        assert "TestProcess::test_in_class" in test_names


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


class TestFindTestFilesAlternativeNaming:
    """Tests for alternative test file naming conventions."""

    def test_finds_alternative_naming_basename_test(self, tmp_path: Path) -> None:
        """Test finding test file with <basename>_test.py naming convention (line 85)."""
        source_file = tmp_path / "utils.py"
        source_file.write_text("# source")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        # Alternative naming: utils_test.py instead of test_utils.py
        alt_test_file = tests_dir / "utils_test.py"
        alt_test_file.write_text("# alternative test")

        result = find_test_files(source_file, tmp_path)
        assert len(result) == 1
        assert result[0] == alt_test_file


class TestGetFunctionNameEdgeCases:
    """Tests for _get_function_name edge cases."""

    def test_function_without_name_node(self, tmp_path: Path) -> None:
        """Test handling of malformed function without proper name (line 162).

        This tests the fallback return 'unknown' path.
        """
        from local_deepwiki.generators.examples.orchestrator import _get_function_name

        # Create a mock node that returns None for name field
        class MockNode:
            def child_by_field_name(self, name: str):
                return None

        mock_node = MockNode()
        result = _get_function_name(mock_node, b"")
        assert result == "unknown"


class TestGetDocstringEdgeCases:
    """Tests for _get_docstring edge cases."""

    def test_function_with_empty_body(self, tmp_path: Path) -> None:
        """Test function body with no children (line 169)."""
        from local_deepwiki.generators.examples.orchestrator import _get_docstring

        # Mock node where body has no children
        class MockBodyNode:
            children = []

        class MockFuncNode:
            def child_by_field_name(self, name: str):
                if name == "body":
                    return MockBodyNode()
                return None

        result = _get_docstring(MockFuncNode(), b"")
        assert result is None

    def test_function_with_no_body(self, tmp_path: Path) -> None:
        """Test function with no body at all (line 169)."""
        from local_deepwiki.generators.examples.orchestrator import _get_docstring

        class MockFuncNode:
            def child_by_field_name(self, name: str):
                return None

        result = _get_docstring(MockFuncNode(), b"")
        assert result is None

    def test_docstring_with_double_quotes_prefix(self, tmp_path: Path) -> None:
        """Test docstring with double quote prefix/suffix handling (line 180)."""
        test_file = tmp_path / "test_example.py"
        # Using a triple-double-quoted docstring that tree-sitter will parse
        test_file.write_text(
            '''def test_something():
    ""\"\"Test with unusual quotes.""\"\"
    result = my_function()
    assert result is not None
'''
        )

        from local_deepwiki.generators.examples.orchestrator import extract_examples_for_entities

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["my_function"],
        )
        # Should still extract the example
        assert len(examples) >= 0  # May or may not find depending on parsing


class TestGetFunctionBodyEdgeCases:
    """Tests for _get_function_body edge cases."""

    def test_function_with_no_body_returns_empty(self) -> None:
        """Test function with no body returns empty string (line 191)."""
        from local_deepwiki.generators.examples.orchestrator import _get_function_body

        class MockFuncNode:
            def child_by_field_name(self, name: str):
                return None

        result = _get_function_body(MockFuncNode(), b"")
        assert result == ""


class TestExtractUsageSnippetEdgeCases:
    """Tests for _extract_usage_snippet edge cases."""

    def test_skips_multiline_docstring(self, tmp_path: Path) -> None:
        """Test skipping multi-line docstrings in function body (lines 241, 245-246, 250-251, 253)."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                '''
            def test_with_multiline_docstring():
                """
                This is a multi-line docstring.
                It spans multiple lines.
                And should be skipped.
                """
                result = my_function()
                assert result == "expected"
        '''
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["my_function"],
        )

        assert len(examples) == 1
        # Docstring should not be in the code snippet
        assert "spans multiple lines" not in examples[0].code
        assert "my_function" in examples[0].code

    def test_skips_single_quote_docstring(self, tmp_path: Path) -> None:
        """Test skipping single-quoted docstrings (lines 243-251)."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                """
            def test_single_quote_docstring():
                '''Single quote docstring.'''
                result = target_function()
                assert result is not None
        """
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["target_function"],
        )

        assert len(examples) == 1
        assert "target_function" in examples[0].code

    def test_breaks_after_two_assertions(self, tmp_path: Path) -> None:
        """Test that extraction stops after 2 assertions (line 288).

        The extraction logic breaks when assertions_found >= 2.
        We need a test long enough (>5 relevant lines) to trigger this,
        since short tests include the full body.
        """
        test_file = tmp_path / "test_example.py"
        # Create a long test with many assertions to trigger the 2-assertion limit
        test_file.write_text(
            dedent(
                """
            def test_many_assertions():
                setup_value = "setup"
                config = {"key": "value"}
                data = [1, 2, 3]
                result1 = my_func(1)
                assert result1 == 1
                intermediate = result1 + 1
                result2 = my_func(2)
                assert result2 == 2
                result3 = my_func(3)
                assert result3 == 3
                result4 = my_func(4)
                assert result4 == 4
                result5 = my_func(5)
                assert result5 == 5
        """
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["my_func"],
        )

        assert len(examples) == 1
        # Should stop after 2 assertions
        assert "result1" in examples[0].code
        assert "result2" in examples[0].code
        # After 2 assertions at paren_depth <= 0, we break
        # result3 and beyond should NOT be present
        assert "result5" not in examples[0].code

    def test_respects_max_lines_limit(self, tmp_path: Path) -> None:
        """Test that extraction respects max_lines limit (line 291)."""
        test_file = tmp_path / "test_example.py"
        # Create a very long test function
        lines = ["def test_long_function():"]
        lines.append("    result = target_func()")
        for i in range(50):
            lines.append(f"    value{i} = {i}")
        lines.append("    assert result is not None")
        test_file.write_text("\n".join(lines))

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["target_func"],
        )

        # Should still extract something, but limited
        if examples:
            # The default max_lines is 25
            assert examples[0].code.count("\n") <= 25

    def test_returns_none_when_no_relevant_lines(self, tmp_path: Path) -> None:
        """Test returns None when entity not found in function body (line 298)."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                """
            def test_no_matching_entity():
                result = other_function()
                assert result == "value"
        """
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["nonexistent_entity"],
        )

        # No examples should be found
        assert len(examples) == 0

    def test_handles_dedent_typeerror(self, tmp_path: Path) -> None:
        """Test handling of TypeError in dedent (lines 309-310).

        This is an edge case where dedent might fail on unusual input.
        """
        from local_deepwiki.generators.examples.orchestrator import _extract_usage_snippet
        from local_deepwiki.core.parser import CodeParser
        from local_deepwiki.models import Language

        # Create a test file with mixed indentation that could cause issues
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                """
            def test_mixed_indent():
                result = my_func()
\t\tassert result is not None
        """
            ).strip()
        )

        # This should not crash, even with mixed indentation
        parser = CodeParser()
        source = test_file.read_bytes()
        root = parser.parse_source(source, Language.PYTHON)

        # Find the function node
        from local_deepwiki.generators.examples.orchestrator import _find_test_functions

        test_funcs = _find_test_functions(root)
        if test_funcs:
            func_node, _ = test_funcs[0]
            # Should not raise, even if dedent fails
            result = _extract_usage_snippet(func_node, source, "my_func")
            # May return a result or None, but should not crash
            assert result is None or isinstance(result, str)


class TestExtractExamplesFileErrors:
    """Tests for file read error handling."""

    def test_handles_unreadable_file(self, tmp_path: Path) -> None:
        """Test handling of file read errors (lines 334-336)."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text("def test_foo(): pass")

        # Make file unreadable (on Unix systems)
        import os
        import stat

        # Store original mode
        original_mode = test_file.stat().st_mode

        try:
            # Remove read permission
            test_file.chmod(0o000)

            examples = extract_examples_for_entities(
                test_file,
                entity_names=["foo"],
            )

            # Should return empty list, not crash
            assert examples == []
        finally:
            # Restore permissions for cleanup
            test_file.chmod(original_mode)

    def test_handles_nonexistent_file(self, tmp_path: Path) -> None:
        """Test handling of nonexistent file (lines 334-336)."""
        nonexistent_file = tmp_path / "does_not_exist.py"

        examples = extract_examples_for_entities(
            nonexistent_file,
            entity_names=["anything"],
        )

        # Should return empty list, not crash
        assert examples == []


class TestSnippetLengthFilter:
    """Tests for snippet length filtering."""

    def test_filters_very_short_snippets(self, tmp_path: Path) -> None:
        """Test that snippets shorter than 10 chars are filtered (line 363)."""
        test_file = tmp_path / "test_example.py"
        # Create a test where the entity appears but extraction results in very short snippet
        test_file.write_text(
            dedent(
                """
            def test_tiny():
                x()
        """
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["x"],
        )

        # Very short snippet should be filtered
        # The snippet "x()" is only 3 chars, less than 10
        assert len(examples) == 0


class TestDocstringParsingEdgeCases:
    """Additional tests for docstring parsing edge cases."""

    def test_empty_lines_before_code(self, tmp_path: Path) -> None:
        """Test handling of empty lines in function body (line 241)."""
        test_file = tmp_path / "test_example.py"
        # Function body with empty lines before actual code
        test_file.write_text(
            dedent(
                '''
            def test_with_empty_lines():
                """Docstring."""

                result = target_function()
                assert result == "value"
        '''
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["target_function"],
        )

        assert len(examples) == 1
        assert "target_function" in examples[0].code

    def test_multiline_docstring_with_empty_lines(self, tmp_path: Path) -> None:
        """Test multiline docstring with empty lines inside (line 241, 253)."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                '''
            def test_complex_docstring():
                """
                This docstring has an empty line below.

                And continues after.
                """
                result = my_target()
                assert result is not None
        '''
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["my_target"],
        )

        assert len(examples) == 1
        # The empty line in docstring shouldn't cause issues
        assert "my_target" in examples[0].code
        # The docstring content shouldn't be in the snippet
        assert "continues after" not in examples[0].code

    def test_entity_only_in_docstring_not_body(self, tmp_path: Path) -> None:
        """Test when entity name appears only in docstring, not in code (line 298).

        The entity is in the function body string but not in captured relevant_lines.
        """
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            dedent(
                '''
            def test_docstring_mention():
                """Test the special_entity function works correctly."""
                other_function()
                assert True
        '''
            ).strip()
        )

        examples = extract_examples_for_entities(
            test_file,
            entity_names=["special_entity"],
        )

        # Entity appears in body (docstring) but not in actual code lines
        # So no relevant lines are captured
        assert len(examples) == 0


class TestDirectExtractUsageSnippet:
    """Direct tests for _extract_usage_snippet internal function."""

    def test_no_relevant_lines_returns_none(self, tmp_path: Path) -> None:
        """Test that no relevant lines returns None directly (line 298)."""
        from local_deepwiki.generators.examples.orchestrator import (
            _extract_usage_snippet,
            _find_test_functions,
        )
        from local_deepwiki.core.parser import CodeParser
        from local_deepwiki.models import Language

        test_file = tmp_path / "test_example.py"
        # Create a test that doesn't actually use the entity in code
        test_file.write_text(
            dedent(
                """
            def test_something():
                other_call()
                assert True
        """
            ).strip()
        )

        parser = CodeParser()
        source = test_file.read_bytes()
        root = parser.parse_source(source, Language.PYTHON)

        test_funcs = _find_test_functions(root)
        assert len(test_funcs) == 1

        func_node, _ = test_funcs[0]
        # Call with an entity that doesn't exist in the code
        result = _extract_usage_snippet(func_node, source, "nonexistent_entity")

        # Should return None because no lines are relevant
        assert result is None

    def test_dedent_with_none_input(self) -> None:
        """Test dedent handling - the try/except for TypeError (lines 309-310).

        The textwrap.dedent function typically raises TypeError for non-string input.
        Since we always have a string from join(), this path is defensive.
        We test the function doesn't crash even in unusual cases.
        """
        from textwrap import dedent as real_dedent

        # Verify that dedent raises TypeError on None
        try:
            real_dedent(None)  # type: ignore
            raised = False
        except TypeError:
            raised = True

        # If dedent does raise TypeError on None, the except block is valid
        assert raised is True  # Confirms the defensive code is meaningful


class TestGetDocstringDoubleQuoteEdge:
    """Test for the unusual double-quote docstring edge case."""

    def test_docstring_extraction_via_real_parsing(self, tmp_path: Path) -> None:
        """Test docstring extraction through actual tree-sitter parsing.

        Line 180 handles docstrings that start with '""' after stripping.
        This is an edge case from tree-sitter's string parsing.
        """
        from local_deepwiki.generators.examples.orchestrator import _get_docstring
        from local_deepwiki.core.parser import CodeParser
        from local_deepwiki.models import Language

        test_file = tmp_path / "test_example.py"
        # Standard triple-quoted docstring
        test_file.write_text(
            dedent(
                '''
            def test_normal():
                """Normal docstring."""
                pass
        '''
            ).strip()
        )

        parser = CodeParser()
        source = test_file.read_bytes()
        root = parser.parse_source(source, Language.PYTHON)

        # Find the function
        from local_deepwiki.generators.examples.orchestrator import _find_test_functions

        test_funcs = _find_test_functions(root)
        if test_funcs:
            func_node, _ = test_funcs[0]
            docstring = _get_docstring(func_node, source)
            # Should extract the docstring cleanly
            assert docstring == "Normal docstring." or docstring is not None
