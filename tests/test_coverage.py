"""Tests for documentation coverage analysis."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.generators.coverage import (
    CoverageStats,
    FileCoverage,
    _get_coverage_emoji,
    _get_wiki_link,
    _has_meaningful_docstring,
    analyze_file_coverage,
    analyze_project_coverage,
    generate_coverage_page,
)
from local_deepwiki.models import ChunkType, CodeChunk, FileInfo, IndexStatus, Language


class TestCoverageStats:
    """Tests for CoverageStats dataclass."""

    def test_total_entities(self):
        """Test total_entities property."""
        stats = CoverageStats(
            total_classes=5,
            total_functions=10,
            total_methods=15,
        )
        assert stats.total_entities == 30

    def test_documented_entities(self):
        """Test documented_entities property."""
        stats = CoverageStats(
            documented_classes=3,
            documented_functions=8,
            documented_methods=12,
        )
        assert stats.documented_entities == 23

    def test_coverage_percent(self):
        """Test coverage_percent property."""
        stats = CoverageStats(
            total_classes=10,
            documented_classes=10,
            total_functions=10,
            documented_functions=5,
            total_methods=10,
            documented_methods=5,
        )
        # 20/30 = 66.67%
        assert 66.6 < stats.coverage_percent < 66.7

    def test_coverage_percent_empty(self):
        """Test coverage_percent with no entities."""
        stats = CoverageStats()
        assert stats.coverage_percent == 100.0


class TestFileCoverage:
    """Tests for FileCoverage dataclass."""

    def test_creates_with_defaults(self):
        """Test creating FileCoverage with defaults."""
        fc = FileCoverage(file_path="test.py")
        assert fc.file_path == "test.py"
        assert fc.stats.total_entities == 0
        assert fc.undocumented == []


class TestHasMeaningfulDocstring:
    """Tests for _has_meaningful_docstring function."""

    def test_returns_false_for_none(self):
        """Test returns False for None docstring."""
        assert _has_meaningful_docstring(None) is False

    def test_returns_false_for_empty(self):
        """Test returns False for empty string."""
        assert _has_meaningful_docstring("") is False

    def test_returns_false_for_short(self):
        """Test returns False for very short docstrings."""
        assert _has_meaningful_docstring("hi") is False
        assert _has_meaningful_docstring("test") is False

    def test_returns_true_for_meaningful(self):
        """Test returns True for meaningful docstrings."""
        assert _has_meaningful_docstring("This is a proper docstring.") is True
        assert _has_meaningful_docstring("Calculate the sum of two numbers.") is True

    def test_returns_false_for_placeholder(self):
        """Test returns False for placeholder docstrings."""
        assert _has_meaningful_docstring("TODO") is False
        assert _has_meaningful_docstring("FIXME") is False
        assert _has_meaningful_docstring("...") is False
        assert _has_meaningful_docstring("pass") is False

    def test_returns_false_for_padded_placeholder(self):
        """Test returns False for placeholder with whitespace padding."""
        # These are >10 chars but still placeholders after strip/lower
        assert _has_meaningful_docstring("   TODO   ") is False
        assert _has_meaningful_docstring("  FIXME  ") is False
        assert _has_meaningful_docstring("    xxx    ") is False


class TestGetCoverageEmoji:
    """Tests for _get_coverage_emoji function."""

    def test_green_for_high_coverage(self):
        """Test green emoji for 90%+ coverage."""
        assert _get_coverage_emoji(100) == "🟢"
        assert _get_coverage_emoji(95) == "🟢"
        assert _get_coverage_emoji(90) == "🟢"

    def test_yellow_for_good_coverage(self):
        """Test yellow emoji for 70-89% coverage."""
        assert _get_coverage_emoji(89) == "🟡"
        assert _get_coverage_emoji(75) == "🟡"
        assert _get_coverage_emoji(70) == "🟡"

    def test_orange_for_medium_coverage(self):
        """Test orange emoji for 50-69% coverage."""
        assert _get_coverage_emoji(69) == "🟠"
        assert _get_coverage_emoji(55) == "🟠"
        assert _get_coverage_emoji(50) == "🟠"

    def test_red_for_low_coverage(self):
        """Test red emoji for <50% coverage."""
        assert _get_coverage_emoji(49) == "🔴"
        assert _get_coverage_emoji(25) == "🔴"
        assert _get_coverage_emoji(0) == "🔴"


class TestGetWikiLink:
    """Tests for _get_wiki_link function."""

    def test_simple_path(self):
        """Test simple file path conversion."""
        result = _get_wiki_link("src/module.py")
        assert result == "files/src/module.md"

    def test_nested_path(self):
        """Test nested file path conversion."""
        result = _get_wiki_link("src/package/subpackage/module.py")
        assert result == "files/src/package/subpackage/module.md"

    def test_root_file(self):
        """Test root level file path."""
        result = _get_wiki_link("main.py")
        assert result == "files/main.md"


class TestAnalyzeFileCoverage:
    """Tests for analyze_file_coverage function."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    async def test_empty_file(self, mock_vector_store):
        """Test analyzing file with no chunks."""
        result = await analyze_file_coverage("src/empty.py", mock_vector_store)

        assert result.file_path == "src/empty.py"
        assert result.stats.total_entities == 0
        assert result.undocumented == []

    async def test_counts_documented_class(self, mock_vector_store):
        """Test counting a documented class."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="class MyClass: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=10,
                    name="MyClass",
                    docstring="This is a well-documented class.",
                )
            ]
        )

        result = await analyze_file_coverage("src/module.py", mock_vector_store)

        assert result.stats.total_classes == 1
        assert result.stats.documented_classes == 1
        assert result.stats.coverage_percent == 100.0
        assert len(result.undocumented) == 0

    async def test_counts_undocumented_class(self, mock_vector_store):
        """Test counting an undocumented class."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="class MyClass: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=10,
                    name="MyClass",
                    docstring=None,
                )
            ]
        )

        result = await analyze_file_coverage("src/module.py", mock_vector_store)

        assert result.stats.total_classes == 1
        assert result.stats.documented_classes == 0
        assert "class MyClass" in result.undocumented

    async def test_counts_documented_function(self, mock_vector_store):
        """Test counting a documented function."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def my_func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="my_func",
                    docstring="This function does something important.",
                )
            ]
        )

        result = await analyze_file_coverage("src/module.py", mock_vector_store)

        assert result.stats.total_functions == 1
        assert result.stats.documented_functions == 1
        assert len(result.undocumented) == 0

    async def test_counts_undocumented_function(self, mock_vector_store):
        """Test counting an undocumented function."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def my_func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="my_func",
                    docstring="",
                )
            ]
        )

        result = await analyze_file_coverage("src/module.py", mock_vector_store)

        assert result.stats.total_functions == 1
        assert result.stats.documented_functions == 0
        assert "function my_func" in result.undocumented

    async def test_counts_documented_method(self, mock_vector_store):
        """Test counting a documented method."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def my_method(self): pass",
                    chunk_type=ChunkType.METHOD,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="my_method",
                    parent_name="MyClass",
                    docstring="This method performs an action.",
                )
            ]
        )

        result = await analyze_file_coverage("src/module.py", mock_vector_store)

        assert result.stats.total_methods == 1
        assert result.stats.documented_methods == 1
        assert len(result.undocumented) == 0

    async def test_counts_undocumented_method(self, mock_vector_store):
        """Test counting an undocumented method."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def my_method(self): pass",
                    chunk_type=ChunkType.METHOD,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="my_method",
                    parent_name="MyClass",
                    docstring=None,
                )
            ]
        )

        result = await analyze_file_coverage("src/module.py", mock_vector_store)

        assert result.stats.total_methods == 1
        assert result.stats.documented_methods == 0
        assert "method MyClass.my_method" in result.undocumented

    async def test_method_without_parent(self, mock_vector_store):
        """Test method without parent name uses Unknown."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def orphan_method(self): pass",
                    chunk_type=ChunkType.METHOD,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="orphan_method",
                    parent_name=None,
                    docstring=None,
                )
            ]
        )

        result = await analyze_file_coverage("src/module.py", mock_vector_store)

        assert "method Unknown.orphan_method" in result.undocumented

    async def test_chunk_without_name(self, mock_vector_store):
        """Test chunk without name uses Unknown."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="class: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name=None,
                    docstring=None,
                )
            ]
        )

        result = await analyze_file_coverage("src/module.py", mock_vector_store)

        assert "class Unknown" in result.undocumented

    async def test_mixed_coverage(self, mock_vector_store):
        """Test file with mixed documented and undocumented entities."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="class MyClass: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=10,
                    name="MyClass",
                    docstring="A documented class.",
                ),
                CodeChunk(
                    id="chunk2",
                    content="def undoc_func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=12,
                    end_line=15,
                    name="undoc_func",
                    docstring=None,
                ),
                CodeChunk(
                    id="chunk3",
                    content="def doc_func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=17,
                    end_line=20,
                    name="doc_func",
                    docstring="A documented function.",
                ),
            ]
        )

        result = await analyze_file_coverage("src/module.py", mock_vector_store)

        assert result.stats.total_classes == 1
        assert result.stats.documented_classes == 1
        assert result.stats.total_functions == 2
        assert result.stats.documented_functions == 1
        assert result.stats.coverage_percent == pytest.approx(66.67, rel=0.01)
        assert "function undoc_func" in result.undocumented
        assert len(result.undocumented) == 1


class TestAnalyzeProjectCoverage:
    """Tests for analyze_project_coverage function."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def sample_index_status(self):
        """Create a sample index status."""
        return IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=10,
            files=[
                FileInfo(
                    path="src/module1.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/module2.py",
                    hash="def456",
                    size_bytes=500,
                    last_modified=1234567890.0,
                ),
            ],
        )

    async def test_empty_project(self, mock_vector_store, sample_index_status):
        """Test analyzing project with no documentable entities."""
        overall, file_coverages = await analyze_project_coverage(
            sample_index_status, mock_vector_store
        )

        assert overall.total_entities == 0
        assert len(file_coverages) == 2

    async def test_aggregates_stats(self, mock_vector_store, sample_index_status):
        """Test that stats are aggregated across files."""

        async def get_chunks(file_path):
            if file_path == "src/module1.py":
                return [
                    CodeChunk(
                        id="chunk1",
                        content="class A: pass",
                        chunk_type=ChunkType.CLASS,
                        language=Language.PYTHON,
                        file_path=file_path,
                        start_line=1,
                        end_line=5,
                        name="A",
                        docstring="Class A documentation.",
                    )
                ]
            else:
                return [
                    CodeChunk(
                        id="chunk2",
                        content="def func(): pass",
                        chunk_type=ChunkType.FUNCTION,
                        language=Language.PYTHON,
                        file_path=file_path,
                        start_line=1,
                        end_line=5,
                        name="func",
                        docstring="Function documentation.",
                    )
                ]

        mock_vector_store.get_chunks_by_file = AsyncMock(side_effect=get_chunks)

        overall, file_coverages = await analyze_project_coverage(
            sample_index_status, mock_vector_store
        )

        assert overall.total_classes == 1
        assert overall.documented_classes == 1
        assert overall.total_functions == 1
        assert overall.documented_functions == 1
        assert overall.total_entities == 2
        assert overall.documented_entities == 2
        assert overall.coverage_percent == 100.0

    async def test_sorts_by_coverage(self, mock_vector_store, sample_index_status):
        """Test that files are sorted by coverage (lowest first)."""

        async def get_chunks(file_path):
            if file_path == "src/module1.py":
                # 100% coverage
                return [
                    CodeChunk(
                        id="chunk1",
                        content="def func(): pass",
                        chunk_type=ChunkType.FUNCTION,
                        language=Language.PYTHON,
                        file_path=file_path,
                        start_line=1,
                        end_line=5,
                        name="func",
                        docstring="Documented function.",
                    )
                ]
            else:
                # 0% coverage
                return [
                    CodeChunk(
                        id="chunk2",
                        content="def undoc(): pass",
                        chunk_type=ChunkType.FUNCTION,
                        language=Language.PYTHON,
                        file_path=file_path,
                        start_line=1,
                        end_line=5,
                        name="undoc",
                        docstring=None,
                    )
                ]

        mock_vector_store.get_chunks_by_file = AsyncMock(side_effect=get_chunks)

        overall, file_coverages = await analyze_project_coverage(
            sample_index_status, mock_vector_store
        )

        # Lowest coverage should be first
        assert file_coverages[0].file_path == "src/module2.py"
        assert file_coverages[0].stats.coverage_percent == 0.0
        assert file_coverages[1].file_path == "src/module1.py"
        assert file_coverages[1].stats.coverage_percent == 100.0


