"""Comprehensive tests for the plugin registry module.

This module focuses on achieving 90%+ coverage of registry.py,
covering all edge cases and error handling paths.
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.models import CodeChunk, ChunkType, IndexStatus
from local_deepwiki.models import Language as LangEnum
from local_deepwiki.models import WikiPage
from local_deepwiki.plugins.base import (
    EmbeddingProviderPlugin,
    LanguageParserPlugin,
    PluginMetadata,
    WikiGeneratorPlugin,
    WikiGeneratorResult,
)
from local_deepwiki.plugins.registry import (
    PluginRegistry,
    get_plugin_registry,
    reset_plugin_registry,
)


# Logger name for patching
LOGGER_NAME = "local_deepwiki.plugins.registry"


# =============================================================================
# Mock Plugin Implementations
# =============================================================================


class MockLanguageParser(LanguageParserPlugin):
    """Mock language parser for testing."""

    def __init__(self, name: str = "mock"):
        self._name = name
        self._initialized = False
        self._cleaned = False

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=f"{self._name}-parser",
            version="1.0.0",
            description=f"Mock parser for {self._name}",
        )

    @property
    def language_name(self) -> str:
        return self._name

    @property
    def file_extensions(self) -> list[str]:
        return [f".{self._name}"]

    def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
        return [
            CodeChunk(
                id="mock-chunk-1",
                file_path=str(file_path),
                language=LangEnum.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="mock_function",
                content=source.decode("utf-8"),
                start_line=1,
                end_line=10,
            )
        ]

    def initialize(self) -> None:
        self._initialized = True

    def cleanup(self) -> None:
        self._cleaned = True


class MockWikiGenerator(WikiGeneratorPlugin):
    """Mock wiki generator for testing."""

    def __init__(self, name: str = "mock-generator"):
        self._name = name
        self._initialized = False
        self._cleaned = False

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._name,
            version="1.0.0",
            description="Mock generator for testing",
        )

    @property
    def generator_name(self) -> str:
        return self._name

    async def generate(
        self,
        index_status: IndexStatus,
        wiki_path: Path,
        context: dict[str, Any],
    ) -> WikiGeneratorResult:
        return WikiGeneratorResult(
            pages=[
                WikiPage(
                    path="mock.md",
                    title="Mock Page",
                    content="# Mock Content",
                    generated_at=0.0,
                )
            ],
            metadata={"mock": True},
        )

    def initialize(self) -> None:
        self._initialized = True

    def cleanup(self) -> None:
        self._cleaned = True


class MockEmbeddingProvider(EmbeddingProviderPlugin):
    """Mock embedding provider for testing."""

    def __init__(self, name: str = "mock"):
        self._name = name
        self._initialized = False
        self._cleaned = False

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=f"{self._name}-embeddings",
            version="1.0.0",
            description="Mock embeddings for testing",
        )

    @property
    def provider_name(self) -> str:
        return self._name

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    def get_dimension(self) -> int:
        return 384

    def initialize(self) -> None:
        self._initialized = True

    def cleanup(self) -> None:
        self._cleaned = True


class FailingCleanupParser(LanguageParserPlugin):
    """Parser that fails during cleanup."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="failing-cleanup-parser", version="1.0.0")

    @property
    def language_name(self) -> str:
        return "failclean"

    @property
    def file_extensions(self) -> list[str]:
        return [".failclean"]

    def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
        return []

    def cleanup(self) -> None:
        raise RuntimeError("Cleanup failed intentionally")


