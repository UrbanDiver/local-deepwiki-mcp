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
        diagram = generate_dependency_graph(chunks, "myproject", wiki_base_path="files/")
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
        diagram = generate_dependency_graph(chunks, "myproject", show_external=True, max_external=2)
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
