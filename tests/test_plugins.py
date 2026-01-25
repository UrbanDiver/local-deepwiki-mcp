"""Tests for the plugin system."""

from pathlib import Path
from typing import Any

import pytest

from local_deepwiki.models import CodeChunk, ChunkType, IndexStatus
from local_deepwiki.models import Language as LangEnum
from local_deepwiki.models import WikiPage
from local_deepwiki.plugins.base import (
    EmbeddingProviderPlugin,
    LanguageParserPlugin,
    Plugin,
    PluginMetadata,
    WikiGeneratorPlugin,
    WikiGeneratorResult,
)
from local_deepwiki.plugins.registry import (
    PluginRegistry,
    get_plugin_registry,
    reset_plugin_registry,
)


# Test plugin implementations
class MockLanguageParser(LanguageParserPlugin):
    """Mock language parser for testing."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock-parser",
            version="1.0.0",
            description="Mock parser for testing",
        )

    @property
    def language_name(self) -> str:
        return "mock"

    @property
    def file_extensions(self) -> list[str]:
        return [".mock", ".mck"]

    def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
        return [
            CodeChunk(
                id="mock-chunk-1",
                file_path=str(file_path),
                language=LangEnum.PYTHON,  # Use existing enum for mock
                chunk_type=ChunkType.FUNCTION,
                name="mock_function",
                content=source.decode("utf-8"),
                start_line=1,
                end_line=10,
            )
        ]


class MockWikiGenerator(WikiGeneratorPlugin):
    """Mock wiki generator for testing."""

    def __init__(self, name: str = "mock-generator"):
        self._name = name

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


class MockEmbeddingProvider(EmbeddingProviderPlugin):
    """Mock embedding provider for testing."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock-embeddings",
            version="1.0.0",
            description="Mock embeddings for testing",
        )

    @property
    def provider_name(self) -> str:
        return "mock"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Return simple mock embeddings
        return [[0.1] * 384 for _ in texts]

    def get_dimension(self) -> int:
        return 384


class TestPluginMetadata:
    """Tests for PluginMetadata."""

    def test_basic_metadata(self):
        """Test creating basic metadata."""
        meta = PluginMetadata(name="test", version="1.0.0")
        assert meta.name == "test"
        assert meta.version == "1.0.0"
        assert meta.description == ""
        assert meta.author == ""
        assert meta.dependencies == []

    def test_full_metadata(self):
        """Test creating full metadata."""
        meta = PluginMetadata(
            name="test",
            version="2.0.0",
            description="A test plugin",
            author="Test Author",
            dependencies=["dep1", "dep2"],
        )
        assert meta.description == "A test plugin"
        assert meta.author == "Test Author"
        assert meta.dependencies == ["dep1", "dep2"]

    def test_str_representation(self):
        """Test string representation."""
        meta = PluginMetadata(name="test", version="1.0.0")
        assert str(meta) == "test v1.0.0"


class TestLanguageParserPlugin:
    """Tests for LanguageParserPlugin."""

    def test_mock_parser_metadata(self):
        """Test mock parser metadata."""
        parser = MockLanguageParser()
        assert parser.metadata.name == "mock-parser"
        assert parser.metadata.version == "1.0.0"

    def test_mock_parser_language(self):
        """Test mock parser language name."""
        parser = MockLanguageParser()
        assert parser.language_name == "mock"

    def test_mock_parser_extensions(self):
        """Test mock parser file extensions."""
        parser = MockLanguageParser()
        assert ".mock" in parser.file_extensions
        assert ".mck" in parser.file_extensions

    def test_detect_language(self):
        """Test language detection by extension."""
        parser = MockLanguageParser()
        assert parser.detect_language(Path("test.mock")) is True
        assert parser.detect_language(Path("test.mck")) is True
        assert parser.detect_language(Path("test.py")) is False

    def test_parse_file(self):
        """Test parsing a mock file."""
        parser = MockLanguageParser()
        chunks = parser.parse_file(Path("test.mock"), b"mock content")
        assert len(chunks) == 1
        assert chunks[0].name == "mock_function"


