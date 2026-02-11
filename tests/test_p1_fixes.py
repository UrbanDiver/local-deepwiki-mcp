"""Tests for P1 usability fixes.

Fix 1: Mermaid click handlers in codemap diagrams
Fix 2: Pagination for get_glossary and get_inheritance
Fix 3: Coverage artifact filtering in module overview
Fix 4: exclude_tests option for detect_secrets
"""

from local_deepwiki.generators.codemap import (
    CodemapEdge,
    CodemapFocus,
    CodemapGraph,
    CodemapNode,
    generate_codemap_diagram,
)
from local_deepwiki.models import (
    DetectSecretsArgs,
    FileInfo,
    GetGlossaryArgs,
    GetInheritanceArgs,
    IndexStatus,
)


# ---------------------------------------------------------------------------
# Fix 1: Codemap click handlers
# ---------------------------------------------------------------------------


class TestCodemapClickHandlers:
    """Tests for Mermaid click handlers in codemap diagrams."""

    def _make_graph(self) -> CodemapGraph:
        """Build a small two-node cross-file graph for testing."""
        nodes = {
            "mod_a.func_a": CodemapNode(
                name="func_a",
                qualified_name="mod_a.func_a",
                file_path="src/mod_a.py",
                start_line=1,
                end_line=10,
                chunk_type="function",
            ),
            "mod_b.func_b": CodemapNode(
                name="func_b",
                qualified_name="mod_b.func_b",
                file_path="src/mod_b.py",
                start_line=5,
                end_line=20,
                chunk_type="function",
            ),
        }
        edges = [
            CodemapEdge(
                source="mod_a.func_a",
                target="mod_b.func_b",
                edge_type="calls",
                source_file="src/mod_a.py",
                target_file="src/mod_b.py",
            ),
        ]
        return CodemapGraph(nodes=nodes, edges=edges, entry_point="mod_a.func_a")

    def test_click_handlers_present_with_repo_path(self, tmp_path):
        """When repo_path is provided, click handlers should appear."""
        graph = self._make_graph()
        diagram = generate_codemap_diagram(
            graph, CodemapFocus.EXECUTION_FLOW, repo_path=tmp_path
        )
        assert "click N0" in diagram or "click N1" in diagram
        assert '"files/' in diagram

    def test_click_handlers_absent_without_repo_path(self):
        """When repo_path is None, no click handlers should appear."""
        graph = self._make_graph()
        diagram = generate_codemap_diagram(graph, CodemapFocus.EXECUTION_FLOW)
        assert "click " not in diagram

    def test_click_handlers_use_relative_paths(self, tmp_path):
        """Click handlers should use paths relative to repo_path."""
        graph = self._make_graph()
        diagram = generate_codemap_diagram(
            graph, CodemapFocus.EXECUTION_FLOW, repo_path=tmp_path
        )
        # Should reference files/src/mod_a.py, not absolute paths
        assert '"files/src/mod_a.py"' in diagram
        assert '"files/src/mod_b.py"' in diagram

    def test_click_handlers_with_data_flow_focus(self, tmp_path):
        """Click handlers should work with all focus modes."""
        graph = self._make_graph()
        diagram = generate_codemap_diagram(
            graph, CodemapFocus.DATA_FLOW, repo_path=tmp_path
        )
        assert "click " in diagram

    def test_click_handlers_empty_graph(self, tmp_path):
        """Empty graph should not produce click handlers."""
        graph = CodemapGraph()
        diagram = generate_codemap_diagram(
            graph, CodemapFocus.EXECUTION_FLOW, repo_path=tmp_path
        )
        assert "click " not in diagram


# ---------------------------------------------------------------------------
# Fix 2: Pagination models
# ---------------------------------------------------------------------------


class TestGlossaryPaginationModel:
    """Tests for GetGlossaryArgs pagination fields."""

    def test_default_values(self):
        """Default limit=100, offset=0, file_path=None."""
        args = GetGlossaryArgs(repo_path="/tmp/repo")
        assert args.limit == 100
        assert args.offset == 0
        assert args.file_path is None
        assert args.search is None

    def test_custom_pagination(self):
        """Custom limit and offset are accepted."""
        args = GetGlossaryArgs(repo_path="/tmp/repo", limit=50, offset=200)
        assert args.limit == 50
        assert args.offset == 200

    def test_file_path_filter(self):
        """file_path filter is stored correctly."""
        args = GetGlossaryArgs(repo_path="/tmp/repo", file_path="src/models.py")
        assert args.file_path == "src/models.py"

    def test_limit_bounds(self):
        """Limit must be between 1 and 5000."""
        import pytest

        with pytest.raises(Exception):
            GetGlossaryArgs(repo_path="/tmp/repo", limit=0)
        with pytest.raises(Exception):
            GetGlossaryArgs(repo_path="/tmp/repo", limit=5001)

    def test_offset_non_negative(self):
        """Offset must be >= 0."""
        import pytest

        with pytest.raises(Exception):
            GetGlossaryArgs(repo_path="/tmp/repo", offset=-1)


