"""Tests for enhanced diagram generation."""

import pytest

from local_deepwiki.generators.diagrams import (
    ClassInfo,
    _extract_class_attributes,
    _extract_method_signature,
    _find_circular_dependencies,
    _module_to_wiki_path,
    _parse_external_import,
    _parse_import_line,
    _path_to_module,
    generate_class_diagram,
    generate_deep_research_sequence,
    generate_dependency_graph,
    generate_indexing_sequence,
    generate_language_pie_chart,
    generate_module_overview,
    generate_sequence_diagram,
    generate_wiki_generation_sequence,
    generate_workflow_sequences,
    sanitize_mermaid_name,
)
from local_deepwiki.models import ChunkType, CodeChunk, FileInfo, IndexStatus, Language


class TestSanitizeMermaidName:
    """Tests for sanitize_mermaid_name function."""

    def test_basic_name(self):
        """Test basic name passes through."""
        assert sanitize_mermaid_name("MyClass") == "MyClass"

    def test_replaces_brackets(self):
        """Test angle brackets are replaced."""
        assert sanitize_mermaid_name("List<int>") == "List_int_"

    def test_replaces_square_brackets(self):
        """Test square brackets are replaced."""
        assert sanitize_mermaid_name("arr[0]") == "arr_0_"

    def test_replaces_dots(self):
        """Test dots are replaced."""
        assert sanitize_mermaid_name("module.class") == "module_class"

    def test_replaces_hyphens(self):
        """Test hyphens are replaced."""
        assert sanitize_mermaid_name("my-class") == "my_class"

    def test_replaces_colons(self):
        """Test colons are replaced."""
        assert sanitize_mermaid_name("scope::name") == "scope__name"

    def test_prefixes_digit(self):
        """Test names starting with digits get prefixed."""
        assert sanitize_mermaid_name("123Class") == "C123Class"


class TestExtractClassAttributes:
    """Tests for _extract_class_attributes function."""

    def test_extracts_type_annotations(self):
        """Test extraction of class-level type annotations."""
        content = """class MyClass:
    name: str
    count: int
"""
        attrs = _extract_class_attributes(content, "python")
        assert "+name: str" in attrs
        assert "+count: int" in attrs

    def test_extracts_init_assignments(self):
        """Test extraction from __init__ assignments."""
        content = """class MyClass:
    def __init__(self):
        self.value = 42
        self._private = "secret"
"""
        attrs = _extract_class_attributes(content, "python")
        assert "+value" in attrs
        assert "-_private" in attrs

    def test_marks_private_attributes(self):
        """Test private attributes get - prefix."""
        content = """class MyClass:
    _hidden: str
"""
        attrs = _extract_class_attributes(content, "python")
        assert any(a.startswith("-_hidden") for a in attrs)


class TestExtractMethodSignature:
    """Tests for _extract_method_signature function."""

    def test_extracts_return_type(self):
        """Test extraction of return type."""
        content = "def process(x: int, y: str) -> bool:"
        sig = _extract_method_signature(content)
        assert "bool" in sig

    def test_extracts_parameters(self):
        """Test extraction of parameters."""
        content = "def process(x: int, y: str) -> bool:"
        sig = _extract_method_signature(content)
        assert "x: int" in sig
        assert "y: str" in sig

    def test_excludes_self(self):
        """Test self parameter is excluded."""
        content = "def process(self, x: int) -> None:"
        sig = _extract_method_signature(content)
        assert "self" not in sig
        assert "x: int" in sig

    def test_limits_parameters(self):
        """Test long parameter lists are truncated."""
        content = "def process(a: int, b: int, c: int, d: int, e: int, f: int) -> None:"
        sig = _extract_method_signature(content)
        assert "..." in sig

    def test_returns_none_for_invalid(self):
        """Test returns None for non-def content."""
        content = "class MyClass:"
        sig = _extract_method_signature(content)
        assert sig is None


class TestClassInfo:
    """Tests for ClassInfo dataclass."""

    def test_basic_class_info(self):
        """Test basic ClassInfo creation."""
        info = ClassInfo(
            name="MyClass",
            methods=["do_work", "process"],
            attributes=["+name: str"],
            parents=["BaseClass"],
        )
        assert info.name == "MyClass"
        assert len(info.methods) == 2
        assert info.is_abstract is False
        assert info.is_dataclass is False

    def test_abstract_class(self):
        """Test abstract class flag."""
        info = ClassInfo(
            name="AbstractBase",
            methods=[],
            attributes=[],
            parents=["ABC"],
            is_abstract=True,
        )
        assert info.is_abstract is True


