"""Tests for code example extraction from tests and docstrings.

This module tests:
- parse_doctest_examples: Extracting >>> style examples
- parse_google_style_examples: Extracting Google-style Examples sections
- parse_docstring_examples: Combined parsing
- CodeExampleExtractor: Vector store based extraction
- ExamplesWikiGenerator: Wiki plugin integration
"""

from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.generators.examples.docstring import (
    CodeExample,
    parse_docstring_examples,
    parse_doctest_examples,
    parse_google_style_examples,
)
from local_deepwiki.generators.examples.extractor import (
    CodeExampleExtractor,
    format_code_examples_markdown,
)


class TestParseDoctestExamples:
    """Tests for parse_doctest_examples function."""

    def test_simple_doctest(self) -> None:
        """Test parsing a simple doctest example."""
        docstring = """
        Some description.

        >>> add(1, 2)
        3
        """
        examples = parse_doctest_examples(docstring)

        assert len(examples) == 1
        assert examples[0].source == "docstring"
        assert examples[0].code == "add(1, 2)"
        assert examples[0].expected_output == "3"

    def test_multiple_doctests(self) -> None:
        """Test parsing multiple doctest examples."""
        docstring = """
        >>> add(1, 2)
        3
        >>> add(-1, 1)
        0
        >>> add(0, 0)
        0
        """
        examples = parse_doctest_examples(docstring)

        assert len(examples) == 3
        assert examples[0].code == "add(1, 2)"
        assert examples[1].code == "add(-1, 1)"
        assert examples[2].code == "add(0, 0)"

    def test_multiline_doctest(self) -> None:
        """Test parsing doctest with continuation lines."""
        docstring = """
        >>> result = some_function(
        ...     param1="value1",
        ...     param2="value2",
        ... )
        >>> print(result)
        output
        """
        examples = parse_doctest_examples(docstring)

        assert len(examples) == 2
        # First example is the multiline call
        assert "some_function(" in examples[0].code
        assert 'param1="value1"' in examples[0].code
        # Second example is the print
        assert examples[1].code == "print(result)"
        assert examples[1].expected_output == "output"

    def test_doctest_with_multiline_output(self) -> None:
        """Test doctest with multiple lines of output."""
        docstring = """
        >>> list_items()
        item1
        item2
        item3
        """
        examples = parse_doctest_examples(docstring)

        assert len(examples) == 1
        assert examples[0].code == "list_items()"
        assert "item1" in examples[0].expected_output
        assert "item2" in examples[0].expected_output
        assert "item3" in examples[0].expected_output

    def test_empty_docstring(self) -> None:
        """Test empty docstring returns empty list."""
        assert parse_doctest_examples("") == []
        assert parse_doctest_examples(None) == []

    def test_docstring_without_examples(self) -> None:
        """Test docstring without examples returns empty list."""
        docstring = """
        This is a description.

        Args:
            param: A parameter.

        Returns:
            Something.
        """
        examples = parse_doctest_examples(docstring)
        assert examples == []

    def test_doctest_no_output(self) -> None:
        """Test doctest without expected output."""
        docstring = """
        >>> do_something()
        """
        examples = parse_doctest_examples(docstring)

        assert len(examples) == 1
        assert examples[0].code == "do_something()"
        assert examples[0].expected_output is None


class TestParseGoogleStyleExamples:
    """Tests for parse_google_style_examples function."""

    def test_simple_google_examples(self) -> None:
        """Test parsing simple Google-style examples."""
        docstring = """
        Some description.

        Examples:
            result = process("input")
            print(result)
        """
        examples = parse_google_style_examples(docstring)

        assert len(examples) >= 1
        assert "process" in examples[0].code

    def test_google_examples_with_descriptions(self) -> None:
        """Test Google-style examples with description headers."""
        docstring = """
        Do something.

        Examples:
            Basic usage:
                result = func(1)

            With options:
                result = func(1, verbose=True)
        """
        examples = parse_google_style_examples(docstring)

        assert len(examples) >= 1

    def test_google_examples_before_other_sections(self) -> None:
        """Test that parsing stops at next section."""
        docstring = """
        Description.

        Examples:
            x = foo()

        Returns:
            The result.
        """
        examples = parse_google_style_examples(docstring)

        assert len(examples) >= 1
        # Should not include Returns section
        for ex in examples:
            assert "Returns" not in ex.code

    def test_example_singular(self) -> None:
        """Test 'Example:' (singular) is also parsed."""
        docstring = """
        Description.

        Example:
            result = single_example()
        """
        examples = parse_google_style_examples(docstring)

        assert len(examples) >= 1
        assert "single_example" in examples[0].code

    def test_empty_docstring(self) -> None:
        """Test empty docstring returns empty list."""
        assert parse_google_style_examples("") == []
        assert parse_google_style_examples(None) == []

    def test_no_examples_section(self) -> None:
        """Test docstring without Examples section."""
        docstring = """
        Description.

        Args:
            x: A parameter.

        Returns:
            Something.
        """
        examples = parse_google_style_examples(docstring)
        assert examples == []


