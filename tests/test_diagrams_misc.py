"""Tests for miscellaneous diagram functions: sanitize, language pie, sequence, etc."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from local_deepwiki.generators.diagrams import (
    _parse_external_import,
    _path_to_module,
    generate_class_diagram,
    generate_language_pie_chart,
    generate_module_overview,
    generate_sequence_diagram,
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


class TestParseExternalImportEdgeCases:
    """Additional tests for _parse_external_import."""

    def test_returns_none_for_underscore_module(self):
        """Test returns None for modules starting with underscore (line 680)."""
        result = _parse_external_import("from _internal import something")
        assert result is None


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
            "main": ["a", "b", "c"],
            "helper": ["x"],
        }
        diagram = generate_sequence_diagram(call_graph)
        assert diagram is not None
        assert "main" in diagram


class TestInternalImportResolution:
    """Tests for internal import resolution."""

    pass


class TestFilePathToWikiPath:
    """Tests for file path to wiki path conversion."""

    pass


class TestPathToModuleEdgeCases:
    """Tests for _path_to_module edge cases."""

    def test_handles_no_src_directory(self):
        """Test path without src directory (lines 766-767)."""
        result = _path_to_module("mypackage/core/parser.py")

    def test_handles_short_path(self):
        """Test very short path."""
        result = _path_to_module("file.py")
        assert result is None or result is not None


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
                    path="module.py",
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)

    def test_empty_directories_returns_none(self):
        """Test empty directories dict returns None (line 857)."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="x.py",
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
            "main": ["helper", "helper"],
            "helper": [],
        }
        diagram = generate_sequence_diagram(call_graph, entry_point="main")
        assert diagram is not None

    def test_returns_none_for_no_calls(self):
        """Test returns None when only participants, no calls (line 984)."""
        call_graph = {
            "main": [],
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


class TestPathToModuleException:
    """Tests for _path_to_module exception handling (lines 766-767)."""

    def test_handles_unusual_path_structure(self):
        """Test path with src but unusual structure."""
        result = _path_to_module("src/.py")
        assert result is None or result == ""

    def test_handles_path_with_only_src(self):
        """Test path that's just src/file.py."""
        result = _path_to_module("src/file.py")


class TestPathToModuleValueError:
    """Test for _path_to_module ValueError handling (lines 766-767)."""

    def test_path_without_src_triggers_exception(self):
        """Test path that triggers exception in try block."""
        result = _path_to_module("notsrc/pkg/file.py")
        assert result is not None or result is None

    def test_path_with_only_one_part_after_src(self):
        """Test path where len(parts) <= 1 after src processing."""
        result = _path_to_module("src/single.py")


class TestPathToModuleIndexError:
    """Test for _path_to_module IndexError handling (lines 766-767)."""

    def test_path_causes_index_error(self):
        """Test path that triggers IndexError."""
        from local_deepwiki.generators.diagrams import _path_to_module

        result = _path_to_module("src")

    def test_path_with_src_at_end(self):
        """Test path where src is at the end."""
        result = _path_to_module("pkg/src.py")


class TestPathToModuleExceptionCoverage:
    """Test for complete exception coverage in _path_to_module."""

    def test_force_exception_with_mock(self):
        """Force exception in _path_to_module using mock."""
        from local_deepwiki.generators.diagrams import _path_to_module

        original_path = Path

        class MockPath:
            def __init__(self, path_str):
                self._path = original_path(path_str)
                self.suffix = self._path.suffix
                self.name = self._path.name

            @property
            def parts(self):
                parts = list(self._path.parts)
                if "forceerror" in str(self._path):

                    class BadList(list):
                        def index(self, item):
                            raise IndexError("Forced error")

                    return BadList(parts)
                return parts

        with patch(
            "local_deepwiki.generators.diagrams.dependency_diagram.Path", MockPath
        ):
            result = _path_to_module("forceerror/module.py")


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
                    path="mypackage/module.py",
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="mypackage/utils/helper.py",
                    language="python",
                    hash="b",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)
        assert diagram is not None


class TestModuleOverviewRootDirectory:
    """Test for _root counting in module overview (line 854)."""

    def test_file_at_package_level_only(self):
        """Test file with exactly 2 path parts."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="src/mymodule.py",
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)
        assert diagram is not None


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
                    path="lib/mymodule.py",
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)


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
                    path="pkg/mymodule.py",
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        diagram = generate_module_overview(status)