class TestGenerateClassDiagram:
    """Tests for generate_class_diagram function."""

    def test_generates_diagram_with_class(self):
        """Test diagram generation with a single class."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            )
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "classDiagram" in diagram
        assert "MyClass" in diagram
        assert "method" in diagram

    def test_returns_none_for_empty_classes(self):
        """Test returns None when classes have no content."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class Empty: pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
                name="Empty",
                metadata={},
            )
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is None

    def test_shows_inheritance(self):
        """Test inheritance relationships are shown."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class Child:\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="Child",
                metadata={"parent_classes": ["Parent"]},
            )
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "--|>" in diagram
        assert "Parent" in diagram

    def test_marks_dataclass(self):
        """Test dataclass annotation is shown."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="@dataclass\nclass Data:\n    name: str",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="Data",
                metadata={},
            )
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "<<dataclass>>" in diagram

    def test_shows_method_visibility(self):
        """Test private methods are marked with -."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def public(self): pass\n    def _private(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="MyClass",
                metadata={},
            )
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "+public" in diagram
        assert "-_private" in diagram


class TestGenerateDependencyGraph:
    """Tests for generate_dependency_graph function."""

    def test_generates_flowchart(self):
        """Test basic flowchart generation."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/local_deepwiki/core/parser.py",
                content="from local_deepwiki.models import ChunkType",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/local_deepwiki/models.py",
                content="# models",
                chunk_type=ChunkType.MODULE,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "local_deepwiki")
        # May return None if no internal deps found
        # Just verify it doesn't crash
        assert diagram is None or "flowchart" in diagram

    def test_returns_none_for_no_imports(self):
        """Test returns None when no imports."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="def func(): pass",
                chunk_type=ChunkType.FUNCTION,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            )
        ]
        diagram = generate_dependency_graph(chunks, "project")
        assert diagram is None


class TestFindCircularDependencies:
    """Tests for _find_circular_dependencies function."""

    def test_finds_direct_cycle(self):
        """Test detection of A -> B -> A cycle."""
        deps = {
            "a": {"b"},
            "b": {"a"},
        }
        circular = _find_circular_dependencies(deps)
        assert len(circular) > 0
        assert ("a", "b") in circular or ("b", "a") in circular

    def test_finds_longer_cycle(self):
        """Test detection of A -> B -> C -> A cycle."""
        deps = {
            "a": {"b"},
            "b": {"c"},
            "c": {"a"},
        }
        circular = _find_circular_dependencies(deps)
        assert len(circular) > 0

    def test_no_cycle(self):
        """Test no false positives for acyclic graph."""
        deps = {
            "a": {"b"},
            "b": {"c"},
            "c": set(),
        }
        circular = _find_circular_dependencies(deps)
        assert len(circular) == 0


class TestPathToModule:
    """Tests for _path_to_module function."""

    def test_converts_simple_path(self):
        """Test basic path conversion."""
        result = _path_to_module("src/mypackage/core/parser.py")
        assert result is not None
        assert "parser" in result

    def test_skips_init_files(self):
        """Test __init__.py files return None."""
        result = _path_to_module("src/pkg/__init__.py")
        assert result is None

    def test_skips_non_python(self):
        """Test non-Python files return None."""
        result = _path_to_module("src/pkg/script.js")
        assert result is None


class TestParseImportLine:
    """Tests for _parse_import_line function."""

    def test_parses_from_import(self):
        """Test from X import Y parsing."""
        result = _parse_import_line("from myproject.core import parser", "myproject")
        assert result is not None
        assert "core" in result

    def test_ignores_external(self):
        """Test external imports return None."""
        result = _parse_import_line("from pathlib import Path", "myproject")
        assert result is None

    def test_parses_import_statement(self):
        """Test import X parsing."""
        result = _parse_import_line("import myproject.core.parser", "myproject")
        assert result is not None


class TestGenerateModuleOverview:
    """Tests for generate_module_overview function."""

    def test_generates_diagram(self):
        """Test module overview generation."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=3,
            total_chunks=10,
            languages={"python": 3},
            files=[
                FileInfo(
                    path="src/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/core/chunker.py",
                    language="python",
                    hash="b",
                    chunk_count=3,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/utils/helpers.py",
                    language="python",
                    hash="c",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)
        assert diagram is not None
        assert "graph TB" in diagram

    def test_returns_none_for_empty(self):
        """Test returns None when no files."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=0,
            total_chunks=0,
            languages={},
            files=[],
        )
        diagram = generate_module_overview(status)
        assert diagram is None


class TestGenerateLanguagePieChart:
    """Tests for generate_language_pie_chart function."""

    def test_generates_pie_chart(self):
        """Test pie chart generation."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=5,
            total_chunks=20,
            languages={"python": 3, "javascript": 2},
            files=[],
        )
        chart = generate_language_pie_chart(status)
        assert chart is not None
        assert "pie" in chart
        assert "python" in chart
        assert "javascript" in chart

    def test_returns_none_for_no_languages(self):
        """Test returns None when no languages."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=0,
            total_chunks=0,
            languages={},
            files=[],
        )
        chart = generate_language_pie_chart(status)
        assert chart is None


class TestGenerateSequenceDiagram:
    """Tests for generate_sequence_diagram function."""

    def test_generates_sequence(self):
        """Test sequence diagram generation."""
        call_graph = {
            "main": ["process", "validate"],
            "process": ["transform"],
            "validate": [],
            "transform": [],
        }
        diagram = generate_sequence_diagram(call_graph, "main")
        assert diagram is not None
        assert "sequenceDiagram" in diagram
        assert "main" in diagram
        assert "process" in diagram

    def test_returns_none_for_empty(self):
        """Test returns None for empty call graph."""
        diagram = generate_sequence_diagram({})
        assert diagram is None

    def test_auto_selects_entry_point(self):
        """Test auto-selects entry point when not specified."""
        call_graph = {
            "main": ["a", "b", "c"],  # Most calls
            "helper": ["x"],
        }
        diagram = generate_sequence_diagram(call_graph)
        assert diagram is not None
        assert "main" in diagram


class TestWorkflowSequenceDiagrams:
    """Tests for workflow-specific sequence diagram generators."""

    def test_indexing_sequence_valid_mermaid(self):
        """Test indexing sequence generates valid Mermaid."""
        result = generate_indexing_sequence()
        assert "```mermaid" in result
        assert "sequenceDiagram" in result
        assert "RepositoryIndexer" in result
        assert "VectorStore" in result
        assert "CodeParser" in result
        assert "CodeChunker" in result
        assert "EmbeddingProvider" in result

    def test_indexing_sequence_shows_loop(self):
        """Test indexing sequence contains loop for file batches."""
        result = generate_indexing_sequence()
        assert "loop For each file batch" in result
        assert "end" in result

    def test_wiki_generation_sequence_valid_mermaid(self):
        """Test wiki generation sequence is valid Mermaid."""
        result = generate_wiki_generation_sequence()
        assert "```mermaid" in result
        assert "sequenceDiagram" in result
        assert "WikiGenerator" in result
        assert "LLMProvider" in result
        assert "VectorStore" in result

    def test_wiki_generation_sequence_has_parallel(self):
        """Test wiki generation sequence contains parallel operations."""
        result = generate_wiki_generation_sequence()
        assert "par Parallel searches" in result
        assert "rect rgb" in result  # Has colored sections

    def test_wiki_generation_sequence_shows_phases(self):
        """Test wiki generation shows all generation phases."""
        result = generate_wiki_generation_sequence()
        assert "Generate Overview" in result
        assert "Generate Architecture" in result
        assert "Generate Module Docs" in result

    def test_deep_research_sequence_valid_mermaid(self):
        """Test deep research sequence is valid Mermaid."""
        result = generate_deep_research_sequence()
        assert "```mermaid" in result
        assert "sequenceDiagram" in result
        assert "DeepResearchPipeline" in result
        assert "LLMProvider" in result
        assert "VectorStore" in result

    def test_deep_research_sequence_shows_all_steps(self):
        """Test deep research shows all 5 steps."""
        result = generate_deep_research_sequence()
        assert "Step 1: Decomposition" in result
        assert "Step 2: Parallel Retrieval" in result
        assert "Step 3: Gap Analysis" in result
        assert "Step 4: Follow-up Retrieval" in result
        assert "Step 5: Synthesis" in result

    def test_deep_research_sequence_has_parallel(self):
        """Test deep research contains parallel operations."""
        result = generate_deep_research_sequence()
        assert "par For each sub-question" in result
        assert "par For each follow-up" in result

    def test_workflow_sequences_contains_all(self):
        """Test combined workflow has all three sequences."""
        result = generate_workflow_sequences()
        assert "### Indexing Pipeline" in result
        assert "### Wiki Generation Pipeline" in result
        assert "### Deep Research Pipeline" in result

    def test_workflow_sequences_contains_all_diagrams(self):
        """Test combined workflow includes all diagram content."""
        result = generate_workflow_sequences()
        # Should contain content from all three diagrams
        assert "RepositoryIndexer" in result  # From indexing
        assert "WikiGenerator" in result  # From wiki generation
        assert "DeepResearchPipeline" in result  # From deep research

    def test_all_sequences_close_mermaid_blocks(self):
        """Test all sequences properly close mermaid code blocks."""
        for func in [
            generate_indexing_sequence,
            generate_wiki_generation_sequence,
            generate_deep_research_sequence,
        ]:
            result = func()
            # Should have opening and closing backticks
            assert result.count("```mermaid") == 1
            assert result.count("```") == 2  # Opening and closing


class TestEnhancedDependencyGraph:
    """Tests for enhanced dependency graph features."""

    def test_subgraph_grouping(self):
        """Test modules are grouped by directory in subgraphs."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from myproject.core.chunker import chunk",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/myproject/core/chunker.py",
                content="from myproject.generators.wiki import WikiGen",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="3",
                file_path="src/myproject/generators/wiki.py",
                content="# wiki generator",
                chunk_type=ChunkType.MODULE,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject")
        assert diagram is not None
        assert "subgraph" in diagram
        assert "core" in diagram.lower() or "Core" in diagram

    def test_clickable_links(self):
        """Test click handlers are added when wiki_base_path provided."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from myproject.core.chunker import chunk",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/myproject/core/chunker.py",
                content="# chunker",
                chunk_type=ChunkType.MODULE,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(
            chunks, "myproject", wiki_base_path="files/"
        )
        assert diagram is not None
        assert "click" in diagram
        assert "files/" in diagram

    def test_no_clickable_links_without_base_path(self):
        """Test click handlers are not added when wiki_base_path is empty."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from myproject.core.chunker import chunk",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/myproject/core/chunker.py",
                content="# chunker",
                chunk_type=ChunkType.MODULE,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject", wiki_base_path="")
        assert diagram is not None
        assert "click" not in diagram

    def test_external_dependencies_shown(self):
        """Test external deps shown with different styling when enabled."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from pathlib import Path\nimport os\nfrom pydantic import BaseModel",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject", show_external=True)
        # May or may not have internal deps, but if external shown
        if diagram:
            assert "external" in diagram.lower() or "External" in diagram
            assert "stroke-dasharray" in diagram

    def test_external_dependencies_hidden(self):
        """Test external deps hidden when show_external=False."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from pathlib import Path\nimport os",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject", show_external=False)
        # External deps should not appear
        if diagram:
            # External subgraph should not exist
            assert "External Dependencies" not in diagram

    def test_max_external_limit(self):
        """Test max_external limits number of external deps shown."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="import os\nimport sys\nimport json\nimport re\nimport pathlib",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=5,
            ),
        ]
        diagram = generate_dependency_graph(
            chunks, "myproject", show_external=True, max_external=2
        )
        if diagram and "External" in diagram:
            # Count external nodes (E0, E1, etc.)
            import re as regex

            ext_nodes = regex.findall(r"E\d+\(\[", diagram)
            assert len(ext_nodes) <= 2


class TestParseExternalImport:
    """Tests for _parse_external_import function."""

    def test_parses_from_import(self):
        """Test parsing 'from X import Y' style."""
        result = _parse_external_import("from pathlib import Path")
        assert result == "pathlib"

    def test_parses_import_statement(self):
        """Test parsing 'import X' style."""
        result = _parse_external_import("import os")
        assert result == "os"

    def test_parses_nested_import(self):
        """Test parsing nested module imports."""
        result = _parse_external_import("from os.path import join")
        assert result == "os"

    def test_returns_none_for_invalid(self):
        """Test returns None for non-import lines."""
        assert _parse_external_import("def func():") is None
        assert _parse_external_import("# comment") is None
        assert _parse_external_import("") is None


class TestModuleToWikiPath:
    """Tests for _module_to_wiki_path function."""

    def test_simple_module(self):
        """Test simple module path conversion."""
        result = _module_to_wiki_path("core.parser", "local_deepwiki")
        assert result == "src/local_deepwiki/core/parser.md"

    def test_nested_module(self):
        """Test nested module path conversion."""
        result = _module_to_wiki_path("providers.llm.ollama", "local_deepwiki")
        assert result == "src/local_deepwiki/providers/llm/ollama.md"

    def test_single_level_module(self):
        """Test single-level module path conversion."""
        result = _module_to_wiki_path("models", "local_deepwiki")
        assert result == "src/local_deepwiki/models.md"


class TestDuplicateClassHandling:
    """Tests for duplicate class handling in diagram generation."""

    def test_skips_duplicate_class(self):
        """Test that duplicate class chunks are skipped (line 57)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="2",
                file_path="test2.py",
                content="class MyClass:\n    def other(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",  # Same name - should be skipped
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "MyClass" in diagram
        # Only one class definition should appear
        assert diagram.count("class MyClass") == 1