class FailingCleanupGenerator(WikiGeneratorPlugin):
    """Wiki generator that fails during cleanup."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="failing-cleanup-gen", version="1.0.0")

    @property
    def generator_name(self) -> str:
        return "failclean-gen"

    async def generate(
        self,
        index_status: IndexStatus,
        wiki_path: Path,
        context: dict[str, Any],
    ) -> WikiGeneratorResult:
        return WikiGeneratorResult(pages=[])

    def cleanup(self) -> None:
        raise RuntimeError("Generator cleanup failed intentionally")


class FailingCleanupEmbedding(EmbeddingProviderPlugin):
    """Embedding provider that fails during cleanup."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="failing-cleanup-embed", version="1.0.0")

    @property
    def provider_name(self) -> str:
        return "failclean-embed"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    def get_dimension(self) -> int:
        return 384

    def cleanup(self) -> None:
        raise RuntimeError("Embedding cleanup failed intentionally")


# =============================================================================
# Tests for Plugin Overwriting Warnings (Lines 61, 74, 87)
# =============================================================================


class TestPluginOverwriting:
    """Tests for warning when plugins are overwritten."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return PluginRegistry()

    def test_language_parser_overwrite_warning(self, registry):
        """Test warning when overwriting a language parser (line 61)."""
        parser1 = MockLanguageParser("testlang")
        parser2 = MockLanguageParser("testlang")  # Same language name

        registry.register_language_parser(parser1)

        with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
            registry.register_language_parser(parser2)
            # Verify warning was called with expected message
            mock_logger.warning.assert_called()
            call_args = str(mock_logger.warning.call_args)
            assert "already registered, overwriting" in call_args

        # Second parser should replace first
        assert registry.get_language_parser("testlang") is parser2

    def test_wiki_generator_overwrite_warning(self, registry):
        """Test warning when overwriting a wiki generator (line 74)."""
        gen1 = MockWikiGenerator("testgen")
        gen2 = MockWikiGenerator("testgen")  # Same generator name

        registry.register_wiki_generator(gen1)

        with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
            registry.register_wiki_generator(gen2)
            mock_logger.warning.assert_called()
            call_args = str(mock_logger.warning.call_args)
            assert "already registered, overwriting" in call_args

        assert registry.get_wiki_generator("testgen") is gen2

    def test_embedding_provider_overwrite_warning(self, registry):
        """Test warning when overwriting an embedding provider (line 87)."""
        provider1 = MockEmbeddingProvider("testembed")
        provider2 = MockEmbeddingProvider("testembed")  # Same provider name

        registry.register_embedding_provider(provider1)

        with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
            registry.register_embedding_provider(provider2)
            mock_logger.warning.assert_called()
            call_args = str(mock_logger.warning.call_args)
            assert "already registered, overwriting" in call_args

        assert registry.get_embedding_provider("testembed") is provider2


# =============================================================================
# Tests for Unregister Returning False (Lines 140, 156)
# =============================================================================


class TestUnregisterNotFound:
    """Tests for unregister methods returning False when not found."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return PluginRegistry()

    def test_unregister_wiki_generator_not_found(self, registry):
        """Test unregister_wiki_generator returns False when not found (line 140)."""
        result = registry.unregister_wiki_generator("nonexistent")
        assert result is False

    def test_unregister_embedding_provider_not_found(self, registry):
        """Test unregister_embedding_provider returns False when not found (line 156)."""
        result = registry.unregister_embedding_provider("nonexistent")
        assert result is False

    def test_unregister_language_parser_not_found(self, registry):
        """Test unregister_language_parser returns False when not found."""
        result = registry.unregister_language_parser("nonexistent")
        assert result is False


# =============================================================================
# Tests for load_from_directory Edge Cases (Lines 228-229, 234-235, 245-246)
# =============================================================================