class TestInheritancePaginationModel:
    """Tests for GetInheritanceArgs pagination fields."""

    def test_default_values(self):
        """Default limit=100, offset=0, search=None."""
        args = GetInheritanceArgs(repo_path="/tmp/repo")
        assert args.limit == 100
        assert args.offset == 0
        assert args.search is None

    def test_search_filter(self):
        """Search filter is stored correctly."""
        args = GetInheritanceArgs(repo_path="/tmp/repo", search="Base")
        assert args.search == "Base"

    def test_custom_pagination(self):
        """Custom limit and offset are accepted."""
        args = GetInheritanceArgs(repo_path="/tmp/repo", limit=25, offset=50)
        assert args.limit == 25
        assert args.offset == 50


# ---------------------------------------------------------------------------
# Fix 3: Module overview artifact filtering
# ---------------------------------------------------------------------------


class TestModuleOverviewArtifactFiltering:
    """Tests that generate_module_overview skips coverage/artifact directories."""

    def test_excludes_htmlcov(self):
        """Files under htmlcov/ should be excluded from module overview."""
        from local_deepwiki.generators.diagrams import generate_module_overview

        index_status = IndexStatus(
            repo_path="/repo",
            indexed_at=0.0,
            total_files=4,
            total_chunks=10,
            files=[
                FileInfo(
                    path="src/app/main.py",
                    size_bytes=100,
                    last_modified=0.0,
                    hash="a",
                    chunk_count=2,
                ),
                FileInfo(
                    path="src/app/utils.py",
                    size_bytes=100,
                    last_modified=0.0,
                    hash="b",
                    chunk_count=2,
                ),
                FileInfo(
                    path="htmlcov/index.html",
                    size_bytes=100,
                    last_modified=0.0,
                    hash="c",
                    chunk_count=1,
                ),
                FileInfo(
                    path="htmlcov/style.css",
                    size_bytes=100,
                    last_modified=0.0,
                    hash="d",
                    chunk_count=1,
                ),
            ],
        )

        diagram = generate_module_overview(index_status)
        if diagram is not None:
            assert "htmlcov" not in diagram

    def test_excludes_pytest_cache(self):
        """Files under .pytest_cache/ should be excluded."""
        from local_deepwiki.generators.diagrams import generate_module_overview

        index_status = IndexStatus(
            repo_path="/repo",
            indexed_at=0.0,
            total_files=3,
            total_chunks=6,
            files=[
                FileInfo(
                    path="src/main.py",
                    size_bytes=100,
                    last_modified=0.0,
                    hash="a",
                    chunk_count=2,
                ),
                FileInfo(
                    path=".pytest_cache/README.md",
                    size_bytes=50,
                    last_modified=0.0,
                    hash="b",
                    chunk_count=1,
                ),
                FileInfo(
                    path=".mypy_cache/something.py",
                    size_bytes=50,
                    last_modified=0.0,
                    hash="c",
                    chunk_count=1,
                ),
            ],
        )

        diagram = generate_module_overview(index_status)
        if diagram is not None:
            assert ".pytest_cache" not in diagram
            assert ".mypy_cache" not in diagram

    def test_keeps_real_source_dirs(self):
        """Real source directories should still be included."""
        from local_deepwiki.generators.diagrams import generate_module_overview

        index_status = IndexStatus(
            repo_path="/repo",
            indexed_at=0.0,
            total_files=2,
            total_chunks=4,
            files=[
                FileInfo(
                    path="src/core/parser.py",
                    size_bytes=100,
                    last_modified=0.0,
                    hash="a",
                    chunk_count=2,
                ),
                FileInfo(
                    path="src/core/indexer.py",
                    size_bytes=100,
                    last_modified=0.0,
                    hash="b",
                    chunk_count=2,
                ),
            ],
        )

        diagram = generate_module_overview(index_status)
        assert diagram is not None
        assert "core" in diagram


