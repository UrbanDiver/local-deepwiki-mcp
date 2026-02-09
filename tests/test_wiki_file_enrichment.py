"""Tests for source details, inline source injection, entity heading extraction, blame, and enrichments."""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.generators.wiki_files import (
    _create_source_details,
    _generate_files_index,
    _inject_inline_source_code,
    generate_file_docs,
    generate_single_file_doc,
)
from local_deepwiki.models import (
    ChunkType,
    CodeChunk,
    FileInfo,
    IndexStatus,
    Language,
    SearchResult,
    WikiPage,
)


def make_index_status(
    repo_path: str,
    total_files: int = 0,
    total_chunks: int = 0,
    languages: dict | None = None,
    files: list | None = None,
) -> IndexStatus:
    """Helper to create IndexStatus with required fields."""
    return IndexStatus(
        repo_path=repo_path,
        indexed_at=time.time(),
        total_files=total_files,
        total_chunks=total_chunks,
        languages=languages or {},
        files=files or [],
    )


def make_file_info(
    path: str,
    hash: str = "abc123",
    language: Language | None = Language.PYTHON,
    chunk_count: int = 5,
) -> FileInfo:
    """Helper to create FileInfo with required fields."""
    return FileInfo(
        path=path,
        hash=hash,
        language=language,
        size_bytes=100,
        last_modified=time.time(),
        chunk_count=chunk_count,
    )


def make_code_chunk(
    file_path: str = "src/test.py",
    name: str = "TestClass",
    chunk_type: ChunkType = ChunkType.CLASS,
    content: str = "class TestClass:\n    pass",
    language: Language = Language.PYTHON,
    start_line: int = 1,
    end_line: int = 10,
    parent_name: str | None = None,
) -> CodeChunk:
    """Helper to create CodeChunk with sensible defaults."""
    return CodeChunk(
        id=f"{file_path}:{name}",
        file_path=file_path,
        language=language,
        chunk_type=chunk_type,
        name=name,
        content=content,
        start_line=start_line,
        end_line=end_line,
        parent_name=parent_name,
    )


def make_search_result(
    chunk: CodeChunk | None = None,
    score: float = 0.9,
) -> SearchResult:
    """Helper to create SearchResult."""
    if chunk is None:
        chunk = make_code_chunk()
    return SearchResult(
        chunk=chunk,
        score=score,
        highlights=[],
    )


class TestCreateSourceDetails:
    """Tests for _create_source_details function."""

    def test_creates_details_block(self):
        """Test creates a properly formatted details block."""
        chunk = make_code_chunk(
            name="my_func",
            chunk_type=ChunkType.FUNCTION,
            content="def my_func():\n    pass",
            start_line=10,
            end_line=12,
        )

        result = _create_source_details(chunk, "python")

        assert "<details>" in result
        assert "</details>" in result
        assert "View Source (lines 10-12)" in result
        assert "```python" in result
        assert "def my_func():" in result

    def test_uses_correct_syntax_highlighting(self):
        """Test uses the provided syntax language."""
        chunk = make_code_chunk(
            name="main",
            chunk_type=ChunkType.FUNCTION,
            content="func main() {}",
            language=Language.GO,
        )

        result = _create_source_details(chunk, "go")

        assert "```go" in result