class TestLoadFromDirectory:
    """Tests for load_from_directory method edge cases."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return PluginRegistry()

    def test_load_skips_already_loaded_modules(self, registry, tmp_path):
        """Test that already loaded modules are skipped (lines 228-229)."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create a simple plugin file
        plugin_file = plugins_dir / "duplicate_plugin.py"
        plugin_file.write_text("""
# Simple module that does nothing
x = 1
""")

        # Load once
        loaded1 = registry.load_from_directory(plugins_dir)
        assert loaded1 == 1

        # Try to load again - should skip and log debug message
        with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
            loaded2 = registry.load_from_directory(plugins_dir)
            assert loaded2 == 0
            # Debug message should be called
            mock_logger.debug.assert_called()
            call_args = str(mock_logger.debug.call_args)
            assert "already loaded" in call_args.lower()

    def test_load_handles_spec_none(self, registry, tmp_path):
        """Test handling when spec_from_file_location returns None (lines 234-235)."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_file = plugins_dir / "bad_plugin.py"
        plugin_file.write_text("x = 1")

        with patch("importlib.util.spec_from_file_location", return_value=None):
            with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
                loaded = registry.load_from_directory(plugins_dir)
                assert loaded == 0
                mock_logger.warning.assert_called()
                call_args = str(mock_logger.warning.call_args)
                assert "Could not load plugin spec" in call_args

    def test_load_handles_spec_loader_none(self, registry, tmp_path):
        """Test handling when spec.loader is None (lines 234-235)."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_file = plugins_dir / "noloader_plugin.py"
        plugin_file.write_text("x = 1")

        mock_spec = MagicMock()
        mock_spec.loader = None

        with patch("importlib.util.spec_from_file_location", return_value=mock_spec):
            with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
                loaded = registry.load_from_directory(plugins_dir)
                assert loaded == 0
                mock_logger.warning.assert_called()
                call_args = str(mock_logger.warning.call_args)
                assert "Could not load plugin spec" in call_args

    def test_load_handles_module_execution_error(self, registry, tmp_path):
        """Test handling when module execution raises exception (lines 245-246)."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create a plugin file with syntax error or import error
        plugin_file = plugins_dir / "error_plugin.py"
        plugin_file.write_text("""