class TestWikiGeneratorPlugin:
    """Tests for WikiGeneratorPlugin."""

    def test_mock_generator_metadata(self):
        """Test mock generator metadata."""
        gen = MockWikiGenerator()
        assert gen.metadata.name == "mock-generator"

    def test_mock_generator_name(self):
        """Test mock generator name."""
        gen = MockWikiGenerator("custom-name")
        assert gen.generator_name == "custom-name"

    def test_default_priority(self):
        """Test default priority."""
        gen = MockWikiGenerator()
        assert gen.priority == 0

    def test_default_run_after(self):
        """Test default run_after."""
        gen = MockWikiGenerator()
        assert gen.run_after == []

    async def test_generate(self):
        """Test generating wiki pages."""
        gen = MockWikiGenerator()
        index_status = IndexStatus(
            repo_path="/test",
            indexed_at=0.0,
            total_files=0,
            total_chunks=0,
        )
        result = await gen.generate(index_status, Path("/wiki"), {})
        assert len(result.pages) == 1
        assert result.pages[0].title == "Mock Page"
        assert result.metadata["mock"] is True


class TestEmbeddingProviderPlugin:
    """Tests for EmbeddingProviderPlugin."""

    def test_mock_provider_metadata(self):
        """Test mock provider metadata."""
        provider = MockEmbeddingProvider()
        assert provider.metadata.name == "mock-embeddings"

    def test_mock_provider_name(self):
        """Test mock provider name."""
        provider = MockEmbeddingProvider()
        assert provider.provider_name == "mock"

    def test_get_dimension(self):
        """Test embedding dimension."""
        provider = MockEmbeddingProvider()
        assert provider.get_dimension() == 384

    async def test_embed(self):
        """Test embedding texts."""
        provider = MockEmbeddingProvider()
        embeddings = await provider.embed(["hello", "world"])
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 384