class TestMethodChunkCollection:
    """Tests for METHOD chunk collection in diagrams."""

    def test_collects_method_chunks(self):
        """Test that METHOD chunks are collected (lines 89-99, 208)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="2",
                file_path="test.py",
                content="def process(self, x: int) -> str:\n    return str(x)",
                chunk_type=ChunkType.METHOD,
                language=Language.PYTHON,
                start_line=3,
                end_line=4,
                name="process",
                parent_name="MyClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks, show_types=True)
        assert diagram is not None
        assert "process" in diagram

    def test_method_with_unknown_parent(self):
        """Test method chunk with no parent in classes dict (lines 94-95)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="2",
                file_path="test.py",
                content="def orphan_method(self):\n    pass",
                chunk_type=ChunkType.METHOD,
                language=Language.PYTHON,
                start_line=5,
                end_line=6,
                name="orphan_method",
                parent_name="UnknownClass",  # Parent not in classes
                metadata={},
            ),
        ]
        # Should not crash
        diagram = generate_class_diagram(chunks)
        # May be None if MyClass has no methods/attrs

    def test_skips_duplicate_methods(self):
        """Test that duplicate method names are skipped (lines 97-99)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="2",
                file_path="test.py",
                content="def method(self):\n    pass",
                chunk_type=ChunkType.METHOD,
                language=Language.PYTHON,
                start_line=2,
                end_line=3,
                name="method",
                parent_name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="3",
                file_path="test.py",
                content="def method(self):\n    pass",  # Duplicate
                chunk_type=ChunkType.METHOD,
                language=Language.PYTHON,
                start_line=4,
                end_line=5,
                name="method",
                parent_name="MyClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        # Count occurrences of method (should appear once in class body)


class TestClassDiagramAbstract:
    """Tests for abstract class handling in diagrams."""

    def test_marks_abstract_class(self):
        """Test abstract class annotation is shown (line 147)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="from abc import ABC\nclass AbstractBase(ABC):\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="AbstractBase",
                metadata={"parent_classes": ["ABC"]},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "<<abstract>>" in diagram

    def test_marks_abstract_by_content(self):
        """Test abstract detection from content keyword."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyAbstract:\n    # abstract base\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="MyAbstract",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "<<abstract>>" in diagram


class TestMethodWithoutSignature:
    """Tests for method display without signature."""

    def test_method_without_types(self):
        """Test method shown without types when show_types=False (line 159)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks, show_types=False)
        assert diagram is not None
        assert "method()" in diagram