class TestInjectInlineSourceCode:
    """Tests for _inject_inline_source_code function."""

    def test_injects_source_after_api_reference_function(self):
        """Test injects source code after function in API Reference."""
        content = """## API Reference

### Functions

#### `my_func`

```python
def my_func() -> None
```

Does something.

**Returns:** `None`

## Other Section
"""
        chunk = make_code_chunk(
            name="my_func",
            chunk_type=ChunkType.FUNCTION,
            content="def my_func():\n    pass",
            start_line=10,
            end_line=12,
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        # Source should appear after Returns
        assert "View Source (lines 10-12)" in result
        assert "<details>" in result
        # Source should be before "Other Section"
        source_pos = result.find("View Source")
        other_pos = result.find("## Other Section")
        assert source_pos < other_pos

    def test_handles_multiple_functions(self):
        """Test handles multiple functions in API Reference."""
        content = """## API Reference

### Functions

#### `func_a`

```python
def func_a() -> None
```

First function.

**Returns:** `None`

#### `func_b`

```python
def func_b() -> str
```

Second function.

**Returns:** `str`
"""
        chunks = [
            make_code_chunk(
                name="func_a",
                chunk_type=ChunkType.FUNCTION,
                content="def func_a():\n    pass",
                start_line=1,
                end_line=3,
            ),
            make_code_chunk(
                name="func_b",
                chunk_type=ChunkType.FUNCTION,
                content="def func_b():\n    return 'hello'",
                start_line=5,
                end_line=7,
            ),
        ]

        result = _inject_inline_source_code(content, chunks, "python")

        # Both functions should have source
        assert "View Source (lines 1-3)" in result
        assert "View Source (lines 5-7)" in result

    def test_adds_unmatched_chunks_to_additional_section(self):
        """Test adds unmatched chunks to Additional Source Code section."""
        content = """## API Reference

#### `unknown_func`

Some description.
"""
        chunk = make_code_chunk(
            name="other_func",
            chunk_type=ChunkType.FUNCTION,
            content="def other_func():\n    pass",
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        # Original content should be there
        assert "#### `unknown_func`" in result
        # Unmatched chunk should appear in Additional Source Code section
        assert "## Additional Source Code" in result
        assert "#### `other_func`" in result
        assert "View Source" in result

    def test_returns_unchanged_for_empty_chunks(self):
        """Test returns unchanged content for empty chunk list."""
        content = "## Some content\n\nMore content."

        result = _inject_inline_source_code(content, [], "python")

        assert result == content

    def test_skips_non_code_chunks(self):
        """Test skips import and module chunks."""
        content = """#### `imports`

Import statement.
"""
        chunk = make_code_chunk(
            name="imports",
            chunk_type=ChunkType.IMPORT,
            content="import os",
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        assert "View Source" not in result

    def test_handles_class_headings(self):
        """Test handles class headings in API Reference."""
        content = """## API Reference

### Classes

#### `MyClass`

```python
class MyClass
```

A test class.

**Returns:** `MyClass`
"""
        chunk = make_code_chunk(
            name="MyClass",
            chunk_type=ChunkType.CLASS,
            content="class MyClass:\n    pass",
            start_line=1,
            end_line=3,
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        assert "View Source (lines 1-3)" in result

    def test_handles_heading_with_signature(self):
        """Test handles headings with full function signature."""
        content = """## API Reference

#### `__init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434")`

Initialize the provider.

**Returns:** `None`
"""
        chunk = make_code_chunk(
            name="__init__",
            chunk_type=ChunkType.FUNCTION,
            content="def __init__(self, model, base_url):\n    self.model = model",
            start_line=10,
            end_line=12,
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        assert "View Source (lines 10-12)" in result

    def test_handles_class_prefix_in_heading(self):
        """Test handles headings with 'class ' prefix."""
        content = """## API Reference

### `class OllamaProvider`

A provider for Ollama.

**Returns:** `OllamaProvider`
"""
        chunk = make_code_chunk(
            name="OllamaProvider",
            chunk_type=ChunkType.CLASS,
            content="class OllamaProvider:\n    pass",
            start_line=1,
            end_line=5,
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        assert "View Source (lines 1-5)" in result

    def test_injects_source_before_next_heading_no_returns(self):
        """Test injects source when hitting next heading without Returns line."""
        content = """## API Reference

#### `__init__`

```python
def __init__(base_url: str)
```

| Parameter | Type |
|-----------|------|
| base_url | str |

### class `NextClass`

Another class.
"""
        chunk = make_code_chunk(
            name="__init__",
            chunk_type=ChunkType.FUNCTION,
            content="def __init__(self, base_url):\n    self.url = base_url",
            start_line=5,
            end_line=7,
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        # Source should be injected before NextClass heading
        assert "View Source (lines 5-7)" in result
        # The next heading should still be present
        assert "### class `NextClass`" in result
        # Source should come before NextClass
        source_pos = result.find("View Source")
        next_class_pos = result.find("### class `NextClass`")
        assert source_pos < next_class_pos

    def test_handles_duplicate_method_names_with_qualified_lookup(self):
        """Test uses qualified names to match methods in different classes."""
        content = """## API Reference

### class `ClassA`

First class.

#### `__init__`

Initialize ClassA.

### class `ClassB`

Second class.

#### `__init__`

Initialize ClassB.
"""
        chunk_a = make_code_chunk(
            name="__init__",
            chunk_type=ChunkType.METHOD,
            content="def __init__(self):\n    self.a = 1",
            start_line=10,
            end_line=12,
            parent_name="ClassA",
        )
        chunk_b = make_code_chunk(
            name="__init__",
            chunk_type=ChunkType.METHOD,
            content="def __init__(self):\n    self.b = 2",
            start_line=20,
            end_line=22,
            parent_name="ClassB",
        )

        result = _inject_inline_source_code(content, [chunk_a, chunk_b], "python")

        # Both should have different source blocks
        assert "View Source (lines 10-12)" in result
        assert "View Source (lines 20-22)" in result
        # ClassA's __init__ should get ClassA's source
        class_a_pos = result.find("### class `ClassA`")
        class_b_pos = result.find("### class `ClassB`")
        source_a_pos = result.find("View Source (lines 10-12)")
        source_b_pos = result.find("View Source (lines 20-22)")
        assert class_a_pos < source_a_pos < class_b_pos < source_b_pos

    def test_falls_back_to_class_source_for_unmatched_method(self):
        """Test uses class source when method chunk doesn't exist."""
        content = """## API Reference

### class `SimpleClass`

A simple class.

#### `__init__`

Initialize the class.

#### `do_something`

Do something.
"""
        # Only class chunk exists, no separate method chunks
        class_chunk = make_code_chunk(
            name="SimpleClass",
            chunk_type=ChunkType.CLASS,
            content="class SimpleClass:\n    def __init__(self):\n        pass\n    def do_something(self):\n        pass",
            start_line=1,
            end_line=5,
        )

        result = _inject_inline_source_code(content, [class_chunk], "python")

        # Class heading should get class source
        assert "View Source (lines 1-5)" in result
        # Method headings should also get class source as fallback
        # Count occurrences - should be 3 (class + 2 methods)
        assert result.count("View Source (lines 1-5)") == 3

    def test_includes_github_link_when_repo_info_provided(self):
        """Test includes GitHub link when repo_info is provided."""
        from local_deepwiki.core.git_utils import GitRepoInfo

        content = """## API Reference

#### `my_func`

A function.

**Returns:** `None`
"""
        chunk = make_code_chunk(
            name="my_func",
            chunk_type=ChunkType.FUNCTION,
            content="def my_func():\n    pass",
            start_line=10,
            end_line=12,
            file_path="src/example.py",
        )

        repo_info = GitRepoInfo(
            remote_url="https://github.com/owner/repo",
            host="github.com",
            owner="owner",
            repo="repo",
            default_branch="main",
        )

        result = _inject_inline_source_code(content, [chunk], "python", repo_info)

        # Should include GitHub link
        assert "GitHub" in result
        assert "https://github.com/owner/repo/blob/main/src/example.py#L10-L12" in result


class TestExtractEntityFromHeading:
    """Tests for _extract_entity_from_heading function."""

    def test_returns_none_for_heading_without_backticks(self):
        """Test returns None when heading has no backticks."""
        from local_deepwiki.generators.wiki_files import _extract_entity_from_heading

        entity, is_class = _extract_entity_from_heading("### No backticks here")

        assert entity is None
        assert is_class is False

    def test_returns_none_for_incomplete_backticks(self):
        """Test returns None when heading has only opening backtick."""
        from local_deepwiki.generators.wiki_files import _extract_entity_from_heading

        entity, is_class = _extract_entity_from_heading("#### `incomplete")

        assert entity is None
        assert is_class is False

    def test_returns_none_for_empty_backticks(self):
        """Test returns None for empty backticks ``."""
        from local_deepwiki.generators.wiki_files import _extract_entity_from_heading

        entity, is_class = _extract_entity_from_heading("#### ``")

        assert entity is None
        assert is_class is False


class TestGenerateBlameSectionCoverage:
    """Tests for _generate_blame_section to cover uncovered lines."""

    def test_returns_none_for_empty_chunks(self):
        """Test returns None when chunks list is empty."""
        from local_deepwiki.generators.wiki_files import _generate_blame_section

        result = _generate_blame_section(
            repo_path=Path("/tmp/repo"),
            file_path="src/test.py",
            chunks=[],
        )

        assert result is None

    def test_returns_none_for_chunks_without_code_entities(self):
        """Test returns None when chunks have no function/class/method types."""
        from local_deepwiki.generators.wiki_files import _generate_blame_section

        # Create chunks that are imports or modules (not function/class/method)
        chunk = make_code_chunk(
            name="imports",
            chunk_type=ChunkType.IMPORT,
            content="import os",
        )

        result = _generate_blame_section(
            repo_path=Path("/tmp/repo"),
            file_path="src/test.py",
            chunks=[chunk],
        )

        assert result is None

    def test_generates_blame_section_with_entities(self, tmp_path):
        """Test generates blame section when blame info is available."""
        from datetime import datetime
        from local_deepwiki.generators.wiki_files import _generate_blame_section
        from local_deepwiki.core.git_utils import EntityBlameInfo

        chunks = [
            make_code_chunk(
                name="my_func",
                chunk_type=ChunkType.FUNCTION,
                content="def my_func():\n    pass",
                start_line=1,
                end_line=3,
            ),
            make_code_chunk(
                name="MyClass",
                chunk_type=ChunkType.CLASS,
                content="class MyClass:\n    pass",
                start_line=5,
                end_line=8,
            ),
        ]

        mock_blame_info = [
            EntityBlameInfo(
                entity_name="my_func",
                entity_type="function",
                start_line=1,
                end_line=3,
                last_modified_by="John Doe",
                last_modified_date=datetime(2024, 1, 15),
                commit_hash="abc1234567890",
                commit_summary="Add my_func",
            ),
            EntityBlameInfo(
                entity_name="MyClass",
                entity_type="class",
                start_line=5,
                end_line=8,
                last_modified_by="Jane Smith",
                last_modified_date=datetime(2024, 2, 20),
                commit_hash="def5678901234",
                commit_summary="Add MyClass implementation",
            ),
        ]

        with patch("local_deepwiki.generators.wiki_files.get_file_entity_blame") as mock_blame:
            mock_blame.return_value = mock_blame_info

            result = _generate_blame_section(
                repo_path=tmp_path,
                file_path="src/test.py",
                chunks=chunks,
            )

        assert result is not None
        assert "## Last Modified" in result
        assert "| Entity | Type | Author | Date | Commit |" in result
        assert "`my_func`" in result
        assert "`MyClass`" in result
        assert "John Doe" in result
        assert "Jane Smith" in result
        assert "`abc1234`" in result
        assert "`def5678`" in result
        assert "Add my_func" in result

    def test_truncates_long_author_names(self, tmp_path):
        """Test truncates author names longer than 20 characters."""
        from datetime import datetime
        from local_deepwiki.generators.wiki_files import _generate_blame_section
        from local_deepwiki.core.git_utils import EntityBlameInfo

        chunks = [
            make_code_chunk(
                name="func",
                chunk_type=ChunkType.FUNCTION,
                content="def func(): pass",
                start_line=1,
                end_line=2,
            ),
        ]

        mock_blame_info = [
            EntityBlameInfo(
                entity_name="func",
                entity_type="function",
                start_line=1,
                end_line=2,
                last_modified_by="Very Long Author Name That Exceeds Twenty Characters",
                last_modified_date=datetime(2024, 1, 1),
                commit_hash="abc1234567890",
                commit_summary="Short",
            ),
        ]

        with patch("local_deepwiki.generators.wiki_files.get_file_entity_blame") as mock_blame:
            mock_blame.return_value = mock_blame_info

            result = _generate_blame_section(
                repo_path=tmp_path,
                file_path="src/test.py",
                chunks=chunks,
            )

        assert result is not None
        # Author name should be truncated to 17 chars + "..."
        assert "Very Long Author ..." in result

    def test_truncates_long_commit_summary(self, tmp_path):
        """Test truncates commit summaries longer than 30 characters."""
        from datetime import datetime
        from local_deepwiki.generators.wiki_files import _generate_blame_section
        from local_deepwiki.core.git_utils import EntityBlameInfo

        chunks = [
            make_code_chunk(
                name="func",
                chunk_type=ChunkType.FUNCTION,
                content="def func(): pass",
                start_line=1,
                end_line=2,
            ),
        ]

        mock_blame_info = [
            EntityBlameInfo(
                entity_name="func",
                entity_type="function",
                start_line=1,
                end_line=2,
                last_modified_by="Author",
                last_modified_date=datetime(2024, 1, 1),
                commit_hash="abc1234567890",
                commit_summary="This is a very long commit summary that should be truncated",
            ),
        ]

        with patch("local_deepwiki.generators.wiki_files.get_file_entity_blame") as mock_blame:
            mock_blame.return_value = mock_blame_info

            result = _generate_blame_section(
                repo_path=tmp_path,
                file_path="src/test.py",
                chunks=chunks,
            )

        assert result is not None
        # Summary should be truncated to 27 chars + "..."
        assert "This is a very long commit ..." in result

    def test_returns_none_when_no_blame_info(self, tmp_path):
        """Test returns None when get_file_entity_blame returns empty list."""
        from local_deepwiki.generators.wiki_files import _generate_blame_section

        chunks = [
            make_code_chunk(
                name="func",
                chunk_type=ChunkType.FUNCTION,
                content="def func(): pass",
                start_line=1,
                end_line=2,
            ),
        ]

        with patch("local_deepwiki.generators.wiki_files.get_file_entity_blame") as mock_blame:
            mock_blame.return_value = []

            result = _generate_blame_section(
                repo_path=tmp_path,
                file_path="src/test.py",
                chunks=chunks,
            )

        assert result is None


class TestGenerateFileEnrichmentsUsedBy:
    """Tests for 'Used By' section in _generate_file_enrichments."""

    def test_adds_used_by_section_when_callers_exist(self, tmp_path):
        """Test adds Used By section when file has callers."""
        from local_deepwiki.generators.wiki_files import _generate_file_enrichments

        # Create a real file
        (tmp_path / "main.py").write_text("def main(): pass")

        chunks = [
            make_code_chunk(
                name="main",
                chunk_type=ChunkType.FUNCTION,
                content="def main(): pass",
                start_line=1,
                end_line=2,
            ),
        ]

        with (
            patch("local_deepwiki.generators.wiki_files.get_file_api_docs") as mock_api,
            patch("local_deepwiki.generators.wiki_files.generate_class_diagram") as mock_diagram,
            patch("local_deepwiki.generators.wiki_files.get_file_call_graph") as mock_graph,
            patch("local_deepwiki.generators.wiki_files.get_file_callers") as mock_callers,
            patch("local_deepwiki.generators.wiki_files.get_file_examples") as mock_examples,
            patch("local_deepwiki.generators.wiki_files._generate_blame_section") as mock_blame,
        ):
            mock_api.return_value = ""
            mock_diagram.return_value = ""
            mock_graph.return_value = ""
            mock_callers.return_value = {
                "main": ["app.run", "cli.execute"],
                "helper": ["utils.format"],
            }
            mock_examples.return_value = ""
            mock_blame.return_value = None

            result = _generate_file_enrichments(
                content="## Overview\n\nTest content.",
                abs_file_path=tmp_path / "main.py",
                repo_path=tmp_path,
                file_path="main.py",
                all_file_chunks=chunks,
            )

        assert "## Used By" in result
        assert "Functions and methods in this file and their callers:" in result
        assert "**`helper`**: called by `utils.format`" in result
        assert "**`main`**: called by `app.run`, `cli.execute`" in result

    def test_skips_used_by_when_no_callers(self, tmp_path):
        """Test does not add Used By when callers_map is empty."""
        from local_deepwiki.generators.wiki_files import _generate_file_enrichments

        (tmp_path / "main.py").write_text("def main(): pass")

        chunks = [
            make_code_chunk(
                name="main",
                chunk_type=ChunkType.FUNCTION,
                content="def main(): pass",
            ),
        ]

        with (
            patch("local_deepwiki.generators.wiki_files.get_file_api_docs") as mock_api,
            patch("local_deepwiki.generators.wiki_files.generate_class_diagram") as mock_diagram,
            patch("local_deepwiki.generators.wiki_files.get_file_call_graph") as mock_graph,
            patch("local_deepwiki.generators.wiki_files.get_file_callers") as mock_callers,
            patch("local_deepwiki.generators.wiki_files.get_file_examples") as mock_examples,
            patch("local_deepwiki.generators.wiki_files._generate_blame_section") as mock_blame,
        ):
            mock_api.return_value = ""
            mock_diagram.return_value = ""
            mock_graph.return_value = ""
            mock_callers.return_value = {}  # No callers
            mock_examples.return_value = ""
            mock_blame.return_value = None

            result = _generate_file_enrichments(
                content="## Overview",
                abs_file_path=tmp_path / "main.py",
                repo_path=tmp_path,
                file_path="main.py",
                all_file_chunks=chunks,
            )

        assert "## Used By" not in result

    def test_skips_used_by_when_callers_are_empty_lists(self, tmp_path):
        """Test does not add Used By when all caller lists are empty."""
        from local_deepwiki.generators.wiki_files import _generate_file_enrichments

        (tmp_path / "main.py").write_text("def main(): pass")

        chunks = [
            make_code_chunk(
                name="main",
                chunk_type=ChunkType.FUNCTION,
                content="def main(): pass",
            ),
        ]

        with (
            patch("local_deepwiki.generators.wiki_files.get_file_api_docs") as mock_api,
            patch("local_deepwiki.generators.wiki_files.generate_class_diagram") as mock_diagram,
            patch("local_deepwiki.generators.wiki_files.get_file_call_graph") as mock_graph,
            patch("local_deepwiki.generators.wiki_files.get_file_callers") as mock_callers,
            patch("local_deepwiki.generators.wiki_files.get_file_examples") as mock_examples,
            patch("local_deepwiki.generators.wiki_files._generate_blame_section") as mock_blame,
        ):
            mock_api.return_value = ""
            mock_diagram.return_value = ""
            mock_graph.return_value = ""
            # Has entries but all empty lists
            mock_callers.return_value = {"main": [], "helper": []}
            mock_examples.return_value = ""
            mock_blame.return_value = None

            result = _generate_file_enrichments(
                content="## Overview",
                abs_file_path=tmp_path / "main.py",
                repo_path=tmp_path,
                file_path="main.py",
                all_file_chunks=chunks,
            )

        # Should not include Used By when all caller lists are empty
        assert "## Used By" not in result

    def test_adds_blame_section_when_available(self, tmp_path):
        """Test adds blame section when _generate_blame_section returns content."""
        from local_deepwiki.generators.wiki_files import _generate_file_enrichments

        (tmp_path / "main.py").write_text("def main(): pass")

        chunks = [
            make_code_chunk(
                name="main",
                chunk_type=ChunkType.FUNCTION,
                content="def main(): pass",
            ),
        ]

        blame_content = """## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `main` | function | John | 2024-01-15 | `abc1234` |"""

        with (
            patch("local_deepwiki.generators.wiki_files.get_file_api_docs") as mock_api,
            patch("local_deepwiki.generators.wiki_files.generate_class_diagram") as mock_diagram,
            patch("local_deepwiki.generators.wiki_files.get_file_call_graph") as mock_graph,
            patch("local_deepwiki.generators.wiki_files.get_file_callers") as mock_callers,
            patch("local_deepwiki.generators.wiki_files.get_file_examples") as mock_examples,
            patch("local_deepwiki.generators.wiki_files._generate_blame_section") as mock_blame,
        ):
            mock_api.return_value = ""
            mock_diagram.return_value = ""
            mock_graph.return_value = ""
            mock_callers.return_value = {}
            mock_examples.return_value = ""
            mock_blame.return_value = blame_content

            result = _generate_file_enrichments(
                content="## Overview",
                abs_file_path=tmp_path / "main.py",
                repo_path=tmp_path,
                file_path="main.py",
                all_file_chunks=chunks,
            )

        assert "## Last Modified" in result
        assert "`main`" in result