class TestGenerateCoveragePage:
    """Tests for generate_coverage_page function."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def sample_index_status(self):
        """Create a sample index status."""
        return IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            files=[
                FileInfo(
                    path="src/module.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
            ],
        )

    async def test_returns_none_for_empty_project(
        self, mock_vector_store, sample_index_status
    ):
        """Test returns None when no documentable entities exist."""
        result = await generate_coverage_page(sample_index_status, mock_vector_store)
        assert result is None

    async def test_generates_page_header(self, mock_vector_store, sample_index_status):
        """Test generates page with proper header."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="func",
                    docstring="A documented function.",
                )
            ]
        )

        result = await generate_coverage_page(sample_index_status, mock_vector_store)

        assert result is not None
        assert "# Documentation Coverage" in result
        assert "This report shows the documentation coverage" in result

    async def test_includes_summary_section(
        self, mock_vector_store, sample_index_status
    ):
        """Test includes summary with overall coverage."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="func",
                    docstring="Documented function.",
                )
            ]
        )

        result = await generate_coverage_page(sample_index_status, mock_vector_store)

        assert "## Summary" in result
        assert "Overall Coverage: 100.0%" in result
        assert "🟢" in result  # High coverage emoji

    async def test_includes_type_breakdown(
        self, mock_vector_store, sample_index_status
    ):
        """Test includes breakdown by entity type."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="class MyClass: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=10,
                    name="MyClass",
                    docstring="A class.",
                ),
                CodeChunk(
                    id="chunk2",
                    content="def func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=12,
                    end_line=15,
                    name="func",
                    docstring="A function.",
                ),
                CodeChunk(
                    id="chunk3",
                    content="def method(self): pass",
                    chunk_type=ChunkType.METHOD,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=17,
                    end_line=20,
                    name="method",
                    parent_name="MyClass",
                    docstring="A method.",
                ),
            ]
        )

        result = await generate_coverage_page(sample_index_status, mock_vector_store)

        assert "### By Type" in result
        assert "| Classes |" in result
        assert "| Functions |" in result
        assert "| Methods |" in result

    async def test_includes_file_coverage_table(
        self, mock_vector_store, sample_index_status
    ):
        """Test includes coverage by file table."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="func",
                    docstring="Documented.",
                )
            ]
        )

        result = await generate_coverage_page(sample_index_status, mock_vector_store)

        assert "## Coverage by File" in result
        assert "| File | Documented | Total | Coverage |" in result
        assert "module.py" in result

    async def test_includes_legend(self, mock_vector_store, sample_index_status):
        """Test includes legend at the end."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="func",
                    docstring="Documented.",
                )
            ]
        )

        result = await generate_coverage_page(sample_index_status, mock_vector_store)

        assert "**Legend:**" in result
        assert "🟢 ≥90%" in result
        assert "🟡 ≥70%" in result
        assert "🟠 ≥50%" in result
        assert "🔴 <50%" in result

    async def test_shows_files_needing_attention(
        self, mock_vector_store, sample_index_status
    ):
        """Test shows files with low coverage needing attention."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def undoc1(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="undoc1",
                    docstring=None,
                ),
                CodeChunk(
                    id="chunk2",
                    content="def undoc2(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=7,
                    end_line=10,
                    name="undoc2",
                    docstring=None,
                ),
            ]
        )

        result = await generate_coverage_page(sample_index_status, mock_vector_store)

        assert "## Files Needing Attention" in result
        assert "Files with less than 50% documentation coverage:" in result
        assert "module.py" in result
        assert "Undocumented:" in result
        assert "`function undoc1`" in result
        assert "`function undoc2`" in result

    async def test_skips_empty_files_in_table(self, mock_vector_store):
        """Test skips files with no documentable entities in table."""
        index_status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=5,
            files=[
                FileInfo(
                    path="src/empty.py",
                    hash="abc123",
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/module.py",
                    hash="def456",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
            ],
        )

        async def get_chunks(file_path):
            if file_path == "src/module.py":
                return [
                    CodeChunk(
                        id="chunk1",
                        content="def func(): pass",
                        chunk_type=ChunkType.FUNCTION,
                        language=Language.PYTHON,
                        file_path=file_path,
                        start_line=1,
                        end_line=5,
                        name="func",
                        docstring="Documented.",
                    )
                ]
            return []

        mock_vector_store.get_chunks_by_file = AsyncMock(side_effect=get_chunks)

        result = await generate_coverage_page(index_status, mock_vector_store)

        # Only module.py should appear in the coverage table, not empty.py
        assert "module.py" in result
        # empty.py might appear but should not have coverage stats row
        lines = result.split("\n")
        file_table_lines = [l for l in lines if "empty.py" in l and "|" in l]
        assert len(file_table_lines) == 0

    async def test_limits_undocumented_list(self, mock_vector_store, sample_index_status):
        """Test limits undocumented items to 20 with overflow message."""
        # Create 25 undocumented functions
        chunks = [
            CodeChunk(
                id=f"chunk{i}",
                content=f"def func{i}(): pass",
                chunk_type=ChunkType.FUNCTION,
                language=Language.PYTHON,
                file_path="src/module.py",
                start_line=i,
                end_line=i + 2,
                name=f"func{i}",
                docstring=None,
            )
            for i in range(25)
        ]
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=chunks)

        result = await generate_coverage_page(sample_index_status, mock_vector_store)

        assert "... and 5 more" in result

    async def test_coverage_emoji_in_file_table(
        self, mock_vector_store, sample_index_status
    ):
        """Test correct emoji appears in file coverage table."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="func",
                    docstring="Documented function with good docs.",
                )
            ]
        )

        result = await generate_coverage_page(sample_index_status, mock_vector_store)

        # 100% coverage should show green emoji in file table
        assert "🟢" in result