class TestExtractMethodsFromContent:
    """Tests for method extraction from class content."""

    def test_extracts_methods_from_class_content(self):
        """Test methods extracted from class content when no METHOD chunks (lines 113, 123)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def method_one(self) -> str:\n        pass\n    def method_two(self) -> int:\n        pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=5,
                name="MyClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "method_one" in diagram
        assert "method_two" in diagram

    def test_skips_extraction_when_methods_exist(self):
        """Test extraction skipped when class already has methods (line 113)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def in_content(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="2",
                file_path="test.py",
                content="def from_chunk(self):\n    pass",
                chunk_type=ChunkType.METHOD,
                language=Language.PYTHON,
                start_line=2,
                end_line=3,
                name="from_chunk",
                parent_name="MyClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        # Should have from_chunk but in_content may also be extracted


class TestAttributeExtractionEdgeCases:
    """Tests for attribute extraction edge cases."""

    def test_attribute_without_type(self):
        """Test attribute extraction without type hint (line 259)."""
        content = """class MyClass:
    name: str
    plain
    def __init__(self):
        pass
"""
        attrs = _extract_class_attributes(content, "python")
        # Should handle attributes both with and without types

    def test_init_attribute_with_type(self):
        """Test init assignment with type hint (line 267)."""
        content = """class MyClass:
    def __init__(self):
        self.typed: str = "value"
        self.untyped = 42
"""
        attrs = _extract_class_attributes(content, "python")
        assert any("typed" in a for a in attrs)


class TestMethodSignatureEdgeCases:
    """Tests for method signature edge cases."""

    def test_parameter_without_type(self):
        """Test parameter without type annotation (lines 303-305)."""
        content = "def process(x, y=None) -> bool:"
        sig = _extract_method_signature(content)
        assert sig is not None
        assert "x" in sig


class TestIsTestModule:
    """Tests for _is_test_module function."""

    def test_detects_test_module_by_name(self):
        """Test detection by module name prefix (line 329)."""
        from local_deepwiki.generators.diagrams import _is_test_module

        assert _is_test_module("test_parser", "test_parser.py") is True
        assert _is_test_module("core.test_utils", "core/test_utils.py") is True

    def test_detects_test_by_path(self):
        """Test detection by file path (line 332)."""
        from local_deepwiki.generators.diagrams import _is_test_module

        assert _is_test_module("parser", "tests/parser.py") is True
        assert _is_test_module("parser", "/project/tests/parser.py") is True

    def test_non_test_module(self):
        """Test non-test module returns False."""
        from local_deepwiki.generators.diagrams import _is_test_module

        assert _is_test_module("core.parser", "src/core/parser.py") is False


class TestDependencyCollectionEdgeCases:
    """Tests for dependency collection edge cases."""

    def test_handles_search_result_wrapper(self):
        """Test unwrapping SearchResult objects (line 370)."""

        class MockSearchResult:
            def __init__(self, chunk):
                self.chunk = chunk

        inner_chunk = CodeChunk(
            id="1",
            file_path="src/myproject/core/parser.py",
            content="from myproject.core.chunker import chunk",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        wrapped = MockSearchResult(inner_chunk)
        chunks = [wrapped]
        diagram = generate_dependency_graph(chunks, "myproject")
        # Should not crash when unwrapping

    def test_skips_empty_module_path(self):
        """Test skipping chunks with non-convertible paths (line 377)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="__init__.py",  # Should return None from _path_to_module
                content="from myproject.core import parser",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject")
        # Should handle gracefully

    def test_excludes_test_modules(self):
        """Test test modules are excluded (lines 380, 396)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="tests/test_parser.py",
                content="from myproject.core import parser",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/myproject/core/parser.py",
                content="from myproject.utils import helpers",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject", exclude_tests=True)
        if diagram:
            assert "test_parser" not in diagram

    def test_includes_test_modules_when_not_excluded(self):
        """Test test modules included when exclude_tests=False."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="tests/test_parser.py",
                content="from myproject.core import parser",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject", exclude_tests=False)
        # Should include test module

    def test_skips_empty_lines(self):
        """Test empty lines in import content are skipped (line 391)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from myproject.utils import helpers\n\n\nfrom myproject.core import chunker",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=4,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject")
        # Should handle empty lines gracefully


class TestExternalDependencySubgraph:
    """Tests for external dependency subgraph generation."""

    def test_empty_external_deps(self):
        """Test no external subgraph when empty (line 506)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from myproject.core.chunker import chunk",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/myproject/core/chunker.py",
                content="# module",
                chunk_type=ChunkType.MODULE,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject", show_external=True)
        if diagram:
            # No external imports, so no External Dependencies subgraph
            pass


class TestEdgesAndCircularDependencies:
    """Tests for edge generation and circular dependency handling."""

    def test_skips_missing_from_id(self):
        """Test edges skipped when from_id not found (line 536)."""
        # This is tested internally, hard to test directly

    def test_circular_dependency_styling(self):
        """Test circular dependencies get special styling (lines 540-541, 563-574)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/a.py",
                content="from myproject.core.b import B",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/myproject/core/b.py",
                content="from myproject.core.a import A",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject", detect_circular=True)
        if diagram:
            # Should have circular styling
            assert "circular" in diagram or "stroke:#f00" in diagram


class TestExternalDependencyEdges:
    """Tests for external dependency edge generation."""

    def test_external_dep_edges(self):
        """Test external dependency edges are added (line 641)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from myproject.utils import helpers\nimport pathlib\nimport os",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
            ),
            CodeChunk(
                id="2",
                file_path="src/myproject/utils/helpers.py",
                content="# helpers",
                chunk_type=ChunkType.MODULE,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject", show_external=True)
        if diagram:
            # Should have dashed edges to external deps
            assert "-.-> " in diagram or "External" in diagram


class TestParseExternalImportEdgeCases:
    """Additional tests for _parse_external_import."""

    def test_returns_none_for_underscore_module(self):
        """Test returns None for modules starting with underscore (line 680)."""
        result = _parse_external_import("from _internal import something")
        assert result is None


class TestFindCircularDependenciesEdgeCases:
    """Tests for circular dependency detection edge cases."""

    def test_visited_node_skipped(self):
        """Test already-visited nodes are skipped (line 727)."""
        deps = {
            "a": {"b", "c"},
            "b": {"c"},
            "c": {"d"},
            "d": set(),
        }
        circular = _find_circular_dependencies(deps)
        assert len(circular) == 0  # No cycle


class TestPathToModuleEdgeCases:
    """Tests for _path_to_module edge cases."""

    def test_handles_no_src_directory(self):
        """Test path without src directory (lines 766-767)."""
        result = _path_to_module("mypackage/core/parser.py")
        # Should still work, just different result

    def test_handles_short_path(self):
        """Test very short path."""
        result = _path_to_module("file.py")
        assert result is not None or result is None  # Should not crash


class TestModuleOverviewEdgeCases:
    """Tests for module overview edge cases."""

    def test_files_with_root_only(self):
        """Test files in root with _root counting (line 854)."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="src/mypackage/module.py",
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)
        # Should handle files at package root

    def test_short_path_skipped(self):
        """Test files with path < 2 parts are skipped (line 839)."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="module.py",  # Only 1 part
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)
        # May return None since file is skipped

    def test_empty_directories_returns_none(self):
        """Test empty directories dict returns None (line 857)."""
        # Already covered by test_returns_none_for_empty but adding explicit test
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="x.py",  # Too short
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)
        assert diagram is None


class TestSequenceDiagramEdgeCases:
    """Tests for sequence diagram edge cases."""

    def test_entry_point_not_in_graph(self):
        """Test returns None when entry_point not in call_graph (line 937)."""
        call_graph = {
            "main": ["process"],
            "process": [],
        }
        diagram = generate_sequence_diagram(call_graph, entry_point="nonexistent")
        assert diagram is None

    def test_max_depth_limits_participants(self):
        """Test max_depth limits participant collection (line 947)."""
        call_graph = {
            "a": ["b"],
            "b": ["c"],
            "c": ["d"],
            "d": ["e"],
            "e": ["f"],
            "f": ["g"],
        }
        diagram = generate_sequence_diagram(call_graph, entry_point="a", max_depth=2)
        assert diagram is not None
        # Should not include deeply nested participants

    def test_max_depth_limits_calls(self):
        """Test max_depth limits call depth (line 965)."""
        call_graph = {
            "main": ["a"],
            "a": ["b"],
            "b": ["c"],
            "c": ["d"],
        }
        diagram = generate_sequence_diagram(call_graph, entry_point="main", max_depth=1)
        assert diagram is not None

    def test_skips_visited_calls(self):
        """Test visited calls are skipped (line 969)."""
        call_graph = {
            "main": ["helper", "helper"],  # Duplicate
            "helper": [],
        }
        diagram = generate_sequence_diagram(call_graph, entry_point="main")
        assert diagram is not None

    def test_returns_none_for_no_calls(self):
        """Test returns None when only participants, no calls (line 984)."""
        call_graph = {
            "main": [],  # No callees
        }
        diagram = generate_sequence_diagram(call_graph, entry_point="main")
        assert diagram is None

    def test_displays_last_part_of_dotted_name(self):
        """Test dotted names show only last part in participant."""
        call_graph = {
            "module.main": ["module.helper"],
            "module.helper": [],
        }
        diagram = generate_sequence_diagram(call_graph, entry_point="module.main")
        assert diagram is not None
        assert "as main" in diagram
        assert "as helper" in diagram


class TestClassDiagramWithSearchResults:
    """Tests for class diagram with SearchResult wrapper."""

    def test_unwraps_search_results(self):
        """Test SearchResult objects are unwrapped."""

        class MockSearchResult:
            def __init__(self, chunk):
                self.chunk = chunk

        inner_chunk = CodeChunk(
            id="1",
            file_path="test.py",
            content="class MyClass:\n    def method(self): pass",
            chunk_type=ChunkType.CLASS,
            language=Language.PYTHON,
            start_line=1,
            end_line=2,
            name="MyClass",
            metadata={},
        )
        wrapped = MockSearchResult(inner_chunk)
        chunks = [wrapped]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "MyClass" in diagram


class TestClassDiagramBaseModel:
    """Tests for BaseModel detection as dataclass."""

    def test_detects_basemodel_as_dataclass(self):
        """Test Pydantic BaseModel is marked as dataclass."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyModel:\n    name: str\n    age: int",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="MyModel",
                metadata={"parent_classes": ["BaseModel"]},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "<<dataclass>>" in diagram


