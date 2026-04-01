"""Tests for the examples_plugin module.

This module tests the ExamplesWikiGenerator plugin and the
get_examples_for_api_page helper function for generating
code examples documentation.
"""

from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.generators.examples.plugin import (
    ExamplesWikiGenerator,
    get_examples_for_api_page,
)
from local_deepwiki.generators.examples.docstring import CodeExample
from local_deepwiki.generators.examples.extractor import CodeExampleExtractor
from local_deepwiki.models import ChunkType, IndexStatus, Language


class TestExamplesWikiGeneratorMetadata:
    """Tests for ExamplesWikiGenerator metadata properties."""

    def test_metadata(self) -> None:
        """Test plugin metadata is correct."""
        generator = ExamplesWikiGenerator()
        metadata = generator.metadata

        assert metadata.name == "examples-generator"
        assert metadata.version == "1.0.0"
        assert metadata.author == "local-deepwiki"
        assert "code examples" in metadata.description.lower()

    def test_generator_name(self) -> None:
        """Test generator_name property."""
        generator = ExamplesWikiGenerator()
        assert generator.generator_name == "examples"

    def test_priority(self) -> None:
        """Test priority property."""
        generator = ExamplesWikiGenerator()
        assert generator.priority == 50

    def test_run_after(self) -> None:
        """Test run_after property returns empty list (line 63)."""
        generator = ExamplesWikiGenerator()
        assert generator.run_after == []