class TestParseDocstringExamples:
    """Tests for the combined parse_docstring_examples function."""

    def test_prefers_doctests(self) -> None:
        """Test that doctests are extracted when present."""
        docstring = """
        Description.

        >>> foo()
        bar

        Examples:
            result = foo()
        """
        examples = parse_docstring_examples(docstring)

        # Should have doctest examples
        doctest_examples = [
            ex for ex in examples if ">>>" not in ex.code or ex.expected_output
        ]
        assert len(doctest_examples) >= 1

    def test_falls_back_to_google(self) -> None:
        """Test fallback to Google-style when no doctests."""
        docstring = """
        Description.

        Examples:
            result = process()
        """
        examples = parse_docstring_examples(docstring)

        assert len(examples) >= 1

    def test_empty_returns_empty(self) -> None:
        """Test empty/None docstring returns empty list."""
        assert parse_docstring_examples("") == []
        assert parse_docstring_examples(None) == []


class TestCodeExample:
    """Tests for the CodeExample dataclass."""

    def test_creation(self) -> None:
        """Test creating a CodeExample."""
        ex = CodeExample(
            source="test",
            code="result = func()",
            description="Test function call",
            test_file="test_example.py",
            language="python",
        )

        assert ex.source == "test"
        assert ex.code == "result = func()"
        assert ex.description == "Test function call"
        assert ex.test_file == "test_example.py"
        assert ex.language == "python"

    def test_defaults(self) -> None:
        """Test default values."""
        ex = CodeExample(source="docstring", code="x = 1")

        assert ex.description is None
        assert ex.test_file is None
        assert ex.language == "python"
        assert ex.expected_output is None
        assert ex.entity_name is None