# ---------------------------------------------------------------------------
# Fix 3: Config exclude_patterns
# ---------------------------------------------------------------------------


class TestConfigExcludePatterns:
    """Tests that default exclude_patterns include coverage directories."""

    def test_default_excludes_htmlcov(self):
        """Default exclude_patterns should include htmlcov/**."""
        from local_deepwiki.config import ParsingConfig

        config = ParsingConfig()
        assert "htmlcov/**" in config.exclude_patterns

    def test_default_excludes_pytest_cache(self):
        """Default exclude_patterns should include .pytest_cache/**."""
        from local_deepwiki.config import ParsingConfig

        config = ParsingConfig()
        assert ".pytest_cache/**" in config.exclude_patterns

    def test_default_excludes_coverage_dir(self):
        """Default exclude_patterns should include coverage/**."""
        from local_deepwiki.config import ParsingConfig

        config = ParsingConfig()
        assert "coverage/**" in config.exclude_patterns

    def test_default_excludes_mypy_cache(self):
        """Default exclude_patterns should include .mypy_cache/**."""
        from local_deepwiki.config import ParsingConfig

        config = ParsingConfig()
        assert ".mypy_cache/**" in config.exclude_patterns

    def test_default_excludes_ruff_cache(self):
        """Default exclude_patterns should include .ruff_cache/**."""
        from local_deepwiki.config import ParsingConfig

        config = ParsingConfig()
        assert ".ruff_cache/**" in config.exclude_patterns

    def test_default_excludes_tox(self):
        """Default exclude_patterns should include .tox/**."""
        from local_deepwiki.config import ParsingConfig

        config = ParsingConfig()
        assert ".tox/**" in config.exclude_patterns

    def test_default_excludes_nox(self):
        """Default exclude_patterns should include .nox/**."""
        from local_deepwiki.config import ParsingConfig

        config = ParsingConfig()
        assert ".nox/**" in config.exclude_patterns

    def test_default_excludes_coverage_file(self):
        """Default exclude_patterns should include .coverage."""
        from local_deepwiki.config import ParsingConfig

        config = ParsingConfig()
        assert ".coverage" in config.exclude_patterns


# ---------------------------------------------------------------------------
# Fix 4: exclude_tests option for detect_secrets
# ---------------------------------------------------------------------------


class TestDetectSecretsExcludeTests:
    """Tests for exclude_tests model field."""

    def test_default_false(self):
        """Default exclude_tests should be False."""
        args = DetectSecretsArgs(repo_path="/tmp/repo")
        assert args.exclude_tests is False

    def test_explicit_true(self):
        """Setting exclude_tests=True should work."""
        args = DetectSecretsArgs(repo_path="/tmp/repo", exclude_tests=True)
        assert args.exclude_tests is True


class TestIsTestFile:
    """Tests for the _is_test_file helper."""

    def test_test_directory(self):
        """Files in tests/ should be detected as test files."""
        from local_deepwiki.handlers._shared import _is_test_file

        assert _is_test_file("tests/test_something.py") is True
        assert _is_test_file("test/test_thing.py") is True
        assert _is_test_file("testing/helpers.py") is True

    def test_spec_directory(self):
        """Files in spec/ or specs/ should be detected as test files."""
        from local_deepwiki.handlers._shared import _is_test_file

        assert _is_test_file("spec/foo_spec.rb") is True
        assert _is_test_file("specs/bar.js") is True

    def test_test_file_prefix(self):
        """Files starting with test_ should be detected as test files."""
        from local_deepwiki.handlers._shared import _is_test_file

        assert _is_test_file("src/test_utils.py") is True

    def test_test_file_suffix(self):
        """Files ending with _test.py should be detected as test files."""
        from local_deepwiki.handlers._shared import _is_test_file

        assert _is_test_file("src/utils_test.py") is True

    def test_conftest(self):
        """conftest.py files should be detected as test files."""
        from local_deepwiki.handlers._shared import _is_test_file

        assert _is_test_file("conftest.py") is True
        assert _is_test_file("tests/conftest.py") is True

    def test_regular_source_file(self):
        """Regular source files should not be detected as test files."""
        from local_deepwiki.handlers._shared import _is_test_file

        assert _is_test_file("src/models.py") is False
        assert _is_test_file("src/handlers.py") is False
        assert _is_test_file("lib/utils.js") is False

    def test_nested_test_directory(self):
        """Deeply nested test directories should be detected."""
        from local_deepwiki.handlers._shared import _is_test_file

        assert _is_test_file("src/app/tests/test_auth.py") is True