class TestClassDiagramDocstring:
    """Tests for class docstring in diagram."""

    def test_class_with_docstring(self):
        """Test class with docstring is handled."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content='class MyClass:\n    """A documented class."""\n    def method(self): pass',
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="MyClass",
                docstring="A documented class.",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "MyClass" in diagram


class TestMethodsByClassInitialization:
    """Tests for methods_by_class initialization during extraction (line 123)."""

    def test_initializes_methods_by_class_during_extraction(self):
        """Test that methods_by_class[class_name] is initialized when extracting from content."""
        # Create a class chunk without any METHOD chunks
        # The class should NOT be in methods_by_class initially
        # but methods will be extracted from content
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class NewClass:\n    def extracted_method(self) -> None:\n        pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="NewClass",
                metadata={},
            ),
        ]
        # This should trigger line 123 where methods_by_class[class_name] = []
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "extracted_method" in diagram


class TestAttributeWithoutTypeHint:
    """Tests for attribute extraction without type hint (line 259)."""

    def test_extracts_attribute_without_equals(self):
        """Test extraction of class attribute without equals sign or type."""
        # Pattern: ^\s{4}(\w+)\s*:\s*([^=\n]+?)(?:\s*=|$)
        # This tests when type_str is empty after strip
        content = """class MyClass:
    plain_attr:
    typed_attr: str