class TestCodeExampleExtractor:
    """Tests for the CodeExampleExtractor class."""

    @pytest.fixture
    def mock_vector_store(self) -> MagicMock:
        """Create a mock vector store."""
        store = MagicMock()
        store.search = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def extractor(self, mock_vector_store: MagicMock) -> CodeExampleExtractor:
        """Create an extractor with mock store."""
        return CodeExampleExtractor(mock_vector_store)

    async def test_extract_examples_for_function_empty(
        self,
        extractor: CodeExampleExtractor,
    ) -> None:
        """Test extraction when no results found."""
        examples = await extractor.extract_examples_for_function("my_func")
        assert examples == []

    async def test_extract_examples_for_function_short_name(
        self,
        extractor: CodeExampleExtractor,
    ) -> None:
        """Test that short names are skipped."""
        examples = await extractor.extract_examples_for_function("fn")
        assert examples == []

    async def test_extract_examples_for_function_with_results(
        self,
        mock_vector_store: MagicMock,
        extractor: CodeExampleExtractor,
    ) -> None:
        """Test extraction with mock search results."""
        # Create mock chunk
        mock_chunk = MagicMock()
        mock_chunk.name = "test_process_data"
        mock_chunk.content = dedent("""
            def test_process_data():
                result = process_data("input")
                assert result == "output"
        """)
        mock_chunk.docstring = "Test the process_data function."
        mock_chunk.file_path = "tests/test_module.py"
        mock_chunk.language = MagicMock()
        mock_chunk.language.value = "python"

        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        examples = await extractor.extract_examples_for_function("process_data")

        # Should find the test example
        assert len(examples) >= 1
        assert any("process_data" in ex.code for ex in examples)

    async def test_extract_examples_for_function_skips_mocks(
        self,
        mock_vector_store: MagicMock,
        extractor: CodeExampleExtractor,
    ) -> None:
        """Test that mock-heavy tests are skipped."""
        mock_chunk = MagicMock()
        mock_chunk.name = "test_with_mocks"
        mock_chunk.content = dedent("""
            def test_with_mocks():
                mock = MagicMock()
                with patch("module.func"):
                    result = my_func(mock)
                assert result
        """)
        mock_chunk.docstring = None
        mock_chunk.file_path = "tests/test_module.py"
        mock_chunk.language = MagicMock()
        mock_chunk.language.value = "python"

        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        examples = await extractor.extract_examples_for_function("my_func")

        # Mock-heavy test should be skipped
        assert len(examples) == 0

    async def test_extract_examples_for_class(
        self,
        mock_vector_store: MagicMock,
        extractor: CodeExampleExtractor,
    ) -> None:
        """Test class example extraction."""
        mock_chunk = MagicMock()
        mock_chunk.name = "test_my_class"
        mock_chunk.content = dedent("""
            def test_my_class():
                obj = MyClass(name="test")
                assert obj.name == "test"
        """)
        mock_chunk.docstring = None
        mock_chunk.file_path = "tests/test_classes.py"
        mock_chunk.language = MagicMock()
        mock_chunk.language.value = "python"

        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        examples = await extractor.extract_examples_for_class("MyClass")

        assert len(examples) >= 1

    async def test_extract_examples_with_docstring(
        self,
        mock_vector_store: MagicMock,
        extractor: CodeExampleExtractor,
    ) -> None:
        """Test extraction includes docstring examples."""
        # Mock the entity definition with docstring
        mock_chunk = MagicMock()
        mock_chunk.name = "calculate"
        mock_chunk.content = "def calculate(x, y): return x + y"
        mock_chunk.docstring = """
        Calculate the sum.

        >>> calculate(1, 2)
        3
        """
        mock_chunk.file_path = "src/math.py"
        mock_chunk.language = MagicMock()
        mock_chunk.language.value = "python"

        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        examples = await extractor.extract_examples_for_function("calculate")

        # Should include docstring example
        docstring_examples = [ex for ex in examples if ex.source == "docstring"]
        assert len(docstring_examples) >= 1

    async def test_deduplication(
        self,
        mock_vector_store: MagicMock,
        extractor: CodeExampleExtractor,
    ) -> None:
        """Test that duplicate examples are removed."""
        # Create two chunks with similar code
        mock_chunk1 = MagicMock()
        mock_chunk1.name = "test_func_1"
        mock_chunk1.content = "result = func()\nassert result"
        mock_chunk1.docstring = None
        mock_chunk1.file_path = "tests/test1.py"
        mock_chunk1.language = MagicMock()
        mock_chunk1.language.value = "python"

        mock_chunk2 = MagicMock()
        mock_chunk2.name = "test_func_2"
        mock_chunk2.content = "result = func()\nassert result"  # Same code
        mock_chunk2.docstring = None
        mock_chunk2.file_path = "tests/test2.py"
        mock_chunk2.language = MagicMock()
        mock_chunk2.language.value = "python"

        mock_result1 = MagicMock()
        mock_result1.chunk = mock_chunk1
        mock_result2 = MagicMock()
        mock_result2.chunk = mock_chunk2

        mock_vector_store.search = AsyncMock(return_value=[mock_result1, mock_result2])

        examples = await extractor.extract_examples_for_function("func")

        # Should deduplicate
        codes = [ex.code.strip()[:50] for ex in examples]
        assert len(codes) == len(set(codes))  # No duplicates


class TestFormatCodeExamplesMarkdown:
    """Tests for format_code_examples_markdown function."""

    def test_empty_list(self) -> None:
        """Test formatting empty list."""
        result = format_code_examples_markdown([])
        assert result == ""

    def test_single_example(self) -> None:
        """Test formatting a single example."""
        examples = [
            CodeExample(
                source="test",
                code="result = func()",
                entity_name="func",
            )
        ]

        result = format_code_examples_markdown(examples)

        assert "## Examples" in result
        assert "```python" in result
        assert "result = func()" in result

    def test_with_description(self) -> None:
        """Test formatting with description."""
        examples = [
            CodeExample(
                source="docstring",
                code="x = 1",
                description="Basic usage",
            )
        ]

        result = format_code_examples_markdown(examples)

        assert "### Basic usage" in result

    def test_with_expected_output(self) -> None:
        """Test formatting with expected output."""
        examples = [
            CodeExample(
                source="docstring",
                code="add(1, 2)",
                expected_output="3",
            )
        ]

        result = format_code_examples_markdown(examples)

        assert "Output:" in result
        assert "3" in result

    def test_respects_max_examples(self) -> None:
        """Test max_examples limit."""
        examples = [CodeExample(source="test", code=f"func{i}()") for i in range(10)]

        result = format_code_examples_markdown(examples, max_examples=3)

        # Should only have 3 examples
        assert result.count("```python") == 3