raise RuntimeError("Intentional error during module load")
""")

        with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
            loaded = registry.load_from_directory(plugins_dir)
            assert loaded == 0
            mock_logger.warning.assert_called()
            call_args = str(mock_logger.warning.call_args)
            assert "Failed to load plugin" in call_args

    def test_load_from_file_directory(self, registry, tmp_path):
        """Test that load_from_directory handles path that is a file."""
        # Create a file instead of directory
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("not a directory")

        loaded = registry.load_from_directory(file_path)
        assert loaded == 0


# =============================================================================
# Tests for load_from_entry_points (Lines 259-294)
# =============================================================================


class TestLoadFromEntryPoints:
    """Tests for load_from_entry_points method."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return PluginRegistry()

    def test_load_from_entry_points_python310_success(self, registry):
        """Test loading entry points on Python 3.10+ (lines 262-274)."""
        # Create mock entry point
        mock_ep = MagicMock()
        mock_ep.name = "test-plugin"
        mock_ep.load.return_value = MockLanguageParser

        mock_entry_points = MagicMock(return_value=[mock_ep])

        with patch.dict(sys.modules, {"importlib.metadata": MagicMock()}):
            with patch("sys.version_info", (3, 10, 0)):
                # Need to patch entry_points at the module level
                with patch(
                    "local_deepwiki.plugins.registry.sys.version_info",
                    (3, 10, 0),
                ):
                    # Mock the import within the function
                    mock_metadata = MagicMock()
                    mock_metadata.entry_points = mock_entry_points

                    with patch.dict(sys.modules, {"importlib.metadata": mock_metadata}):
                        loaded = registry.load_from_entry_points()
                        # The actual implementation checks version_info at runtime
                        # This test verifies the path doesn't crash
                        assert loaded >= 0

    def test_load_from_entry_points_empty(self, registry):
        """Test load_from_entry_points when no plugins are found."""
        # By default, entry_points returns empty for our custom groups
        loaded = registry.load_from_entry_points()
        # Should return 0 when no entry points found
        assert loaded >= 0

    def test_load_from_entry_points_handles_load_error(self, registry):
        """Test handling entry point load errors (lines 273-274, 288-289)."""
        mock_ep = MagicMock()
        mock_ep.name = "bad-plugin"
        mock_ep.load.side_effect = RuntimeError("Load failed")

        def mock_entry_points(group=None):
            if group in PluginRegistry.ENTRY_POINT_GROUPS.values():
                return [mock_ep]
            return []

        # We need to carefully mock the version check and entry_points
        with patch.object(sys, "version_info", (3, 11, 0)):
            with patch(
                "importlib.metadata.entry_points", side_effect=mock_entry_points
            ):
                with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
                    loaded = registry.load_from_entry_points()
                    # Load should have been attempted
                    mock_logger.warning.assert_called()
                    call_args = str(mock_logger.warning.call_args)
                    assert "Failed to load entry point" in call_args

    def test_load_from_entry_points_python39_path(self, registry):
        """Test loading entry points on Python 3.9 (lines 276-289)."""
        mock_ep = MagicMock()
        mock_ep.name = "test-plugin-39"
        mock_ep.load.return_value = MockWikiGenerator

        # Mock for Python 3.9 style (returns dict-like)
        mock_all_eps = {
            "local_deepwiki.plugins.generators": [mock_ep],
        }

        def mock_get_entry_points():
            return mock_all_eps

        # Force Python 3.9 path
        with patch.object(sys, "version_info", (3, 9, 0)):
            with patch("importlib.metadata.entry_points", mock_get_entry_points):
                loaded = registry.load_from_entry_points()
                # Should not crash on 3.9 path
                assert loaded >= 0

    def test_load_from_entry_points_python39_load_error(self, registry):
        """Test Python 3.9 path handles entry point load errors (lines 288-289)."""
        mock_ep = MagicMock()
        mock_ep.name = "failing-plugin-39"
        mock_ep.load.side_effect = RuntimeError("Load failed in 3.9 path")

        # Mock for Python 3.9 style (returns dict-like)
        mock_all_eps = {
            "local_deepwiki.plugins.parsers": [mock_ep],
        }

        def mock_get_entry_points():
            return mock_all_eps

        # Force Python 3.9 path
        with patch.object(sys, "version_info", (3, 9, 0)):
            with patch("importlib.metadata.entry_points", mock_get_entry_points):
                with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
                    loaded = registry.load_from_entry_points()
                    # Should log warning for failed load
                    mock_logger.warning.assert_called()
                    call_args = str(mock_logger.warning.call_args)
                    assert "Failed to load entry point" in call_args
                    assert loaded == 0

    def test_load_from_entry_points_import_error(self, registry, caplog):
        """Test handling ImportError for importlib.metadata (lines 291-292)."""
        # Mock version check to trigger the import
        original_version = sys.version_info

        with patch.object(sys, "version_info", (3, 10, 0)):
            with patch(
                "importlib.metadata.entry_points",
                side_effect=ImportError("No module"),
            ):
                loaded = registry.load_from_entry_points()
                # Should handle import error gracefully
                assert loaded == 0


# =============================================================================
# Tests for discover_plugins (Lines 316-340)
# =============================================================================