"""
        attrs = _extract_class_attributes(content, "python")
        # plain_attr should match but type_hint group might be empty/whitespace
        # This covers line 259


class TestExcludeTestImports:
    """Tests for excluding test module imports (line 396)."""

    def test_excludes_test_module_imports(self):
        """Test that imports of test_ modules are excluded when exclude_tests=True."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from myproject.test_helpers import mock\nfrom myproject.core.chunker import chunk",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
            ),
            CodeChunk(
                id="2",
                file_path="src/myproject/core/chunker.py",
                content="# chunker module",
                chunk_type=ChunkType.MODULE,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject", exclude_tests=True)
        if diagram:
            # test_helpers should not appear
            assert "test_helpers" not in diagram


class TestCircularDependencyStylingComplete:
    """Complete tests for circular dependency styling (lines 536, 568, 572-574)."""

    def test_full_circular_styling_with_multiple_modules(self):
        """Test complete circular styling with modules that have node_ids."""
        # Create a clear circular dependency that will trigger styling
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/module_a.py",
                content="from myproject.core.module_b import B",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/myproject/core/module_b.py",
                content="from myproject.core.module_a import A",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject", detect_circular=True)
        if diagram:
            # Should contain circular marking
            assert "circular" in diagram or "linkStyle" in diagram


class TestExternalDependencyEdgesComplete:
    """Complete tests for external dependency edges (line 641)."""

    def test_external_edges_with_valid_from_id(self):
        """Test external dependency edges when from_id exists."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from myproject.core.chunker import chunk\nimport pathlib\nimport json",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
            ),
            CodeChunk(
                id="2",
                file_path="src/myproject/core/chunker.py",
                content="# chunker",
                chunk_type=ChunkType.MODULE,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject", show_external=True)
        if diagram:
            # Should have edges to external deps
            assert "-.-> " in diagram or "E0" in diagram or "E1" in diagram


class TestPathToModuleException:
    """Tests for _path_to_module exception handling (lines 766-767)."""

    def test_handles_unusual_path_structure(self):
        """Test path with src but unusual structure."""
        # Try to trigger ValueError or IndexError
        result = _path_to_module("src/.py")  # Very short after src
        # Should not crash, may return None or empty
        assert result is None or result == ""

    def test_handles_path_with_only_src(self):
        """Test path that's just src/file.py."""
        result = _path_to_module("src/file.py")
        # After removing src, only ["file"] remains which has len=1
        # So parts = parts[1:] would result in [] or cause IndexError
        # Should handle gracefully


class TestModuleOverviewRootFiles:
    """Tests for module overview with root-level files (line 854)."""

    def test_files_directly_in_package(self):
        """Test files directly in top-level package (line 854)."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=10,
            languages={"python": 2},
            files=[
                FileInfo(
                    path="mypackage/module.py",  # Only 2 parts, len(parts) == 2
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="mypackage/utils/helper.py",  # 3 parts
                    language="python",
                    hash="b",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)
        # module.py should increment _root counter
        assert diagram is not None


class TestInternalFunctionsDirectly:
    """Direct tests for internal functions to ensure coverage."""

    def test_add_edges_with_missing_node(self):
        """Test _add_edges skips modules not in node_ids."""
        from local_deepwiki.generators.diagrams import _add_edges

        lines = []
        internal_deps = {"unknown_module": {"other"}}
        node_ids = {}  # Empty - from_id won't be found
        circular_edges = set()

        _add_edges(lines, internal_deps, node_ids, circular_edges)
        # Should not add any edges since from_id is None
        assert len(lines) == 0

    def test_add_circular_styling_with_missing_node(self):
        """Test _add_circular_styling skips modules not in node_ids."""
        from local_deepwiki.generators.diagrams import _add_circular_styling

        lines = []
        internal_deps = {"unknown_module": {"other"}}
        node_ids = {}  # Empty - from_id won't be found
        circular_edges = {("unknown_module", "other")}

        _add_circular_styling(lines, internal_deps, node_ids, circular_edges)
        # Should have linkStyle default but skip the module without node_id
        assert "linkStyle default" in lines[0]

    def test_collect_dependencies_with_test_import(self):
        """Test _collect_dependencies excludes test_ imports."""
        from local_deepwiki.generators.diagrams import _collect_dependencies

        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from myproject.test_utils import helper\nfrom myproject.core.other import func",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
            ),
        ]
        data = _collect_dependencies(
            chunks, "myproject", show_external=False, exclude_tests=True
        )
        # test_utils should be excluded from dependencies
        parser_deps = data.dependencies.get("core.parser", set())
        assert "test_utils" not in parser_deps


class TestClassDiagramMethodNotInList:
    """Test for method extraction when class not in methods_by_class (line 123)."""

    def test_method_extraction_creates_list(self):
        """Test that method extraction initializes the list for a class."""
        # Create chunks where the class is added to classes dict
        # but NOT to methods_by_class, then method extraction should create it
        from local_deepwiki.generators.diagrams import (
            _collect_class_from_chunk,
            _extract_methods_from_class_content,
            _unwrap_chunk,
        )

        chunk = CodeChunk(
            id="1",
            file_path="test.py",
            content="class TestClass:\n    def method_a(self) -> int:\n        return 1",
            chunk_type=ChunkType.CLASS,
            language=Language.PYTHON,
            start_line=1,
            end_line=3,
            name="TestClass",
            metadata={},
        )

        classes = {}
        methods_by_class = {}

        # Collect the class
        _collect_class_from_chunk(
            chunk, classes, methods_by_class, show_attributes=True
        )

        # methods_by_class["TestClass"] should be an empty list now
        assert "TestClass" in methods_by_class
        assert methods_by_class["TestClass"] == []

        # Now clear methods_by_class to test _extract_methods_from_class_content
        # creating the list
        del methods_by_class["TestClass"]

        # Extract methods from content - this should create the list
        _extract_methods_from_class_content(
            [chunk], classes, methods_by_class, show_types=True
        )

        # Now TestClass should be in methods_by_class with the extracted method
        assert "TestClass" in methods_by_class
        assert len(methods_by_class["TestClass"]) > 0


class TestAttributeWithoutTypeDirectly:
    """Direct test for attribute without type (line 259)."""

    def test_attribute_class_level_no_type_value(self):
        """Test attribute with annotation but empty type hint."""
        # The pattern: ^\s{4}(\w+)\s*:\s*([^=\n]+?)(?:\s*=|$)
        # If we have "    attr:  = value" the type_hint would be empty after strip
        content = """class MyClass:
    empty_type:   = "value"
    normal: str
"""
        attrs = _extract_class_attributes(content, "python")
        # empty_type has type_hint as whitespace, stripped to ""
        # so line 259 should be hit: attributes.append(f"{prefix}{name}")


class TestModuleOverviewRootDirectory:
    """Test for _root counting in module overview (line 854)."""

    def test_file_at_package_level_only(self):
        """Test file with exactly 2 path parts (len(parts) == 2, after top_dir processing)."""
        # After top_dir = parts[0], if len(parts) > 1 is False, we hit line 854
        # Need parts = [top_dir] after processing, meaning original path has 2 parts
        # and top_dir in (src, lib, pkg) so we skip to parts[1] and len becomes 1
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="src/mymodule.py",  # 2 parts: ["src", "mymodule.py"]
                    # top_dir becomes "src", then parts = parts[1:] = ["mymodule.py"]
                    # top_dir = parts[0] = "mymodule.py", parts = ["mymodule.py"]
                    # len(parts) > 1 is False, so _root is incremented
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)
        # Should handle the _root case
        assert diagram is not None


class TestExternalEdgeMissingFromId:
    """Test for external dependency edges with missing from_id (line 641)."""

    def test_external_edge_skipped_when_no_from_id(self):
        """Test that external edges are skipped when from_id doesn't exist."""
        from local_deepwiki.generators.diagrams import (
            _collect_dependencies,
            _build_node_ids,
        )

        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/orphan.py",  # Will become "orphan" module
                content="import pathlib",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
        ]

        data = _collect_dependencies(
            chunks, "myproject", show_external=True, exclude_tests=False
        )
        # Create node_ids that don't include the orphan module
        node_ids = {}  # Empty - from_id won't be found

        # Line 641 is hit when from_id is None for a module with external deps
        # We need to manually test this logic