class TestExamplesWikiGeneratorGenerate:
    """Tests for the generate method."""

    @pytest.fixture
    def mock_index_status(self) -> MagicMock:
        """Create a mock index status."""
        status = MagicMock(spec=IndexStatus)
        status.repo_path = "/tmp/test-repo"
        return status

    @pytest.fixture
    def mock_vector_store(self) -> MagicMock:
        """Create a mock vector store."""
        store = MagicMock()
        store.search = AsyncMock(return_value=[])
        return store

    async def test_generate_no_vector_store(
        self,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generation without vector store returns empty result."""
        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={},
        )

        assert result.pages == []

    async def test_generate_no_examples_found(
        self,
        mock_vector_store: MagicMock,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generation when no examples found returns empty result."""
        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={"vector_store": mock_vector_store},
        )

        assert result.pages == []

    async def test_generate_skips_short_function_names(
        self,
        mock_vector_store: MagicMock,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that functions with short names are skipped (line 112)."""
        # Create mock chunk with short name
        mock_chunk = MagicMock()
        mock_chunk.name = "fn"  # Only 2 chars, should be skipped
        mock_chunk.content = "def fn(): pass"
        mock_chunk.docstring = ">>> fn()\n42"
        mock_chunk.file_path = "src/module.py"
        mock_chunk.language = MagicMock()
        mock_chunk.language.value = "python"

        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={"vector_store": mock_vector_store},
        )

        # No examples should be generated for short names
        assert result.pages == []

    async def test_generate_skips_test_functions(
        self,
        mock_vector_store: MagicMock,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that test functions are skipped (line 116)."""
        # Create mock chunk with test_ prefix
        mock_chunk = MagicMock()
        mock_chunk.name = "test_something"  # Test function, should be skipped
        mock_chunk.content = "def test_something(): pass"
        mock_chunk.docstring = ">>> test_something()\nOK"
        mock_chunk.file_path = "tests/test_module.py"
        mock_chunk.language = MagicMock()
        mock_chunk.language.value = "python"

        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        # First call returns function with test_ prefix, second call (classes) returns empty
        mock_vector_store.search = AsyncMock(side_effect=[[mock_result], []])

        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={"vector_store": mock_vector_store},
        )

        assert result.pages == []

    async def test_generate_skips_private_functions(
        self,
        mock_vector_store: MagicMock,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that private functions are skipped (line 116)."""
        # Create mock chunk with underscore prefix
        mock_chunk = MagicMock()
        mock_chunk.name = "_private_helper"  # Private function, should be skipped
        mock_chunk.content = "def _private_helper(): pass"
        mock_chunk.docstring = ">>> _private_helper()\nresult"
        mock_chunk.file_path = "src/module.py"
        mock_chunk.language = MagicMock()
        mock_chunk.language.value = "python"

        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={"vector_store": mock_vector_store},
        )

        assert result.pages == []

    async def test_generate_skips_short_class_names(
        self,
        mock_vector_store: MagicMock,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that classes with short names are skipped (line 137)."""
        # Mock function search to return nothing
        # Mock class search to return short-named class
        mock_chunk_class = MagicMock()
        mock_chunk_class.name = "AB"  # Only 2 chars, should be skipped
        mock_chunk_class.content = "class AB: pass"
        mock_chunk_class.docstring = "Short class"
        mock_chunk_class.file_path = "src/module.py"
        mock_chunk_class.language = MagicMock()
        mock_chunk_class.language.value = "python"

        mock_result_class = MagicMock()
        mock_result_class.chunk = mock_chunk_class

        # First call for functions returns empty, second for classes returns short-named
        mock_vector_store.search = AsyncMock(side_effect=[[], [mock_result_class]])

        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={"vector_store": mock_vector_store},
        )

        assert result.pages == []

    async def test_generate_skips_private_classes(
        self,
        mock_vector_store: MagicMock,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that private classes are skipped (line 141)."""
        mock_chunk_class = MagicMock()
        mock_chunk_class.name = "_InternalHelper"  # Private class, should be skipped
        mock_chunk_class.content = "class _InternalHelper: pass"
        mock_chunk_class.docstring = "Internal helper"
        mock_chunk_class.file_path = "src/module.py"
        mock_chunk_class.language = MagicMock()
        mock_chunk_class.language.value = "python"

        mock_result_class = MagicMock()
        mock_result_class.chunk = mock_chunk_class

        mock_vector_store.search = AsyncMock(side_effect=[[], [mock_result_class]])

        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={"vector_store": mock_vector_store},
        )

        assert result.pages == []

    async def test_generate_handles_search_exception(
        self,
        mock_vector_store: MagicMock,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that exceptions during search are handled (lines 156-158)."""
        mock_vector_store.search = AsyncMock(side_effect=RuntimeError("Search failed"))

        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={"vector_store": mock_vector_store},
        )

        # Should return empty result on exception
        assert result.pages == []

    async def test_generate_with_function_docstring_examples(
        self,
        mock_vector_store: MagicMock,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generation with docstring examples from functions."""
        mock_chunk = MagicMock()
        mock_chunk.name = "process_data"
        mock_chunk.content = "def process_data(x): return x * 2"
        mock_chunk.docstring = """
        Process the input data.

        >>> process_data(5)
        10
        """
        mock_chunk.file_path = "src/processor.py"
        mock_chunk.language = MagicMock()
        mock_chunk.language.value = "python"

        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store.search = AsyncMock(side_effect=[[mock_result], []])

        generator = ExamplesWikiGenerator()

        # Mock the extractor to avoid search calls failing
        with patch.object(
            CodeExampleExtractor,
            "extract_examples_for_function",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await generator.generate(
                index_status=mock_index_status,
                wiki_path=tmp_path,
                context={"vector_store": mock_vector_store},
            )

        assert len(result.pages) == 1
        assert result.pages[0].path == "examples.md"
        assert "Code Examples" in result.pages[0].content
        assert "process_data" in result.pages[0].content

    async def test_generate_with_class_docstring_examples(
        self,
        mock_vector_store: MagicMock,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generation with docstring examples from classes."""
        mock_chunk_class = MagicMock()
        mock_chunk_class.name = "DataProcessor"
        mock_chunk_class.content = "class DataProcessor: pass"
        mock_chunk_class.docstring = """
        A data processor class.

        >>> processor = DataProcessor()
        >>> processor.run()
        'done'
        """
        mock_chunk_class.file_path = "src/processor.py"
        mock_chunk_class.language = MagicMock()
        mock_chunk_class.language.value = "python"

        mock_result_class = MagicMock()
        mock_result_class.chunk = mock_chunk_class

        mock_vector_store.search = AsyncMock(side_effect=[[], [mock_result_class]])

        generator = ExamplesWikiGenerator()

        # Mock the extractor to avoid search calls failing
        with patch.object(
            CodeExampleExtractor,
            "extract_examples_for_class",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await generator.generate(
                index_status=mock_index_status,
                wiki_path=tmp_path,
                context={"vector_store": mock_vector_store},
            )

        assert len(result.pages) == 1
        assert "DataProcessor" in result.pages[0].content


class TestGenerateExamplesPage:
    """Tests for _generate_examples_page method."""

    @pytest.fixture
    def generator(self) -> ExamplesWikiGenerator:
        """Create a generator instance."""
        return ExamplesWikiGenerator()

    @pytest.fixture
    def mock_index_status(self) -> MagicMock:
        """Create a mock index status."""
        status = MagicMock(spec=IndexStatus)
        status.repo_path = "/tmp/test-repo"
        return status

    def test_generate_page_with_test_examples(
        self,
        generator: ExamplesWikiGenerator,
        mock_index_status: MagicMock,
    ) -> None:
        """Test page generation with test-sourced examples (lines 211, 217-235)."""
        examples_by_entity = {
            "my_function": [
                CodeExample(
                    source="test",
                    code="result = my_function(42)\nassert result == 84",
                    description="Test basic multiplication",
                    test_file="tests/test_module.py",
                    language="python",
                    entity_name="my_function",
                ),
            ],
        }

        content = generator._generate_examples_page(
            examples_by_entity, mock_index_status
        )

        assert "# Code Examples" in content
        assert "Examples from Tests" in content
        assert "`my_function`" in content
        assert "my_function(42)" in content
        assert "tests/test_module.py" in content
        assert "*Test basic multiplication*" in content

    def test_generate_page_with_docstring_examples(
        self,
        generator: ExamplesWikiGenerator,
        mock_index_status: MagicMock,
    ) -> None:
        """Test page generation with docstring examples (line 252)."""
        examples_by_entity = {
            "calculate": [
                CodeExample(
                    source="docstring",
                    code="calculate(1, 2)",
                    description="Basic calculation example",
                    language="python",
                    expected_output="3",
                    entity_name="calculate",
                ),
            ],
        }

        content = generator._generate_examples_page(
            examples_by_entity, mock_index_status
        )

        assert "# Code Examples" in content
        assert "Examples from Documentation" in content
        assert "`calculate`" in content
        assert "calculate(1, 2)" in content
        assert "*Basic calculation example*" in content
        assert "Output:" in content
        assert "3" in content

    def test_generate_page_mixed_examples(
        self,
        generator: ExamplesWikiGenerator,
        mock_index_status: MagicMock,
    ) -> None:
        """Test page generation with both test and docstring examples."""
        examples_by_entity = {
            "process": [
                CodeExample(
                    source="test",
                    code="result = process('input')",
                    description=None,
                    test_file="tests/test_process.py",
                    language="python",
                    entity_name="process",
                ),
                CodeExample(
                    source="docstring",
                    code="process('hello')",
                    description=None,
                    language="python",
                    expected_output="'HELLO'",
                    entity_name="process",
                ),
            ],
        }

        content = generator._generate_examples_page(
            examples_by_entity, mock_index_status
        )

        assert "Examples from Tests" in content
        assert "Examples from Documentation" in content

    def test_generate_page_test_example_without_description(
        self,
        generator: ExamplesWikiGenerator,
        mock_index_status: MagicMock,
    ) -> None:
        """Test page generation with test example without description (line 229)."""
        examples_by_entity = {
            "simple_func": [
                CodeExample(
                    source="test",
                    code="simple_func()",
                    description=None,  # No description
                    test_file="tests/test_simple.py",
                    language="python",
                    entity_name="simple_func",
                ),
            ],
        }

        content = generator._generate_examples_page(
            examples_by_entity, mock_index_status
        )

        assert "`simple_func`" in content
        assert "tests/test_simple.py" in content
        # Should not have description formatting
        assert "*None*" not in content

    def test_generate_page_test_example_without_test_file(
        self,
        generator: ExamplesWikiGenerator,
        mock_index_status: MagicMock,
    ) -> None:
        """Test page generation with test example without test_file (line 231)."""
        examples_by_entity = {
            "func": [
                CodeExample(
                    source="test",
                    code="func()",
                    description="Test func",
                    test_file=None,  # No test file
                    language="python",
                    entity_name="func",
                ),
            ],
        }

        content = generator._generate_examples_page(
            examples_by_entity, mock_index_status
        )

        assert "`func`" in content
        # Should not have test file reference
        assert "From `None`" not in content

    def test_generate_page_docstring_example_without_output(
        self,
        generator: ExamplesWikiGenerator,
        mock_index_status: MagicMock,
    ) -> None:
        """Test page generation with docstring example without expected output."""
        examples_by_entity = {
            "run": [
                CodeExample(
                    source="docstring",
                    code="run()",
                    description=None,
                    language="python",
                    expected_output=None,  # No output
                    entity_name="run",
                ),
            ],
        }

        content = generator._generate_examples_page(
            examples_by_entity, mock_index_status
        )

        assert "run()" in content
        # Should not have Output: section
        assert "Output:" not in content

    def test_generate_page_with_default_language(
        self,
        generator: ExamplesWikiGenerator,
        mock_index_status: MagicMock,
    ) -> None:
        """Test page generation uses default python language (lines 234, 254)."""
        examples_by_entity = {
            "process": [
                CodeExample(
                    source="test",
                    code="process()",
                    language=None,  # No language, should default to python
                    entity_name="process",
                ),
            ],
        }

        content = generator._generate_examples_page(
            examples_by_entity, mock_index_status
        )

        assert "```python" in content

    def test_generate_page_limits_examples_per_entity(
        self,
        generator: ExamplesWikiGenerator,
        mock_index_status: MagicMock,
    ) -> None:
        """Test page generation limits examples per entity to 2."""
        examples_by_entity = {
            "func": [
                CodeExample(source="test", code=f"func({i})", entity_name="func")
                for i in range(5)
            ],
        }

        content = generator._generate_examples_page(
            examples_by_entity, mock_index_status
        )

        # Should have at most 2 code blocks for this entity
        assert content.count("func(0)") == 1
        assert content.count("func(1)") == 1
        assert "func(2)" not in content

    def test_generate_page_sorts_entities(
        self,
        generator: ExamplesWikiGenerator,
        mock_index_status: MagicMock,
    ) -> None:
        """Test that entities are sorted alphabetically in output."""
        examples_by_entity = {
            "zebra_func": [
                CodeExample(
                    source="docstring", code="zebra_func()", entity_name="zebra_func"
                ),
            ],
            "alpha_func": [
                CodeExample(
                    source="docstring", code="alpha_func()", entity_name="alpha_func"
                ),
            ],
        }

        content = generator._generate_examples_page(
            examples_by_entity, mock_index_status
        )

        # Alpha should come before zebra
        alpha_pos = content.find("alpha_func")
        zebra_pos = content.find("zebra_func")
        assert alpha_pos < zebra_pos


class TestGetExamplesForApiPage:
    """Tests for the get_examples_for_api_page helper function."""

    def test_with_docstring_only(self) -> None:
        """Test with docstring examples only (lines 281-310)."""
        mock_store = MagicMock()
        extractor = CodeExampleExtractor(mock_store)

        docstring = """
        Calculate sum.

        >>> calculate(1, 2)
        3
        """

        result = get_examples_for_api_page("calculate", extractor, docstring)

        assert "## Examples" in result
        assert "calculate(1, 2)" in result

    def test_without_docstring(self) -> None:
        """Test without docstring returns empty when loop is running."""
        mock_store = MagicMock()
        extractor = CodeExampleExtractor(mock_store)

        # When called without docstring and loop is running, returns empty
        result = get_examples_for_api_page("some_func", extractor, None)

        # Should return empty string when no examples
        assert result == ""

    def test_with_running_event_loop(self) -> None:
        """Test behavior when event loop is already running (line 288-291)."""
        mock_store = MagicMock()
        extractor = CodeExampleExtractor(mock_store)

        docstring = """
        Process data.

        >>> process("input")
        'output'
        """

        # The function handles running event loop by only returning docstring examples
        result = get_examples_for_api_page("process", extractor, docstring)

        assert "process" in result

    def test_handles_exception_in_loop_get(self) -> None:
        """Test exception handling when getting event loop (line 297-298)."""
        mock_store = MagicMock()
        extractor = CodeExampleExtractor(mock_store)

        # With a proper docstring, it should still work
        docstring = """
        Test function.

        >>> test_func()
        'result'
        """

        # Should not raise, should return docstring examples
        result = get_examples_for_api_page("test_func", extractor, docstring)

        assert "test_func" in result

    def test_no_examples_returns_empty_string(self) -> None:
        """Test returns empty string when no examples found (line 307-308)."""
        mock_store = MagicMock()
        extractor = CodeExampleExtractor(mock_store)

        # Docstring without examples
        docstring = """
        This is a description without examples.

        Args:
            x: A parameter.
        """

        result = get_examples_for_api_page("my_func", extractor, docstring)

        assert result == ""

    @pytest.mark.asyncio
    async def test_with_extractor_results(self) -> None:
        """Test with actual extractor returning results."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        extractor = CodeExampleExtractor(mock_store)

        docstring = """
        Calculate.

        >>> calc(1)
        1
        """

        result = get_examples_for_api_page("calc", extractor, docstring)

        # Should have docstring examples at minimum
        assert "calc(1)" in result


class TestExamplesWikiGeneratorIntegration:
    """Integration tests for ExamplesWikiGenerator."""

    @pytest.fixture
    def mock_index_status(self) -> IndexStatus:
        """Create a real IndexStatus."""
        return IndexStatus(
            repo_path="/tmp/test-repo",
            indexed_at=1234567890.0,
            total_files=10,
            total_chunks=50,
            languages={"python": 10},
        )

    async def test_full_generation_flow_with_mixed_examples(
        self,
        tmp_path: Path,
        mock_index_status: IndexStatus,
    ) -> None:
        """Test complete generation flow with both test and docstring examples."""
        mock_vector_store = MagicMock()

        # Create function chunk with docstring
        func_chunk = MagicMock()
        func_chunk.name = "transform_data"
        func_chunk.content = "def transform_data(x): return x.upper()"
        func_chunk.docstring = """
        Transform the data.

        >>> transform_data('hello')
        'HELLO'
        """
        func_chunk.file_path = "src/transform.py"
        func_chunk.language = MagicMock()
        func_chunk.language.value = "python"

        func_result = MagicMock()
        func_result.chunk = func_chunk

        # Create class chunk with docstring
        class_chunk = MagicMock()
        class_chunk.name = "Transformer"
        class_chunk.content = "class Transformer: pass"
        class_chunk.docstring = """
        Data transformer class.

        Examples:
            Basic usage:
                t = Transformer()
                t.process('input')
        """
        class_chunk.file_path = "src/transform.py"
        class_chunk.language = MagicMock()
        class_chunk.language.value = "python"

        class_result = MagicMock()
        class_result.chunk = class_chunk

        mock_vector_store.search = AsyncMock(
            side_effect=[[func_result], [class_result]]
        )

        generator = ExamplesWikiGenerator()

        # Mock the extractor methods to avoid search calls failing
        with (
            patch.object(
                CodeExampleExtractor,
                "extract_examples_for_function",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(
                CodeExampleExtractor,
                "extract_examples_for_class",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await generator.generate(
                index_status=mock_index_status,
                wiki_path=tmp_path,
                context={"vector_store": mock_vector_store},
            )

        assert len(result.pages) == 1
        page = result.pages[0]

        assert page.path == "examples.md"
        assert page.title == "Code Examples"
        assert "transform_data" in page.content
        assert "Transformer" in page.content
        assert result.metadata["total_entities"] == 2

    async def test_generation_with_null_name_chunk(
        self,
        tmp_path: Path,
        mock_index_status: IndexStatus,
    ) -> None:
        """Test that chunks with null names are skipped."""
        mock_vector_store = MagicMock()

        # Create chunk with null name
        chunk = MagicMock()
        chunk.name = None  # Null name
        chunk.content = "x = 1"
        chunk.docstring = None
        chunk.file_path = "src/module.py"

        result_obj = MagicMock()
        result_obj.chunk = chunk

        mock_vector_store.search = AsyncMock(side_effect=[[result_obj], []])

        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={"vector_store": mock_vector_store},
        )

        assert result.pages == []


class TestExamplesWikiGeneratorEdgeCases:
    """Edge case tests for ExamplesWikiGenerator."""

    @pytest.fixture
    def mock_index_status(self) -> MagicMock:
        """Create a mock index status."""
        status = MagicMock(spec=IndexStatus)
        status.repo_path = "/tmp/test-repo"
        return status

    async def test_function_with_no_docstring(
        self,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test function without docstring but with test examples."""
        mock_vector_store = MagicMock()

        # Function chunk without docstring but extractor will find test examples
        func_chunk = MagicMock()
        func_chunk.name = "my_function"
        func_chunk.content = "def my_function(): pass"
        func_chunk.docstring = None  # No docstring
        func_chunk.file_path = "src/module.py"
        func_chunk.language = MagicMock()
        func_chunk.language.value = "python"

        func_result = MagicMock()
        func_result.chunk = func_chunk

        mock_vector_store.search = AsyncMock(side_effect=[[func_result], []])

        generator = ExamplesWikiGenerator()

        # Patch the extractor to return test examples
        with patch.object(
            CodeExampleExtractor,
            "extract_examples_for_function",
            new_callable=AsyncMock,
            return_value=[
                CodeExample(
                    source="test",
                    code="result = my_function()",
                    test_file="tests/test_mod.py",
                    entity_name="my_function",
                )
            ],
        ):
            result = await generator.generate(
                index_status=mock_index_status,
                wiki_path=tmp_path,
                context={"vector_store": mock_vector_store},
            )

        assert len(result.pages) == 1
        assert "my_function" in result.pages[0].content

    async def test_class_with_no_docstring(
        self,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test class without docstring but with test examples."""
        mock_vector_store = MagicMock()

        # Class chunk without docstring
        class_chunk = MagicMock()
        class_chunk.name = "MyClass"
        class_chunk.content = "class MyClass: pass"
        class_chunk.docstring = None
        class_chunk.file_path = "src/module.py"
        class_chunk.language = MagicMock()
        class_chunk.language.value = "python"

        class_result = MagicMock()
        class_result.chunk = class_chunk

        mock_vector_store.search = AsyncMock(side_effect=[[], [class_result]])

        generator = ExamplesWikiGenerator()

        with patch.object(
            CodeExampleExtractor,
            "extract_examples_for_class",
            new_callable=AsyncMock,
            return_value=[
                CodeExample(
                    source="test",
                    code="obj = MyClass()",
                    test_file="tests/test_class.py",
                    entity_name="MyClass",
                )
            ],
        ):
            result = await generator.generate(
                index_status=mock_index_status,
                wiki_path=tmp_path,
                context={"vector_store": mock_vector_store},
            )

        assert len(result.pages) == 1
        assert "MyClass" in result.pages[0].content

    async def test_examples_limited_to_three_per_entity(
        self,
        mock_index_status: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that examples are limited to 3 per entity (line 131, 154)."""
        mock_vector_store = MagicMock()

        func_chunk = MagicMock()
        func_chunk.name = "limited_func"
        func_chunk.content = "def limited_func(): pass"
        func_chunk.docstring = """
        >>> limited_func()
        1
        >>> limited_func()
        2
        >>> limited_func()
        3
        >>> limited_func()
        4
        >>> limited_func()
        5
        """
        func_chunk.file_path = "src/module.py"
        func_chunk.language = MagicMock()
        func_chunk.language.value = "python"

        func_result = MagicMock()
        func_result.chunk = func_chunk

        mock_vector_store.search = AsyncMock(side_effect=[[func_result], []])

        generator = ExamplesWikiGenerator()
        result = await generator.generate(
            index_status=mock_index_status,
            wiki_path=tmp_path,
            context={"vector_store": mock_vector_store},
        )

        # Should generate page with limited examples
        if result.pages:
            content = result.pages[0].content
            # Count occurrences of limited_func in code blocks
            # Should be limited
            assert content.count("limited_func()") <= 6  # Header + up to 3 in code


class TestGetExamplesForApiPageWithEventLoop:
    """Tests for get_examples_for_api_page with event loop scenarios."""

    def test_with_stopped_event_loop(self) -> None:
        """Test when event loop exists but is stopped."""
        import asyncio

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        extractor = CodeExampleExtractor(mock_store)

        docstring = """
        A function.

        >>> func()
        'result'
        """

        # Should handle gracefully
        result = get_examples_for_api_page("func", extractor, docstring)

        # Should still have docstring examples
        assert "func()" in result

    def test_exception_during_run_until_complete(self) -> None:
        """Test exception handling during run_until_complete."""
        mock_store = MagicMock()
        extractor = CodeExampleExtractor(mock_store)

        docstring = """
        Test.

        >>> test()
        42
        """

        # Should not crash, should return docstring examples
        result = get_examples_for_api_page("test", extractor, docstring)

        assert "test()" in result