class TestPluginRegistry:
    """Tests for PluginRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return PluginRegistry()

    def test_empty_registry(self, registry):
        """Test empty registry."""
        assert registry.language_parsers == {}
        assert registry.wiki_generators == {}
        assert registry.embedding_providers == {}

    def test_register_language_parser(self, registry):
        """Test registering a language parser."""
        parser = MockLanguageParser()
        registry.register_language_parser(parser)
        assert "mock" in registry.language_parsers
        assert registry.get_language_parser("mock") is parser

    def test_register_wiki_generator(self, registry):
        """Test registering a wiki generator."""
        gen = MockWikiGenerator()
        registry.register_wiki_generator(gen)
        assert "mock-generator" in registry.wiki_generators
        assert registry.get_wiki_generator("mock-generator") is gen

    def test_register_embedding_provider(self, registry):
        """Test registering an embedding provider."""
        provider = MockEmbeddingProvider()
        registry.register_embedding_provider(provider)
        assert "mock" in registry.embedding_providers
        assert registry.get_embedding_provider("mock") is provider

    def test_register_by_type(self, registry):
        """Test registering plugins by type detection."""
        parser = MockLanguageParser()
        gen = MockWikiGenerator()
        provider = MockEmbeddingProvider()

        registry.register(parser)
        registry.register(gen)
        registry.register(provider)

        assert "mock" in registry.language_parsers
        assert "mock-generator" in registry.wiki_generators
        assert "mock" in registry.embedding_providers

    def test_register_unknown_type(self, registry):
        """Test registering unknown plugin type raises error."""

        class UnknownPlugin(Plugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(name="unknown", version="1.0.0")

        with pytest.raises(TypeError):
            registry.register(UnknownPlugin())

    def test_unregister_language_parser(self, registry):
        """Test unregistering a language parser."""
        parser = MockLanguageParser()
        registry.register_language_parser(parser)
        assert registry.unregister_language_parser("mock") is True
        assert registry.get_language_parser("mock") is None
        assert registry.unregister_language_parser("mock") is False

    def test_unregister_wiki_generator(self, registry):
        """Test unregistering a wiki generator."""
        gen = MockWikiGenerator()
        registry.register_wiki_generator(gen)
        assert registry.unregister_wiki_generator("mock-generator") is True
        assert registry.get_wiki_generator("mock-generator") is None

    def test_unregister_embedding_provider(self, registry):
        """Test unregistering an embedding provider."""
        provider = MockEmbeddingProvider()
        registry.register_embedding_provider(provider)
        assert registry.unregister_embedding_provider("mock") is True
        assert registry.get_embedding_provider("mock") is None

    def test_get_parser_for_extension(self, registry):
        """Test finding parser by extension."""
        parser = MockLanguageParser()
        registry.register_language_parser(parser)

        assert registry.get_parser_for_extension(".mock") is parser
        assert registry.get_parser_for_extension(".MCK") is parser  # Case insensitive
        assert registry.get_parser_for_extension(".py") is None

    def test_list_plugins(self, registry):
        """Test listing all plugins."""
        registry.register_language_parser(MockLanguageParser())
        registry.register_wiki_generator(MockWikiGenerator())
        registry.register_embedding_provider(MockEmbeddingProvider())

        plugins = registry.list_plugins()
        assert "mock" in plugins["language_parsers"]
        assert "mock-generator" in plugins["wiki_generators"]
        assert "mock" in plugins["embedding_providers"]

    def test_cleanup_all(self, registry):
        """Test cleaning up all plugins."""
        registry.register_language_parser(MockLanguageParser())
        registry.register_wiki_generator(MockWikiGenerator())
        registry.register_embedding_provider(MockEmbeddingProvider())

        registry.cleanup_all()

        assert registry.language_parsers == {}
        assert registry.wiki_generators == {}
        assert registry.embedding_providers == {}

    def test_load_from_directory(self, registry, tmp_path):
        """Test loading plugins from directory."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create a simple plugin file
        plugin_file = plugins_dir / "test_plugin.py"
        plugin_file.write_text('''
from local_deepwiki.plugins import PluginMetadata, LanguageParserPlugin, get_plugin_registry
from local_deepwiki.models import CodeChunk
from pathlib import Path

class TestParser(LanguageParserPlugin):
    @property
    def metadata(self):
        return PluginMetadata(name="test-parser", version="1.0.0")

    @property
    def language_name(self):
        return "testlang"

    @property
    def file_extensions(self):
        return [".test"]

    def parse_file(self, file_path, source):
        return []

# Auto-register
get_plugin_registry().register(TestParser())
''')

        loaded = registry.load_from_directory(plugins_dir)
        # Note: This loads the module but registration goes to the global registry
        assert loaded == 1

    def test_load_from_nonexistent_directory(self, registry, tmp_path):
        """Test loading from non-existent directory."""
        loaded = registry.load_from_directory(tmp_path / "nonexistent")
        assert loaded == 0

    def test_load_skips_underscore_files(self, registry, tmp_path):
        """Test that files starting with underscore are skipped."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        (plugins_dir / "_private.py").write_text("# Private file")
        (plugins_dir / "__init__.py").write_text("# Init file")

        loaded = registry.load_from_directory(plugins_dir)
        assert loaded == 0


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_get_plugin_registry_returns_singleton(self):
        """Test that get_plugin_registry returns the same instance."""
        reset_plugin_registry()
        reg1 = get_plugin_registry()
        reg2 = get_plugin_registry()
        assert reg1 is reg2

    def test_reset_plugin_registry(self):
        """Test resetting the global registry."""
        reset_plugin_registry()
        reg1 = get_plugin_registry()
        reg1.register_language_parser(MockLanguageParser())

        reset_plugin_registry()
        reg2 = get_plugin_registry()
        assert reg2.language_parsers == {}
        assert reg1 is not reg2