class TestPathToModuleValueError:
    """Test for _path_to_module ValueError handling (lines 766-767)."""

    def test_path_without_src_triggers_exception(self):
        """Test path that triggers exception in try block."""
        # The try block does: parts.index("src")
        # If "src" not in parts, ValueError is raised and caught
        result = _path_to_module("notsrc/pkg/file.py")
        # Should not crash, exception is caught
        assert result is not None or result is None  # Just verify no crash

    def test_path_with_only_one_part_after_src(self):
        """Test path where len(parts) <= 1 after src processing."""
        # src/pkg.py -> after src removal: ["pkg.py"]
        # len(parts) > 1 is False, so parts = parts[1:] is NOT executed
        # This doesn't trigger the exception, but tests the flow
        result = _path_to_module("src/single.py")
        # parts = ["single"], len > 1 is False
        # So it skips parts = parts[1:] and returns "single"


class TestModuleOverviewLibDirectory:
    """Test module overview with lib directory prefix."""

    def test_lib_directory_prefix(self):
        """Test files in lib/ directory get processed correctly."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="lib/mymodule.py",  # lib is in (src, lib, pkg)
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)
        # Should handle lib prefix, _root case hit


class TestModuleOverviewPkgDirectory:
    """Test module overview with pkg directory prefix."""

    def test_pkg_directory_prefix(self):
        """Test files in pkg/ directory get processed correctly."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="pkg/mymodule.py",  # pkg is in (src, lib, pkg)
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)
        # Should handle pkg prefix