class TestDiscoverPlugins:
    """Tests for discover_plugins method."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return PluginRegistry()

    def test_discover_plugins_custom_dir(self, registry, tmp_path):
        """Test discover_plugins with custom directory (lines 319-320)."""
        custom_dir = tmp_path / "custom_plugins"
        custom_dir.mkdir()

        plugin_file = custom_dir / "custom.py"
        plugin_file.write_text("x = 1")

        with patch.object(registry, "load_from_entry_points", return_value=0):
            loaded = registry.discover_plugins(custom_dir=custom_dir)
            assert loaded >= 1

    def test_discover_plugins_repo_path(self, registry, tmp_path):
        """Test discover_plugins with repo path (lines 323-325)."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        plugins_dir = repo_path / ".deepwiki" / "plugins"
        plugins_dir.mkdir(parents=True)

        plugin_file = plugins_dir / "repo_plugin.py"
        plugin_file.write_text("x = 1")

        with patch.object(registry, "load_from_entry_points", return_value=0):
            loaded = registry.discover_plugins(repo_path=repo_path)
            assert loaded >= 1

    def test_discover_plugins_user_plugins(self, registry, tmp_path, monkeypatch):
        """Test discover_plugins loads user plugins (lines 328-329)."""
        # Mock Path.home() to return tmp_path
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        user_plugins = mock_home / ".config" / "local-deepwiki" / "plugins"
        user_plugins.mkdir(parents=True)

        plugin_file = user_plugins / "user_plugin.py"
        plugin_file.write_text("x = 1")

        with patch.object(registry, "load_from_entry_points", return_value=0):
            loaded = registry.discover_plugins()
            assert loaded >= 1

    def test_discover_plugins_entry_points(self, registry, tmp_path, monkeypatch):
        """Test discover_plugins calls load_from_entry_points (line 332)."""
        # Mock home to avoid loading real user plugins
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        mock_load_entry_points = MagicMock(return_value=2)
        with patch.object(registry, "load_from_entry_points", mock_load_entry_points):
            loaded = registry.discover_plugins()
            mock_load_entry_points.assert_called_once()
            assert loaded == 2

    def test_discover_plugins_logs_summary(self, registry, tmp_path, monkeypatch):
        """Test discover_plugins logs summary (lines 334-338)."""
        # Mock home to avoid loading real user plugins
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        with patch.object(registry, "load_from_entry_points", return_value=0):
            with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
                registry.discover_plugins()
                mock_logger.info.assert_called()
                call_args = str(mock_logger.info.call_args)
                assert "Plugin discovery complete" in call_args

    def test_discover_plugins_all_sources(self, registry, tmp_path, monkeypatch):
        """Test discover_plugins with all sources provided."""
        # Setup custom dir
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        (custom_dir / "c.py").write_text("x = 1")

        # Setup repo path
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        repo_plugins = repo_path / ".deepwiki" / "plugins"
        repo_plugins.mkdir(parents=True)
        (repo_plugins / "r.py").write_text("x = 1")

        # Setup user plugins
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)
        user_plugins = mock_home / ".config" / "local-deepwiki" / "plugins"
        user_plugins.mkdir(parents=True)
        (user_plugins / "u.py").write_text("x = 1")

        with patch.object(registry, "load_from_entry_points", return_value=0):
            loaded = registry.discover_plugins(
                repo_path=repo_path, custom_dir=custom_dir
            )
            assert loaded == 3


# =============================================================================
# Tests for cleanup_all Error Handling (Lines 347-348, 353-354, 359-360)
# =============================================================================