class TestExamplesWikiGenerator:
    """Tests for the ExamplesWikiGenerator plugin."""

    @pytest.fixture
    def mock_vector_store(self) -> MagicMock:
        """Create a mock vector store."""
        store = MagicMock()
        store.search = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def mock_index_status(self) -> MagicMock:
        """Create a mock index status."""
        status = MagicMock()
        status.repo_path = "/tmp/test-repo"
        return status

    async def test_generator_metadata(self) -> None:
        """Test plugin metadata."""
        from local_deepwiki.generators.examples.plugin import ExamplesWikiGenerator

        generator = ExamplesWikiGenerator()

        assert generator.metadata.name == "examples-generator"
        assert generator.generator_name == "examples"
        assert generator.priority == 50

    async def test_generate_no_vector_store(
        self,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generation without vector store."""
        from local_deepwiki.generators.examples.plugin import ExamplesWikiGenerator

        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={},
        )

        assert result.pages == []

    async def test_generate_no_examples(
        self,
        mock_vector_store: MagicMock,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generation when no examples found."""
        from local_deepwiki.generators.examples.plugin import ExamplesWikiGenerator

        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={"vector_store": mock_vector_store},
        )

        # No examples found, no pages generated
        assert result.pages == []

    async def test_generate_with_examples(
        self,
        mock_vector_store: MagicMock,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generation with examples."""
        from local_deepwiki.generators.examples.plugin import ExamplesWikiGenerator

        # Create mock chunk with docstring example
        mock_chunk = MagicMock()
        mock_chunk.name = "process_data"
        mock_chunk.content = "def process_data(x): return x"
        mock_chunk.docstring = """
        Process the data.

        >>> process_data("input")
        'input'
        """
        mock_chunk.file_path = "src/module.py"
        mock_chunk.language = MagicMock()
        mock_chunk.language.value = "python"

        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        # Return the chunk for function search
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={"vector_store": mock_vector_store},
        )

        # Should generate examples page
        assert len(result.pages) == 1
        assert result.pages[0].path == "examples.md"
        assert "Code Examples" in result.pages[0].content


class TestExtractRelevantSnippet:
    """Tests for the _extract_relevant_snippet method."""

    @pytest.fixture
    def extractor(self) -> CodeExampleExtractor:
        """Create an extractor with mock store."""
        mock_store = MagicMock()
        return CodeExampleExtractor(mock_store)

    def test_extract_simple_snippet(self, extractor: CodeExampleExtractor) -> None:
        """Test extracting a simple snippet."""
        content = dedent("""
            def test_func():
                result = my_func()
                assert result == "expected"
        """)

        snippet = extractor._extract_relevant_snippet(content, "my_func")

        assert snippet is not None
        assert "my_func" in snippet
        assert "assert" in snippet

    def test_extract_skips_docstring(self, extractor: CodeExampleExtractor) -> None:
        """Test that docstrings are skipped."""
        content = dedent('''
            def test_func():
                """This is a docstring."""
                result = target()
                assert result
        ''')

        snippet = extractor._extract_relevant_snippet(content, "target")

        assert snippet is not None
        assert "docstring" not in snippet

    def test_extract_returns_none_no_match(
        self, extractor: CodeExampleExtractor
    ) -> None:
        """Test returns None when entity not found."""
        content = "result = other_func()"

        snippet = extractor._extract_relevant_snippet(content, "nonexistent")

        assert snippet is None

    def test_extract_limits_assertions(self, extractor: CodeExampleExtractor) -> None:
        """Test that extraction stops after assertions."""
        content = dedent("""
            def test_func():
                result1 = func()
                assert result1 == 1
                result2 = func()
                assert result2 == 2
                result3 = func()
                assert result3 == 3
        """)

        snippet = extractor._extract_relevant_snippet(content, "func")

        assert snippet is not None
        # Should stop after 2 assertions
        assert "result1" in snippet
        assert "result2" in snippet
        # result3 might or might not be included depending on line count
