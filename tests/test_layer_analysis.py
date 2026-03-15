"""Tests for layer dependency analysis."""

from pathlib import Path

from local_deepwiki.generators.analysis.layer_analysis import (
    LAYER_ORDER,
    analyze_layer_dependencies,
    categorize_file_layer,
)


class TestCategorizeFileLayer:
    """Tests for categorize_file_layer."""

    def test_web_layer(self) -> None:
        assert categorize_file_layer("web/app.py") == "web"

    def test_handler_layer(self) -> None:
        assert categorize_file_layer("handlers/core.py") == "handlers"

    def test_services_layer(self) -> None:
        assert categorize_file_layer("services/query_service.py") == "services"

    def test_core_layer(self) -> None:
        assert categorize_file_layer("core/indexer.py") == "core"
        assert categorize_file_layer("core/vectorstore/base.py") == "core"

    def test_generators_layer(self) -> None:
        assert categorize_file_layer("generators/codemap/graph.py") == "generators"

    def test_providers_layer(self) -> None:
        assert categorize_file_layer("providers/ollama.py") == "providers"

    def test_models_layer(self) -> None:
        assert categorize_file_layer("models/foundation.py") == "models"

    def test_unknown_layer(self) -> None:
        assert categorize_file_layer("server.py") == "root"

    def test_nested_path_with_src_prefix(self) -> None:
        """Paths with src/ prefix should still be categorized correctly."""
        assert categorize_file_layer("src/myproject/core/parser.py") == "core"

    def test_deeply_nested_path(self) -> None:
        """Deeply nested paths should use the first known layer directory."""
        assert categorize_file_layer("web/routes/api/v2/users.py") == "web"


class TestLayerOrder:
    """Tests for LAYER_ORDER constant."""

    def test_web_is_highest(self) -> None:
        assert LAYER_ORDER["web"] == 0

    def test_models_is_lowest(self) -> None:
        assert LAYER_ORDER["models"] == 6

    def test_core_below_generators(self) -> None:
        assert LAYER_ORDER["core"] > LAYER_ORDER["generators"]

    def test_handlers_above_services(self) -> None:
        assert LAYER_ORDER["handlers"] < LAYER_ORDER["services"]


class TestAnalyzeLayerDependencies:
    """Tests for analyze_layer_dependencies."""

    def test_returns_layer_counts(self, tmp_path: Path) -> None:
        """Creates minimal project structure, verifies output shape."""
        # Create a mini project with files in different layers
        core_dir = tmp_path / "core"
        core_dir.mkdir()
        (core_dir / "parser.py").write_text("def parse(): pass\n")
        (core_dir / "indexer.py").write_text("from core.parser import parse\n")

        handlers_dir = tmp_path / "handlers"
        handlers_dir.mkdir()
        (handlers_dir / "main.py").write_text("from core.indexer import index\n")

        result = analyze_layer_dependencies(tmp_path, "myproject")

        assert "layer_file_counts" in result
        assert "layer_edges" in result
        assert "violations" in result
        assert "total_violations" in result

        # Should have found files in core and handlers
        assert result["layer_file_counts"].get("core", 0) == 2
        assert result["layer_file_counts"].get("handlers", 0) == 1

    def test_detects_upward_dependency(self, tmp_path: Path) -> None:
        """Core importing from handlers is an upward (violation) dependency."""
        # Create handlers layer
        handlers_dir = tmp_path / "handlers"
        handlers_dir.mkdir()
        (handlers_dir / "router.py").write_text("def route(): pass\n")

        # Create core layer importing from handlers (violation!)
        core_dir = tmp_path / "core"
        core_dir.mkdir()
        (core_dir / "engine.py").write_text(
            "from handlers.router import route\n\ndef process():\n    return route()\n"
        )

        result = analyze_layer_dependencies(tmp_path, "myproject")

        assert result["total_violations"] >= 1
        # Find the violation: core -> handlers is upward (core is order 4, handlers is order 1)
        violations = result["violations"]
        assert len(violations) >= 1
        violation = violations[0]
        assert violation["from_layer"] == "core"
        assert violation["to_layer"] == "handlers"

    def test_no_violations_for_downward_imports(self, tmp_path: Path) -> None:
        """Handlers importing from core is allowed (downward dependency)."""
        core_dir = tmp_path / "core"
        core_dir.mkdir()
        (core_dir / "util.py").write_text("def helper(): pass\n")

        handlers_dir = tmp_path / "handlers"
        handlers_dir.mkdir()
        (handlers_dir / "api.py").write_text("from core.util import helper\n")

        result = analyze_layer_dependencies(tmp_path, "myproject")

        assert result["total_violations"] == 0
        assert result["violations"] == []

    def test_same_layer_imports_not_violations(self, tmp_path: Path) -> None:
        """Imports within the same layer should not be violations."""
        core_dir = tmp_path / "core"
        core_dir.mkdir()
        (core_dir / "parser.py").write_text("def parse(): pass\n")
        (core_dir / "chunker.py").write_text("from core.parser import parse\n")

        result = analyze_layer_dependencies(tmp_path, "myproject")

        assert result["total_violations"] == 0

    def test_empty_project(self, tmp_path: Path) -> None:
        """An empty directory should return empty results gracefully."""
        result = analyze_layer_dependencies(tmp_path, "empty")

        assert result["layer_file_counts"] == {}
        assert result["layer_edges"] == []
        assert result["violations"] == []
        assert result["total_violations"] == 0

    def test_ignores_non_python_files(self, tmp_path: Path) -> None:
        """Non-.py files should be skipped."""
        core_dir = tmp_path / "core"
        core_dir.mkdir()
        (core_dir / "readme.md").write_text("# Core module\n")
        (core_dir / "data.json").write_text("{}\n")
        (core_dir / "parser.py").write_text("def parse(): pass\n")

        result = analyze_layer_dependencies(tmp_path, "myproject")

        assert result["layer_file_counts"].get("core", 0) == 1