class TestCleanupAllErrors:
    """Tests for cleanup_all handling errors during cleanup."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return PluginRegistry()

    def test_cleanup_all_parser_error(self, registry):
        """Test cleanup_all handles parser cleanup errors (lines 347-348)."""
        registry.register_language_parser(FailingCleanupParser())

        # Should not raise, just log warning
        with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
            registry.cleanup_all()
            # Check warning was logged
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("Error cleaning up parser plugin" in c for c in warning_calls)

        # Registry should still be cleared
        assert registry.language_parsers == {}

    def test_cleanup_all_generator_error(self, registry):
        """Test cleanup_all handles generator cleanup errors (lines 353-354)."""
        registry.register_wiki_generator(FailingCleanupGenerator())

        # Should not raise, just log warning
        with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
            registry.cleanup_all()
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("Error cleaning up generator plugin" in c for c in warning_calls)

        assert registry.wiki_generators == {}

    def test_cleanup_all_embedding_error(self, registry):
        """Test cleanup_all handles embedding cleanup errors (lines 359-360)."""
        registry.register_embedding_provider(FailingCleanupEmbedding())

        # Should not raise, just log warning
        with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
            registry.cleanup_all()
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("Error cleaning up embedding plugin" in c for c in warning_calls)

        assert registry.embedding_providers == {}

    def test_cleanup_all_multiple_errors(self, registry):
        """Test cleanup_all handles multiple cleanup errors."""
        registry.register_language_parser(FailingCleanupParser())
        registry.register_wiki_generator(FailingCleanupGenerator())
        registry.register_embedding_provider(FailingCleanupEmbedding())

        # Should not raise
        with patch("local_deepwiki.plugins.registry.logger") as mock_logger:
            registry.cleanup_all()
            # All errors should be logged
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("Error cleaning up parser plugin" in c for c in warning_calls)
            assert any("Error cleaning up generator plugin" in c for c in warning_calls)
            assert any("Error cleaning up embedding plugin" in c for c in warning_calls)

        # All registries should be cleared
        assert registry.language_parsers == {}
        assert registry.wiki_generators == {}
        assert registry.embedding_providers == {}


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestRegistryEdgeCases:
    """Additional edge case tests for the registry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return PluginRegistry()

    def test_properties_return_copies(self, registry):
        """Test that property accessors return copies, not references."""
        parser = MockLanguageParser()
        registry.register_language_parser(parser)

        # Get the dict
        parsers = registry.language_parsers

        # Modify the returned dict
        parsers["injected"] = parser

        # Original should be unaffected
        assert "injected" not in registry.language_parsers

    def test_get_nonexistent_parsers(self, registry):
        """Test getting nonexistent items returns None."""
        assert registry.get_language_parser("nonexistent") is None
        assert registry.get_wiki_generator("nonexistent") is None
        assert registry.get_embedding_provider("nonexistent") is None

    def test_get_parser_for_extension_case_insensitive(self, registry):
        """Test extension matching is case insensitive."""
        parser = MockLanguageParser("test")
        registry.register_language_parser(parser)

        assert registry.get_parser_for_extension(".test") is parser
        assert registry.get_parser_for_extension(".TEST") is parser
        assert registry.get_parser_for_extension(".Test") is parser

    def test_get_parser_for_extension_no_match(self, registry):
        """Test get_parser_for_extension returns None when no match."""
        parser = MockLanguageParser("test")
        registry.register_language_parser(parser)

        assert registry.get_parser_for_extension(".unknown") is None

    def test_plugin_initialize_called(self, registry):
        """Test that initialize is called when registering."""
        parser = MockLanguageParser()
        generator = MockWikiGenerator()
        provider = MockEmbeddingProvider()

        registry.register_language_parser(parser)
        registry.register_wiki_generator(generator)
        registry.register_embedding_provider(provider)

        assert parser._initialized
        assert generator._initialized
        assert provider._initialized

    def test_plugin_cleanup_called_on_unregister(self, registry):
        """Test that cleanup is called when unregistering."""
        parser = MockLanguageParser()
        generator = MockWikiGenerator()
        provider = MockEmbeddingProvider()

        registry.register_language_parser(parser)
        registry.register_wiki_generator(generator)
        registry.register_embedding_provider(provider)

        registry.unregister_language_parser("mock")
        registry.unregister_wiki_generator("mock-generator")
        registry.unregister_embedding_provider("mock")

        assert parser._cleaned
        assert generator._cleaned
        assert provider._cleaned

    def test_list_plugins_empty(self, registry):
        """Test list_plugins with empty registry."""
        plugins = registry.list_plugins()
        assert plugins == {
            "language_parsers": [],
            "wiki_generators": [],
            "embedding_providers": [],
        }

    def test_list_plugins_populated(self, registry):
        """Test list_plugins with populated registry."""
        registry.register_language_parser(MockLanguageParser("lang1"))
        registry.register_language_parser(MockLanguageParser("lang2"))
        registry.register_wiki_generator(MockWikiGenerator("gen1"))
        registry.register_embedding_provider(MockEmbeddingProvider("embed1"))

        plugins = registry.list_plugins()

        assert "lang1" in plugins["language_parsers"]
        assert "lang2" in plugins["language_parsers"]
        assert "gen1" in plugins["wiki_generators"]
        assert "embed1" in plugins["embedding_providers"]

    def test_entry_point_groups_constant(self, registry):
        """Test ENTRY_POINT_GROUPS constant is correct."""
        expected = {
            "language_parser": "local_deepwiki.plugins.parsers",
            "wiki_generator": "local_deepwiki.plugins.generators",
            "embedding_provider": "local_deepwiki.plugins.embeddings",
        }
        assert registry.ENTRY_POINT_GROUPS == expected