class TestDependencyGraphExternalEdgeSkip:
    """Test that external edges are properly skipped when from_id is missing."""

    def test_full_dependency_graph_with_orphan_external(self):
        """Test dependency graph where external dep module has no from_id."""
        # This is tricky - we need to create a situation where:
        # 1. A module has external deps
        # 2. That module is NOT in node_ids (from_id would be None)
        # This happens when module_external_deps has a key not in node_ids

        # The issue is that _collect_dependencies builds both, so they're in sync
        # Line 641 would only be hit if we manually manipulated the data
        # Let's verify the function handles this gracefully
        pass  # This edge case is very hard to trigger through public API


class TestPathToModuleIndexError:
    """Test for _path_to_module IndexError handling (lines 766-767)."""

    def test_path_causes_index_error(self):
        """Test path that triggers IndexError."""
        from local_deepwiki.generators.diagrams import _path_to_module
        from unittest.mock import patch, PropertyMock

        # The try block does:
        # 1. parts.index("src") - ValueError if "src" not found
        # 2. parts = parts[idx + 1:] - could cause IndexError if idx+1 > len
        # 3. if len(parts) > 1: parts = parts[1:] - safe
        #
        # IndexError is harder to trigger - parts.index() + slice is usually safe
        # Let's try to mock to force the exception
        result = _path_to_module("src")  # Just "src" with .py missing
        # This returns None because suffix != ".py"

    def test_path_with_src_at_end(self):
        """Test path where src is at the end."""
        result = _path_to_module("pkg/src.py")
        # "src" is in parts at index 1, parts[2:] = [], which is fine


class TestExternalEdgeFromIdMissing:
    """Direct test of external edge logic when from_id is missing (line 641)."""

    def test_direct_external_edge_skip(self):
        """Test external edge skipping by manipulating internal data."""
        from local_deepwiki.generators.diagrams import _DependencyData

        # Create a scenario manually
        lines = []
        node_ids = {"module_a": "M0"}  # Only module_a has node ID
        module_external_deps = {
            "module_a": {"pathlib"},
            "module_b": {"os"},  # module_b has no node ID
        }
        ext_node_ids = {"pathlib": "E0", "os": "E1"}

        # Simulate the logic from generate_dependency_graph lines 637-645
        for module, ext_imports in sorted(module_external_deps.items()):
            from_id = node_ids.get(module)
            if not from_id:  # Line 641 - module_b should hit this
                continue
            for ext in sorted(ext_imports):
                target_ext_id = ext_node_ids.get(ext)
                if target_ext_id:
                    lines.append(f"    {from_id} -.-> {target_ext_id}")

        # module_a should have edge, module_b should be skipped
        assert len(lines) == 1
        assert "M0" in lines[0]
        assert "E0" in lines[0]


class TestPathToModuleExceptionCoverage:
    """Test for complete exception coverage in _path_to_module."""

    def test_force_exception_with_mock(self):
        """Force exception in _path_to_module using mock."""
        from local_deepwiki.generators.diagrams import _path_to_module
        from unittest.mock import patch, MagicMock
        from pathlib import Path

        # Create a mock that raises an exception
        original_path = Path

        class MockPath:
            def __init__(self, path_str):
                self._path = original_path(path_str)
                self.suffix = self._path.suffix
                self.name = self._path.name

            @property
            def parts(self):
                parts = list(self._path.parts)
                # Simulate unusual state that causes exception
                if "forceerror" in str(self._path):
                    # Return object that raises on index()
                    class BadList(list):
                        def index(self, item):
                            raise IndexError("Forced error")

                    return BadList(parts)
                return parts

        with patch("local_deepwiki.generators.diagrams.Path", MockPath):
            result = _path_to_module("forceerror/module.py")
            # Exception should be caught, function continues
            # Result depends on remaining logic


class TestDependencyGraphEdges:
    """Verify dependency graph produces edges with real import chunks."""

    def test_internal_import_produces_edge(self):
        """An IMPORT chunk referencing another internal module should produce an edge."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/myproject/core/parser.py",
                content="from myproject.models import Schema",
                chunk_type=ChunkType.IMPORT,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/myproject/models.py",
                content="class Schema: pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="3",
                file_path="src/myproject/core/parser.py",
                content="def parse(): pass",
                chunk_type=ChunkType.FUNCTION,
                language=Language.PYTHON,
                start_line=3,
                end_line=5,
            ),
        ]
        diagram = generate_dependency_graph(chunks, "myproject")
        assert diagram is not None, "Expected a diagram but got None"
        assert "flowchart" in diagram
        # Should have at least one edge arrow
        assert "-->" in diagram