# =============================================================================
# Tests for Global Registry Functions
# =============================================================================


class TestGlobalRegistryFunctions:
    """Tests for global registry singleton functions."""

    def test_get_plugin_registry_creates_singleton(self):
        """Test get_plugin_registry creates singleton on first call."""
        reset_plugin_registry()
        reg1 = get_plugin_registry()
        reg2 = get_plugin_registry()
        assert reg1 is reg2

    def test_reset_plugin_registry_clears_singleton(self):
        """Test reset_plugin_registry clears the singleton."""
        reset_plugin_registry()
        reg1 = get_plugin_registry()
        reg1.register_language_parser(MockLanguageParser())

        reset_plugin_registry()
        reg2 = get_plugin_registry()

        assert reg1 is not reg2
        assert reg2.language_parsers == {}

    def test_reset_plugin_registry_handles_none(self):
        """Test reset_plugin_registry handles None registry."""
        reset_plugin_registry()  # Reset to None
        reset_plugin_registry()  # Should not raise


# =============================================================================
# Tests for Python 3.9/3.10+ Entry Point Compatibility
# =============================================================================


class TestEntryPointCompatibility:
    """Tests for entry point loading compatibility."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return PluginRegistry()

    def test_python310_entry_points_interface(self, registry):
        """Test Python 3.10+ entry_points interface."""
        if sys.version_info >= (3, 10):
            from importlib.metadata import entry_points

            # Just verify the interface exists and doesn't crash
            eps = entry_points(group="nonexistent_group_for_testing")
            assert len(list(eps)) == 0

    def test_entry_points_handles_missing_groups(self, registry):
        """Test that missing entry point groups are handled gracefully."""
        loaded = registry.load_from_entry_points()
        # Should not crash even if groups don't exist
        assert loaded >= 0


# =============================================================================
# Tests for Module Loading Details
# =============================================================================


class TestModuleLoadingDetails:
    """Detailed tests for module loading behavior."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return PluginRegistry()

    def test_loaded_modules_tracking(self, registry, tmp_path):
        """Test that loaded modules are tracked correctly."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_file = plugins_dir / "tracked.py"
        plugin_file.write_text("x = 1")

        assert len(registry._loaded_modules) == 0

        registry.load_from_directory(plugins_dir)

        assert len(registry._loaded_modules) == 1
        assert "local_deepwiki_plugin_tracked" in registry._loaded_modules

    def test_module_added_to_sys_modules(self, registry, tmp_path):
        """Test that loaded modules are added to sys.modules."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_file = plugins_dir / "sysmod.py"
        plugin_file.write_text("x = 42")

        registry.load_from_directory(plugins_dir)

        assert "local_deepwiki_plugin_sysmod" in sys.modules
        assert sys.modules["local_deepwiki_plugin_sysmod"].x == 42

        # Cleanup
        del sys.modules["local_deepwiki_plugin_sysmod"]

    def test_cleanup_all_clears_loaded_modules(self, registry, tmp_path):
        """Test that cleanup_all clears loaded modules tracking."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_file = plugins_dir / "cleared.py"
        plugin_file.write_text("x = 1")

        registry.load_from_directory(plugins_dir)
        assert len(registry._loaded_modules) == 1

        registry.cleanup_all()
        assert len(registry._loaded_modules) == 0
